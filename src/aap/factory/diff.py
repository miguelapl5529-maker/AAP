"""Diff legible entre dos versiones de un agente (§22.2, §14.3):
"un diff YAML legible que un humano puede revisar en treinta segundos".

Camino plano con notación de puntos (`policies.budget.max_steps`) en vez
de un árbol anidado — más fácil de escanear que JSON estructurado.
"""

from aap.core.definition import repository as repo


def _flatten(d: dict, prefix: str = "") -> dict:
    flat = {}
    for key, value in d.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten(value, path))
        else:
            flat[path] = value  # las listas no se desglosan más: se comparan por igualdad
    return flat


def deep_diff(old: dict, new: dict) -> dict:
    flat_old, flat_new = _flatten(old), _flatten(new)
    added = {k: v for k, v in flat_new.items() if k not in flat_old}
    removed = {k: v for k, v in flat_old.items() if k not in flat_new}
    changed = {
        k: {"from": flat_old[k], "to": flat_new[k]}
        for k in flat_new
        if k in flat_old and flat_old[k] != flat_new[k]
    }
    return {"added": added, "changed": changed, "removed": removed}


def diff_versions(agent_id: str, version_a: int, version_b: int) -> dict:
    a = repo.get_version(agent_id, version_a)
    b = repo.get_version(agent_id, version_b)
    return {
        "agent_id": agent_id,
        "a": version_a,
        "b": version_b,
        "diff": deep_diff(a["definition"], b["definition"]),
    }
