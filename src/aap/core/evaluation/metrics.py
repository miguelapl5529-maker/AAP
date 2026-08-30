"""Métricas mecánicas (§12.2, Capa 1): gratis, siempre activas,
objetivas. Se calculan enteramente de `runs` y `tool_calls` — sin LLM,
sin humano. Responden ya a la mitad de las preguntas del brief: qué
falló, cuánto costó, cuánto tardó.
"""

from aap.core.runtime.runs import list_runs_by_version
from aap.core.runtime.tool_calls import list_tool_calls

_TERMINAL_STATUSES = ("completed", "failed", "exhausted", "cancelled", "crashed")


def _avg(values: list) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _empty_metrics() -> dict:
    return {
        "total_runs": 0,
        "completion_rate": None, "failure_rate": None, "exhausted_rate": None,
        "crashed_rate": None, "cancelled_rate": None,
        "cost_usd": {"avg": None, "total": 0.0},
        "latency_ms": {"avg": None},
        "steps": {"avg": None},
        "tool_calls": {"avg": None},
        "tool_error_rate": None,
        "policy_denial_rate": None,
        "cost_per_completed_run": None,
    }


def compute_metrics(runs: list[dict], tool_calls_flat: list[dict]) -> dict:
    total = len(runs)
    if total == 0:
        return _empty_metrics()

    counts = dict.fromkeys(_TERMINAL_STATUSES, 0)
    for r in runs:
        if r["status"] in counts:
            counts[r["status"]] += 1

    costs = [r["cost_usd"] for r in runs]
    completed = counts["completed"]
    completed_costs = [r["cost_usd"] for r in runs if r["status"] == "completed"]
    total_tool_attempts = len(tool_calls_flat)
    tool_errors = sum(1 for tc in tool_calls_flat if tc["status"] in ("error", "timeout"))
    tool_denials = sum(1 for tc in tool_calls_flat if tc["policy_decision"] == "DENY")

    return {
        "total_runs": total,
        "completion_rate": counts["completed"] / total,
        "failure_rate": counts["failed"] / total,
        "exhausted_rate": counts["exhausted"] / total,
        "crashed_rate": counts["crashed"] / total,
        "cancelled_rate": counts["cancelled"] / total,
        "cost_usd": {"avg": _avg(costs), "total": sum(costs)},
        "latency_ms": {"avg": _avg([r["latency_ms"] for r in runs])},
        "steps": {"avg": _avg([r["steps"] for r in runs])},
        "tool_calls": {"avg": _avg([r["tool_calls"] for r in runs])},
        "tool_error_rate": (tool_errors / total_tool_attempts) if total_tool_attempts else None,
        "policy_denial_rate": (tool_denials / total_tool_attempts) if total_tool_attempts else None,
        # Proxy honesto de "coste por outcome" (§12.3) mientras la Capa 3
        # (outcomes reales) siga fuera de V1: lo más cercano que hay es
        # coste por run que sí terminó bien.
        "cost_per_completed_run": (sum(completed_costs) / completed) if completed else None,
    }


def metrics_for_version(agent_version_id: str) -> dict:
    runs = list_runs_by_version(agent_version_id)
    tool_calls_flat = [tc for r in runs for tc in list_tool_calls(r["id"])]
    return compute_metrics(runs, tool_calls_flat)
