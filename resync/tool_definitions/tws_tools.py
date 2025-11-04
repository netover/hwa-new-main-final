"""High-level TWS troubleshooting tools exposed to agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from httpx import AsyncClient

from resync.models.tws import SystemStatus
from resync.utils.exceptions import (
    ToolConnectionError,
    ToolExecutionError,
    ToolProcessingError,
    TWSConnectionError,
)


def _normalise_status(payload: SystemStatus | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, SystemStatus):
        return payload.model_dump()
    return payload  # assume dict-like


def _normalise_jobs(data: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = data.get("jobs") or []
    return [dict(job) for job in jobs]


def _normalise_workstations(data: dict[str, Any]) -> list[dict[str, Any]]:
    workstations = data.get("workstations") or []
    return [dict(ws) for ws in workstations]


def _to_status_tuple(job: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(job.get("name", "UNKNOWN")),
        str(job.get("workstation", "N/A")),
        str(job.get("status", "UNKNOWN")),
    )


def _to_workstation_tuple(ws: dict[str, Any]) -> tuple[str, str]:
    return (
        str(ws.get("name", "UNKNOWN")),
        str(ws.get("status", "UNKNOWN")),
    )


@dataclass
class _BaseTWSTool:
    """Base class shared by the two TWS tools."""

    tws_client: Optional[Any] = None

    async def _resolve_client(self) -> Any:
        if self.tws_client is not None:
            return self.tws_client
        raise ToolExecutionError(
            "Cliente TWS não configurado para a ferramenta. Injete um cliente válido."
        )


class TWSStatusTool(_BaseTWSTool):
    """Tool responsible for reporting the current TWS status."""

    async def get_tws_status(self) -> str:
        client = await self._resolve_client()
        try:
            status = await client.get_system_status()
        except TWSConnectionError as exc:
            raise ToolConnectionError("Falha de comunicação com o TWS") from exc
        except ValueError as exc:
            raise ToolProcessingError(
                "Erro ao processar os dados de status do TWS"
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise ToolProcessingError(
                "Erro inesperado ao obter o status do TWS"
            ) from exc

        data = _normalise_status(status)
        workstations = _normalise_workstations(data)
        jobs = _normalise_jobs(data)

        lines: list[str] = ["Situa��o atual do TWS:"]
        if workstations:
            lines.append("Workstations monitoradas:")
            for name, ws_status in map(_to_workstation_tuple, workstations):
                lines.append(f"- {name} ({ws_status})")
        if jobs:
            lines.append("Jobs monitorados:")
            for name, workstation, job_status in map(_to_status_tuple, jobs):
                lines.append(f"- {name} on {workstation} ({job_status})")
        critical = data.get("critical_jobs") or []
        if critical:
            lines.append("Jobs críticos:")
            for job in critical:
                lines.append(f"- {job}")
        return "\n".join(lines)


class TWSTroubleshootingTool(_BaseTWSTool):
    """Tool capable of analysing the TWS environment for failures."""

    async def analyze_failures(self) -> str:
        client = await self._resolve_client()
        try:
            status = await client.get_system_status()
        except TWSConnectionError as exc:
            raise ToolConnectionError(
                "Falha de comunicação com o TWS ao analisar falhas"
            ) from exc
        except ValueError as exc:
            raise ToolProcessingError(
                "Erro ao processar os dados de falha do TWS"
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise ToolExecutionError(
                "Ocorreu um erro inesperado ao analisar as falhas do TWS"
            ) from exc

        data = _normalise_status(status)
        jobs = _normalise_jobs(data)
        workstations = _normalise_workstations(data)

        failing_jobs = [
            job for job in jobs if str(job.get("status", "")).upper() not in {"SUCC", "SUCCESS"}
        ]
        problematic_workstations = [
            ws for ws in workstations if str(ws.get("status", "")).upper() not in {"LINKED", "UP"}
        ]

        if not failing_jobs and not problematic_workstations:
            return "Nenhuma falha cr�tica encontrada. O ambiente TWS parece est�vel."

        lines: list[str] = ["An�lise de Problemas no TWS:"]
        if failing_jobs:
            formatted_jobs = ", ".join(
                f"{job.get('name', 'UNKNOWN')} (workstation: {job.get('workstation', 'N/A')})"
                for job in failing_jobs
            )
            lines.append(
                f"Jobs com Falha ({len(failing_jobs)}): {formatted_jobs}"
            )
        if problematic_workstations:
            formatted_ws = ", ".join(
                f"{ws.get('name', 'UNKNOWN')} (status: {ws.get('status', 'N/A')})"
                for ws in problematic_workstations
            )
            lines.append(
                f"Workstations com Problemas ({len(problematic_workstations)}): {formatted_ws}"
            )
        return "\n".join(lines)


# Shared instances that can be injected into agents or tests.
tws_status_tool = TWSStatusTool()
tws_troubleshooting_tool = TWSTroubleshootingTool()


__all__ = [
    "TWSStatusTool",
    "TWSTroubleshootingTool",
    "tws_status_tool",
    "tws_troubleshooting_tool",
]
