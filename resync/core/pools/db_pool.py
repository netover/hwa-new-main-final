"""
db_pool.py — versão robusta com melhorias críticas (SQLAlchemy 2.x + asyncio)

Princípios:
- Detecção robusta de dialeto: make_url() + tratamento específico SQLite
- Métricas precisas: separação acquisition_attempts/hits/misses sem dupla contagem
- Transações explícitas: commit/rollback seguro baseado em estado real
- SQLite otimizado: WAL + busy_timeout + retry para SQLITE_BUSY
- Health check enxuto: connect() + SELECT 1
- Observabilidade: redação de segredos em logs
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import sqlite3
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import (
    DisconnectionError,
    OperationalError,
    SQLAlchemyError,
)
from sqlalchemy.exc import TimeoutError as SATimeoutError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql import Executable

from resync.core.exceptions import DatabaseError
from resync.core.pools.base_pool import ConnectionPool, ConnectionPoolConfig

logger = logging.getLogger(__name__)


class SecretRedactor(logging.Filter):
    """Filtro para redação de segredos em logs."""

    PAT = re.compile(r"(password|api[_-]?key|token|secret)=([^&\s]+)", re.I)

    def filter(self, record: logging.LogRecord) -> bool:
        # Redação no msg
        if isinstance(record.msg, str):
            record.msg = self.PAT.sub(r"\1=[REDACTED]", record.msg)

        # Redação em args (tuple/dict)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self.PAT.sub(r"\1=[REDACTED]", str(v))
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self.PAT.sub(r"\1=[REDACTED]", str(a)) for a in record.args
                )
        return True


# Registro idempotente (evita duplicação em hot-reload)
_root = logging.getLogger()
if not any(
    getattr(f, "__class__", None).__name__ == "SecretRedactor" for f in _root.filters
):
    _root.addFilter(SecretRedactor())


async def execute_with_retry(
    session: AsyncSession,
    stmt: Executable | str,
    params: dict[str, Any] | None = None,
    *,
    max_retries: int = 5,
    base_delay: float = 0.1,
) -> Any:
    """Executa statement com retry para SQLITE_BUSY usando backoff+jitter."""
    # Limitar a SQLite para não mascarar erros de outros dialetos
    dialect = getattr(getattr(session, "bind", None), "dialect", None)
    if getattr(dialect, "name", "") != "sqlite":
        return await session.execute(stmt, params or {})

    tries = 0
    while True:
        try:
            return await session.execute(stmt, params or {})
        except (SQLAlchemyError, OperationalError) as e:
            # Verificar exceção SQLite específica
            orig = getattr(e, "orig", None)
            is_busy = isinstance(orig, sqlite3.OperationalError) and getattr(
                sqlite3, "SQLITE_BUSY", 5
            ) in getattr(orig, "args", (None,))
            msg = str(e).lower()

            # Fallback defensivo por mensagem
            if not (is_busy or "database is locked" in msg or "sqlite_busy" in msg):
                raise

            if tries >= max_retries:
                raise

            tries += 1
            delay = base_delay * (2 ** (tries - 1)) * (1 + random.uniform(-0.1, 0.1))
            await asyncio.sleep(delay)


class DatabaseConnectionPool(ConnectionPool[AsyncEngine]):
    """Pool de conexões assíncrono, enxuto e pronto para produção."""

    def __init__(self, config: ConnectionPoolConfig, database_url: str):
        super().__init__(config)
        self.database_url = database_url
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None
        self._sqlite_connect_handler = None  # Para tornar listener idempotente

    def _setup_sqlite_listeners(self) -> None:
        """Configura listeners para aplicar PRAGMAs a cada conexão SQLite."""
        # Tornar registro idempotente - evitar memory leaks
        if self._sqlite_connect_handler is not None:
            event.remove(
                self._engine.sync_engine,
                "connect",
                self._sqlite_connect_handler,
            )

        @event.listens_for(self._engine.sync_engine, "connect")
        def _sqlite_on_connect(dbapi_conn, _):
            # Atenção: PRAGMAs que são por conexão:
            # busy_timeout, synchronous, foreign_keys
            try:
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA busy_timeout = 2000;")  # 2s, por conexão
                cur.execute("PRAGMA foreign_keys = ON;")
                # 'journal_mode=WAL' é persistente no arquivo;
                # manter se quiser reforçar
                cur.execute("PRAGMA synchronous = NORMAL;")  # trade-off durabilidade
                cur.close()
                logger.debug(
                    "PRAGMAs SQLite aplicados por conexão para pool '%s'",
                    self.config.pool_name,
                )
            except (SQLAlchemyError, OSError) as e:
                # evitar travar boot por falha de PRAGMA
                logger.warning(
                    "Falha ao aplicar PRAGMAs SQLite por conexão no pool '%s': %s",
                    self.config.pool_name,
                    e,
                    exc_info=True,
                )

        self._sqlite_connect_handler = _sqlite_on_connect

    async def _setup_pool(self) -> None:
        """Inicializa engine/pool com detecção robusta de dialeto e configs otimizadas."""
        try:
            url = make_url(self.database_url)
            backend = url.get_backend_name()  # e.g., "sqlite", "postgresql"

            engine_kwargs: dict[str, Any] = {"echo": False}

            if backend == "sqlite":
                # Detectar se é in-memory SQLite
                is_memory = url.database in (
                    None,
                    "",
                    ":memory:",
                ) or self.database_url.startswith(
                    ("sqlite:///:memory:", "sqlite:///file::memory:")
                )

                # (A) timeout por conexão via DBAPI (aiosqlite suporta 'timeout')
                engine_kwargs.setdefault("connect_args", {})
                engine_kwargs["connect_args"].setdefault("timeout", 2.0)  # 2s

                if is_memory:
                    # Só in-memory precisa StaticPool para compartilhar conexão
                    engine_kwargs["poolclass"] = StaticPool
                    # não sobrescreve timeout
                    engine_kwargs["connect_args"]["check_same_thread"] = False
                    logger.info(
                        "Pool '%s' configurado com SQLite in-memory (StaticPool)",
                        self.config.pool_name,
                    )

                # Criar engine para SQLite
                self._engine = create_async_engine(self.database_url, **engine_kwargs)

                # (B) listeners síncronos para aplicar PRAGMAs a cada conexão
                self._setup_sqlite_listeners()  # também em in-memory para consistência

                if not is_memory:
                    await self._init_sqlite_pragmas()  # uma vez: journal_mode=WAL

                logger.info(
                    "Pool '%s' configurado com SQLite file-based (WAL + busy_timeout)",
                    self.config.pool_name,
                )
            else:
                # Outros bancos usam pool com configurações completas
                self._engine = create_async_engine(
                    self.database_url,
                    pool_size=self.config.min_size,
                    max_overflow=max(0, self.config.max_size - self.config.min_size),
                    pool_pre_ping=True,  # detecta conexões 'stale' no checkout
                    pool_recycle=self.config.max_lifetime,  # recicla após N segundos
                    pool_timeout=self.config.connection_timeout,  # tempo máx. do pool
                    echo=False,
                )

                logger.info(
                    "Pool '%s' inicializado (backend=%s, size=%s..%s, "
                    "timeout=%ss, recycle=%ss)",
                    self.config.pool_name,
                    backend,
                    self.config.min_size,
                    self.config.max_size,
                    self.config.connection_timeout,
                    self.config.max_lifetime,
                )

            # Config canônica para AsyncSession no 2.x
            self._sessionmaker = async_sessionmaker(
                self._engine,
                expire_on_commit=False,  # em async evita expirations que exigem lazy-load
            )

        except (SQLAlchemyError, ConnectionError, OSError, ValueError) as e:
            logger.error(
                "Falha ao iniciar pool '%s': %s",
                self.config.pool_name,
                e,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to setup database connection pool: {e}") from e

    async def _init_sqlite_pragmas(self) -> None:
        """Configura PRAGMAs persistentes para SQLite file-based."""
        try:
            async with self._engine.begin() as conn:
                await conn.exec_driver_sql("PRAGMA journal_mode=WAL;")  # persistente
                logger.debug(
                    "PRAGMA journal_mode=WAL aplicado para pool '%s'",
                    self.config.pool_name,
                )
        except (SQLAlchemyError, OSError) as e:
            logger.warning(
                "Falha ao aplicar PRAGMA journal_mode no pool '%s': %s",
                self.config.pool_name,
                e,
                exc_info=True,
            )

    @asynccontextmanager
    async def get_connection(self) -> AsyncIterator[AsyncSession]:
        """
        Fornece uma AsyncSession do pool com métricas precisas e tratamento robusto.

        - Métricas: acquisition_attempts/hits/misses/exhaustions/active_connections, latência
        - Commit explícito preferencial; rollback seguro em erro
        - Logs com exc_info=True para debugging
        - Converte Timeout do pool (exaustão) e erros SQLAlchemy em DatabaseError
        """
        if not self._initialized or self._shutdown or not self._sessionmaker:
            raise DatabaseError("Database pool not initialized or shutdown")

        # Separar métricas: tempo de espera vs tempo de uso
        acquire_start = time.monotonic()
        session_acquired = False

        # Incrementar tentativas de aquisição (métrica correta)
        await self.increment_stat("acquisition_attempts", 1)

        try:
            async with self._sessionmaker() as session:
                # Calcular tempo de espera (até conseguir sessão)
                acquire_wait = time.monotonic() - acquire_start
                await self.update_wait_time(acquire_wait)  # <-- só wait

                session_acquired = True
                await self.increment_stat("active_connections", 1)
                await self.increment_stat(
                    "pool_hits", 1
                )  # Hit só após conseguir sessão
                await self.increment_stat("session_acquisitions", 1)

                # Início do uso da sessão
                # use_start = time.monotonic()  # Commented out as not currently used

                try:
                    # Entrega a sessão ao chamador
                    yield session

                    # Preferível: commit explícito do chamador.
                    # Fallback seguro se quiser manter compatibilidade
                    if session.in_transaction():
                        await session.commit()

                except SATimeoutError as e:
                    await self.increment_stat("pool_exhaustions", 1)
                    await self.increment_stat("pool_misses", 1)

                    if session.in_transaction():
                        await session.rollback()

                    logger.warning(
                        "Timeout no pool '%s': %s",
                        self.config.pool_name,
                        e,
                        exc_info=True,
                    )
                    raise DatabaseError("Pool exhausted or timed out") from e

                except (
                    SQLAlchemyError,
                    DisconnectionError,
                    OperationalError,
                ) as e:
                    await self.increment_stat("connection_errors", 1)
                    # NOTA: não incrementar pool_misses aqui - erro durante uso da sessão

                    if session.in_transaction():
                        await session.rollback()

                    logger.error(
                        "Erro SQLAlchemy no pool '%s': %s",
                        self.config.pool_name,
                        e,
                        exc_info=True,
                    )
                    raise DatabaseError(f"Database operation failed: {e}") from e

        except SATimeoutError as e:
            # Captura timeout no "enter" do sessionmaker (antes do async with)
            await self.increment_stat("pool_exhaustions", 1)
            await self.increment_stat("pool_misses", 1)

            logger.warning(
                "Timeout no pool '%s': %s",
                self.config.pool_name,
                e,
                exc_info=True,
            )
            raise DatabaseError("Pool exhausted or timed out") from e

        except DatabaseError:
            # Já tratado e com métricas atualizadas - não fazer re-raise imediato
            logger.debug("DatabaseError já tratado, propagando")
            raise

        except (ConnectionError, OSError, ValueError) as e:
            await self.increment_stat("pool_misses", 1)

            logger.error(
                "Falha ao adquirir sessão do pool '%s': %s",
                self.config.pool_name,
                e,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to acquire DB connection: {e}") from e

        finally:
            if session_acquired:
                # Calcular duração do uso e atualizar métrica separada
                # _use_duration = (
                #     time.monotonic() - use_start
                # )  # Prefixado para evitar warning
                await self.increment_stat("active_connections", -1)
                # NOTA: await self.update_session_duration(_use_duration)  # nova métrica

    async def health_check(self) -> bool:
        """Health check portável: connect() + select(1) sem transação."""
        if not self._engine:
            return False

        try:
            async with self._engine.connect() as conn:
                result = await conn.execute(select(1))
                return bool(result.scalar())
        except (SQLAlchemyError, ConnectionError, OSError) as e:
            logger.warning(
                "Health-check falhou no pool '%s': %s",
                self.config.pool_name,
                e,
                exc_info=True,
            )
            return False

    async def _close_pool(self) -> None:
        """Fecha o engine/pool com descarte das conexões."""
        if self._engine:
            await self._engine.dispose()
            logger.info("Pool '%s' fechado", self.config.pool_name)
            self._engine = None
            self._sessionmaker = None
