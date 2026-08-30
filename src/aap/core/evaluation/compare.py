"""Comparación de versiones por métricas mecánicas (§12.4): "qué
mejoró, qué empeoró, coste relativo, escenarios que rompieron". La
parte de "escenarios que rompieron" la cubre el eval runner
(eval_runner.py); esto cubre el "coste relativo" con datos de runs
reales ya ejecutados.
"""

from aap.core.definition import repository as repo
from aap.core.evaluation.metrics import metrics_for_version

_RATE_KEYS = ("completion_rate", "failure_rate", "exhausted_rate", "tool_error_rate", "policy_denial_rate")


def compare_versions_by_metrics(agent_id: str, version_a: int, version_b: int) -> dict:
    va = repo.get_version(agent_id, version_a)
    vb = repo.get_version(agent_id, version_b)
    ma = metrics_for_version(va["id"])
    mb = metrics_for_version(vb["id"])

    delta = {}
    for key in _RATE_KEYS:
        if ma[key] is not None and mb[key] is not None:
            delta[key] = mb[key] - ma[key]
    if ma["cost_usd"]["avg"] is not None and mb["cost_usd"]["avg"] is not None:
        delta["avg_cost_usd"] = mb["cost_usd"]["avg"] - ma["cost_usd"]["avg"]
    if ma["latency_ms"]["avg"] is not None and mb["latency_ms"]["avg"] is not None:
        delta["avg_latency_ms"] = mb["latency_ms"]["avg"] - ma["latency_ms"]["avg"]

    return {
        "agent_id": agent_id,
        "a": {"version": version_a, "metrics": ma},
        "b": {"version": version_b, "metrics": mb},
        "delta": delta,
    }
