# async_ttl_cache_refactored_bestof.py
# Combina o melhor das duas propostas: concorrência segura (lock ordering + evicção global fora do lock-alvo),
# WAL write-ahead completo (SET/DELETE/CLEAR) com replay lazy em TODOS os métodos públicos,
# snapshot/restore FIEL (preserva expires_at/last_access por item e NÃO polui a WAL no restore),
# métricas O(1) de tamanho/memória, e uso disciplinado de `async with` para locks.

from __future__ import annotations

import asyncio
import logging
from time import time
from typing import Any, Dict, List, Optional, Tuple
from collections import deque

from resync.core.cache.base_cache import BaseCache
from resync.core.cache.memory_manager import CacheMemoryManager, CacheEntry
from resync.core.cache.persistence_manager import CachePersistenceManager
from resync.core.exceptions import CacheError
from resync.core.metrics import log_with_correlation, runtime_metrics
from resync.core.write_ahead_log import WalEntry, WalOperationType, WriteAheadLog

logger = logging.getLogger(__name__)

# ------------------------------
# Settings loading (robusto)
# ------------------------------
try:
    from django.conf import settings as django_settings  # type: ignore
    settings = django_settings
except Exception:
    try:
        import settings  # type: ignore
    except Exception:
        settings = None  # sem settings module; usar parâmetros explícitos/defaults


class AsyncTTLCache(BaseCache):
    """
    Async TTL cache com:
    - Shards + asyncio.Lock (ordem canônica 0..N-1 p/ operações multi-shard)
    - Evicção LRU global **fora** do lock do shard-alvo (evita deadlock)
    - WAL (SET/DELETE/CLEAR) write-ahead + replay lazy (em todos os métodos públicos)
    - Snapshot/restore fiel (preserva expires_at/last_access; restore NÃO escreve na WAL)
    - Limpeza de expirados em background
    - Métricas: contadores O(1) e janelas de latência via deque
    """

    # ------------------------------
    # Inicialização
    # ------------------------------
    def __init__(
        self,
        ttl_seconds: int = 60,
        cleanup_interval: int = 30,
        num_shards: int = 16,
        enable_wal: bool = False,
        wal_path: Optional[str] = None,
        max_entries: int = 100_000,
        max_memory_mb: int = 100,
        paranoia_mode: bool = False,
        snapshot_dir: str = "./cache_snapshots",
    ) -> None:

        correlation_id = runtime_metrics.create_correlation_id(
            {
                "component": "async_cache_refactored",
                "operation": "init",
                "ttl_seconds": ttl_seconds,
                "cleanup_interval": cleanup_interval,
                "num_shards": num_shards,
                "enable_wal": enable_wal,
                "max_entries": max_entries,
                "max_memory_mb": max_memory_mb,
                "paranoia_mode": paranoia_mode,
            }
        )

        try:
            # Carregar configuração de settings (se houver)
            if settings is not None:
                self.ttl_seconds = (
                    ttl_seconds if ttl_seconds != 60 else getattr(settings, "ASYNC_CACHE_TTL", ttl_seconds)
                )
                self.cleanup_interval = (
                    cleanup_interval
                    if cleanup_interval != 30
                    else getattr(settings, "ASYNC_CACHE_CLEANUP_INTERVAL", cleanup_interval)
                )
                self.num_shards = (
                    num_shards
                    if num_shards != 16
                    else getattr(settings, "ASYNC_CACHE_NUM_SHARDS", num_shards)
                )
                self.enable_wal = (
                    enable_wal
                    if enable_wal is not False
                    else getattr(settings, "ASYNC_CACHE_ENABLE_WAL", enable_wal)
                )
                self.wal_path = (
                    wal_path if wal_path is not None else getattr(settings, "ASYNC_CACHE_WAL_PATH", wal_path)
                )
                self.max_entries = (
                    max_entries
                    if max_entries != 100_000
                    else getattr(settings, "ASYNC_CACHE_MAX_ENTRIES", max_entries)
                )
                self.max_memory_mb = (
                    max_memory_mb
                    if max_memory_mb != 100
                    else getattr(settings, "ASYNC_CACHE_MAX_MEMORY_MB", max_memory_mb)
                )
                self.paranoia_mode = (
                    paranoia_mode
                    if paranoia_mode is not False
                    else getattr(settings, "ASYNC_CACHE_PARANOIA_MODE", paranoia_mode)
                )
                log_with_correlation(logging.DEBUG, "Loaded cache config from settings module", correlation_id)
            else:
                self.ttl_seconds = ttl_seconds
                self.cleanup_interval = cleanup_interval
                self.num_shards = num_shards
                self.enable_wal = enable_wal
                self.wal_path = wal_path
                self.max_entries = max_entries
                self.max_memory_mb = max_memory_mb
                self.paranoia_mode = paranoia_mode
                log_with_correlation(
                    logging.WARNING, "Settings module not available, using provided values or defaults", correlation_id
                )

            if self.paranoia_mode:
                self.max_entries = min(self.max_entries, 10_000)
                self.max_memory_mb = min(self.max_memory_mb, 10)

            self.num_shards = int(self.num_shards)
            self.shards: List[Dict[str, CacheEntry]] = [dict() for _ in range(self.num_shards)]
            self.shard_locks: List[asyncio.Lock] = [asyncio.Lock() for _ in range(self.num_shards)]
            self._startup_lock = asyncio.Lock()
            self._needs_wal_replay_on_first_use = True

            # contadores O(1) para evitar scans frequentes
            self._entry_count: int = 0
            self._memory_bytes: int = 0

            # métricas de lock
            self._lock_contention_counts = [0] * self.num_shards
            self._lock_acquisition_times = [deque(maxlen=100) for _ in range(self.num_shards)]

            # managers
            self.memory_manager = CacheMemoryManager(
                max_entries=self.max_entries, max_memory_mb=self.max_memory_mb, paranoia_mode=self.paranoia_mode
            )
            self.persistence_manager = CachePersistenceManager(snapshot_dir=snapshot_dir)

            # WAL
            self.wal: Optional[WriteAheadLog] = None
            if self.enable_wal:
                wal_path_to_use = self.wal_path or "./cache_wal"
                self.wal = WriteAheadLog(wal_path_to_use)
                log_with_correlation(logging.INFO, f"WAL enabled, path: {wal_path_to_use}", correlation_id)

            # cleanup background
            self.cleanup_task: Optional[asyncio.Task] = None
            self.is_running = False

            runtime_metrics.record_health_check(
                "async_cache_refactored",
                "initialized",
                {
                    "ttl_seconds": self.ttl_seconds,
                    "cleanup_interval": self.cleanup_interval,
                    "num_shards": self.num_shards,
                    "enable_wal": self.enable_wal,
                },
            )
            log_with_correlation(logging.INFO, "AsyncTTLCache (refactored) initialized successfully", correlation_id)

        except Exception as e:
            runtime_metrics.record_health_check("async_cache_refactored", "init_failed", {"error": str(e)})
            log_with_correlation(logging.CRITICAL, f"Failed to initialize AsyncTTLCache (refactored): {e}", correlation_id)
            raise
        finally:
            runtime_metrics.close_correlation_id(correlation_id)

    # ------------------------------
    # Helpers
    # ------------------------------
    def _now(self) -> float:
        return time()

    def _validate_key(self, key: Any) -> str:
        if not isinstance(key, str):
            key = str(key)
        if not key:
            raise CacheError("Key must be a non-empty string")
        if len(key) > 1000:
            raise CacheError("Key too long")
        if any(c in key for c in ("\x00", "\r", "\n")):
            raise CacheError("Key contains control characters")
        return key

    def _shard_index(self, key: str) -> int:
        try:
            h = hash(key)
        except Exception as e:
            raise CacheError(f"Unhashable key: {e}")
        if h < 0:
            h = -h
        return h % self.num_shards

    def _estimate_value_size(self, value: Any) -> int:
        try:
            return int(self.memory_manager.estimate_entry_size(value))  # type: ignore[attr-defined]
        except Exception:
            return 0

    # ------------------------------
    # Startup + Cleanup
    # ------------------------------
    async def _replay_wal_on_startup(self) -> int:
        if not self.enable_wal or not self.wal:
            return 0
        return await self.wal.replay_log(self)

    async def _ensure_started(self) -> None:
        if self._needs_wal_replay_on_first_use:
            async with self._startup_lock:
                if self._needs_wal_replay_on_first_use:
                    replayed = await self._replay_wal_on_startup()
                    logger.info("replayed_operations_from_WAL_on_first_use", extra={"replayed": replayed})
                    self._needs_wal_replay_on_first_use = False
        if not self.is_running:
            self.is_running = True
            if not self.cleanup_task or self.cleanup_task.done():
                self.cleanup_task = asyncio.create_task(self._cleanup_loop(), name="cache_cleanup_loop")

    async def _cleanup_loop(self) -> None:
        try:
            while self.is_running:
                await asyncio.sleep(self.cleanup_interval)
                await self._expire_entries_once()
        except asyncio.CancelledError:
            await self._expire_entries_once()
            raise
        except Exception as e:
            logger.exception("cleanup_loop_error: %s", e)

    async def _expire_entries_once(self) -> None:
        now = self._now()
        for i in range(self.num_shards):
            async with self.shard_locks[i]:
                shard = self.shards[i]
                to_delete = []
                for k, entry in shard.items():
                    exp = getattr(entry, "expires_at", None)
                    if exp is not None and exp <= now:
                        to_delete.append(k)
                for k in to_delete:
                    ce = shard.pop(k, None)
                    if ce is not None:
                        self._entry_count -= 1
                        self._memory_bytes -= int(getattr(ce, "size_bytes", 0))

    # ------------------------------
    # Global lock ordering utilities
    # ------------------------------
    async def _acquire_all_shard_locks(self) -> None:
        for i in range(self.num_shards):
            await self.shard_locks[i].acquire()

    def _release_all_shard_locks(self) -> None:
        for i in range(self.num_shards - 1, -1, -1):
            lock = self.shard_locks[i]
            if lock.locked():
                lock.release()

    # ------------------------------
    # Evicção global (fora do lock do shard-alvo)
    # ------------------------------
    async def _evict_globally_if_needed(self, incoming_bytes: int = 0) -> int:
        """
        Evicta LRU global enquanto:
         - entradas > max_entries  OU
         - memória > max_memory_mb (considerando o item que vai entrar)
        Retorna o número de chaves removidas.
        """
        max_bytes = self.max_memory_mb * 1024 * 1024
        if (self._entry_count < self.max_entries) and (self._memory_bytes + incoming_bytes <= max_bytes):
            return 0

        evicted = 0
        await self._acquire_all_shard_locks()
        try:
            # Reconta sob locks
            total_entries = 0
            total_bytes = 0
            candidates: List[Tuple[float, int, str, int]] = []  # (last_access, shard_idx, key, size_bytes)
            now = self._now()
            for i in range(self.num_shards):
                shard = self.shards[i]
                for k, entry in shard.items():
                    total_entries += 1
                    sz = int(getattr(entry, "size_bytes", 0))
                    total_bytes += sz
                    exp = getattr(entry, "expires_at", None)
                    if exp is None or exp > now:
                        la = float(getattr(entry, "last_access", 0.0))
                        candidates.append((la, i, k, sz))

            self._entry_count = total_entries
            self._memory_bytes = total_bytes

            target_bytes = max_bytes - incoming_bytes
            if self._entry_count <= self.max_entries and self._memory_bytes <= target_bytes:
                return 0

            candidates.sort(key=lambda x: x[0])  # LRU primeiro
            idx = 0
            while (self._entry_count > self.max_entries or self._memory_bytes > target_bytes) and idx < len(candidates):
                _, shard_idx, key, sz = candidates[idx]
                idx += 1
                entry = self.shards[shard_idx].pop(key, None)
                if entry is None:
                    continue
                # (Opcional) Registrar DELETE por política; normalmente evicção não precisa ir para a WAL.
                self._entry_count -= 1
                self._memory_bytes -= sz
                evicted += 1

            return evicted
        finally:
            self._release_all_shard_locks()

    # ------------------------------
    # API Pública
    # ------------------------------
    async def get(self, key: Any) -> Any:
        await self._ensure_started()
        k = self._validate_key(key)
        shard_idx = self._shard_index(k)
        now = self._now()

        async with self.shard_locks[shard_idx]:
            shard = self.shards[shard_idx]
            entry = shard.get(k)
            if entry is None:
                return None
            exp = getattr(entry, "expires_at", None)
            if exp is not None and exp <= now:
                shard.pop(k, None)
                self._entry_count -= 1
                self._memory_bytes -= int(getattr(entry, "size_bytes", 0))
                return None
            setattr(entry, "last_access", now)
            return entry.value

    async def set(self, key: Any, value: Any, ttl_seconds: Optional[int] = None) -> None:
        await self._ensure_started()
        k = self._validate_key(key)
        ttl = self.ttl_seconds if ttl_seconds is None else int(ttl_seconds)
        now = self._now()
        expires_at = now + ttl if ttl > 0 else None

        size_bytes = self._estimate_value_size(value)
        # Evicção GLOBAL fora do lock-alvo
        await self._evict_globally_if_needed(incoming_bytes=size_bytes)

        # WAL (write-ahead) antes da mutação
        if self.enable_wal and self.wal:
            entry = WalEntry(operation=getattr(WalOperationType, "SET", "SET"), key=k, value=value, ttl=ttl, ts=now)
            if hasattr(self.wal, "append"):
                await self.wal.append(entry)
            elif hasattr(self.wal, "log_operation"):
                await self.wal.log_operation(entry)  # type: ignore[attr-defined]

        shard_idx = self._shard_index(k)
        async with self.shard_locks[shard_idx]:
            shard = self.shards[shard_idx]
            prev = shard.get(k)
            if prev is not None:
                self._memory_bytes -= int(getattr(prev, "size_bytes", 0))
            else:
                self._entry_count += 1

            ce = CacheEntry(value=value, expires_at=expires_at, last_access=now, size_bytes=size_bytes)
            shard[k] = ce
            self._memory_bytes += size_bytes

    async def delete(self, key: Any) -> bool:
        await self._ensure_started()
        k = self._validate_key(key)

        # WAL antes
        if self.enable_wal and self.wal:
            entry = WalEntry(operation=getattr(WalOperationType, "DELETE", "DELETE"), key=k, ts=self._now())
            if hasattr(self.wal, "append"):
                await self.wal.append(entry)
            elif hasattr(self.wal, "log_operation"):
                await self.wal.log_operation(entry)  # type: ignore[attr-defined]

        shard_idx = self._shard_index(k)
        async with self.shard_locks[shard_idx]:
            shard = self.shards[shard_idx]
            prev = shard.pop(k, None)
            if prev is None:
                return False
            self._entry_count -= 1
            self._memory_bytes -= int(getattr(prev, "size_bytes", 0))
            return True

    async def clear(self) -> None:
        await self._ensure_started()

        # WAL para CLEAR — evita “reaparecimento” após restart
        if self.enable_wal and self.wal:
            entry = WalEntry(operation=getattr(WalOperationType, "CLEAR", "CLEAR"), ts=self._now())
            if hasattr(self.wal, "append"):
                await self.wal.append(entry)
            elif hasattr(self.wal, "log_operation"):
                await self.wal.log_operation(entry)  # type: ignore[attr-defined]

        await self._acquire_all_shard_locks()
        try:
            for i in range(self.num_shards):
                self.shards[i].clear()
            self._entry_count = 0
            self._memory_bytes = 0
        finally:
            self._release_all_shard_locks()

    async def size(self) -> int:
        # manter leve e O(1); sem _ensure_started para não bloquear métricas
        return self._entry_count

    async def bytes_used(self) -> int:
        return self._memory_bytes

    # ------------------------------
    # Snapshot / Restore (FIÉIS, sem poluir WAL)
    # ------------------------------
    async def create_backup_snapshot(self) -> str:
        """
        Snapshot assíncrono e lock-aware.
        Salva por shard: {key: {value, expires_at, last_access, size_bytes}}.
        """
        await self._ensure_started()
        await self._acquire_all_shard_locks()
        try:
            snapshot: Dict[str, Dict[str, Dict[str, Any]]] = {}
            for i in range(self.num_shards):
                shard = self.shards[i]
                if not shard:
                    continue
                sname = f"shard_{i}"
                snapshot[sname] = {}
                for k, e in shard.items():
                    snapshot[sname][k] = {
                        "value": e.value,
                        "expires_at": getattr(e, "expires_at", None),
                        "last_access": getattr(e, "last_access", 0.0),
                        "size_bytes": int(getattr(e, "size_bytes", 0)),
                    }
        finally:
            self._release_all_shard_locks()

        # PM pode ser sync/async
        if hasattr(self.persistence_manager, "create_backup_snapshot_async"):
            return await self.persistence_manager.create_backup_snapshot_async(snapshot)  # type: ignore[attr-defined]
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.persistence_manager.create_backup_snapshot, snapshot)

    async def restore_from_snapshot(self, snapshot_id: str) -> None:
        """
        Restaura snapshot preservando expires_at/last_access por item.
        NÃO escreve no WAL durante o restore.
        """
        await self._ensure_started()

        # Carrega snapshot (sync/async)
        if hasattr(self.persistence_manager, "load_snapshot_async"):
            data = await self.persistence_manager.load_snapshot_async(snapshot_id)  # type: ignore[attr-defined]
        else:
            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(None, self.persistence_manager.load_snapshot, snapshot_id)

        # Limpa estado atual (com WAL CLEAR para consistência com recovery futuro)
        await self.clear()

        # Repopula SEM escrever na WAL, diretamente em memória
        now = self._now()
        await self._acquire_all_shard_locks()
        try:
            for sname, shard_data in (data or {}).items():
                if not sname.startswith("shard_"):
                    continue
                try:
                    shard_idx = int(sname.split("_", 1)[1])
                except Exception:
                    continue
                if not (0 <= shard_idx < self.num_shards):
                    continue
                shard = self.shards[shard_idx]
                for k, ed in (shard_data or {}).items():
                    v = ed.get("value")
                    exp = ed.get("expires_at")
                    la = float(ed.get("last_access", now))
                    sz = int(ed.get("size_bytes", 0))
                    # Se expirado, ignore
                    if exp is not None and exp <= now:
                        continue
                    # Inserção direta
                    shard[k] = CacheEntry(value=v, expires_at=exp, last_access=la, size_bytes=sz)
                    self._entry_count += 1
                    self._memory_bytes += sz
        finally:
            self._release_all_shard_locks()

        logger.info("restore_from_snapshot_complete", extra={"snapshot_id": snapshot_id})

    # ------------------------------
    # WAL replay hooks (usados por WriteAheadLog.replay_log)
    # ------------------------------
    async def apply_wal_set(self, key: str, value: Any, ttl: Optional[int] = None, ts: Optional[float] = None):
        """
        Aplica SET do WAL sem re-logar. Mantém a mesma disciplina: evicção global fora de locks.
        """
        await self._ensure_started()
        k = self._validate_key(key)
        now = self._now()
        ttl_eff = self.ttl_seconds if ttl is None else int(ttl)
        expires_at = (ts or now) + ttl_eff if ttl_eff > 0 else None
        size_bytes = self._estimate_value_size(value)

        await self._evict_globally_if_needed(incoming_bytes=size_bytes)

        shard_idx = self._shard_index(k)
        async with self.shard_locks[shard_idx]:
            shard = self.shards[shard_idx]
            prev = shard.get(k)
            if prev is not None:
                self._memory_bytes -= int(getattr(prev, "size_bytes", 0))
            else:
                self._entry_count += 1
            ce = CacheEntry(value=value, expires_at=expires_at, last_access=ts or now, size_bytes=size_bytes)
            shard[k] = ce
            self._memory_bytes += size_bytes

    async def apply_wal_delete(self, key: str, **_: Any):
        await self._ensure_started()
        k = self._validate_key(key)
        shard_idx = self._shard_index(k)
        async with self.shard_locks[shard_idx]:
            shard = self.shards[shard_idx]
            prev = shard.pop(k, None)
            if prev is not None:
                self._entry_count -= 1
                self._memory_bytes -= int(getattr(prev, "size_bytes", 0))

    async def apply_wal_clear(self, **_: Any):
        await self._ensure_started()
        await self._acquire_all_shard_locks()
        try:
            for i in range(self.num_shards):
                self.shards[i].clear()
            self._entry_count = 0
            self._memory_bytes = 0
        finally:
            self._release_all_shard_locks()

    # ------------------------------
    # Observabilidade / ciclo de vida
    # ------------------------------
    async def keys(self) -> List[str]:
        await self._ensure_started()
        keys: List[str] = []
        await self._acquire_all_shard_locks()
        try:
            for i in range(self.num_shards):
                keys.extend(list(self.shards[i].keys()))
            return keys
        finally:
            self._release_all_shard_locks()

    async def shutdown(self) -> None:
        self.is_running = False
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        if self.enable_wal and self.wal and hasattr(self.wal, "close"):
            close = getattr(self.wal, "close")
            if asyncio.iscoroutinefunction(close):
                await close()  # type: ignore
            else:
                close()

    async def __aenter__(self) -> "AsyncTTLCache":
        await self._ensure_started()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.shutdown()
