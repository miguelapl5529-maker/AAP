"""Redacción de rutas declaradas en `ToolSpec.redact` (§10.1, §11.5).

Se usa al persistir en el event log (H4), nunca para mutar el resultado
real que recibe el agente en ejecución.
"""

import copy

_MASK = "***REDACTED***"


def redact(data: dict, paths: list[str]) -> dict:
    result = copy.deepcopy(data)
    for path in paths:
        _redact_path(result, path.split("."))
    return result


def _redact_path(obj, parts: list[str]) -> None:
    if not parts or not isinstance(obj, dict):
        return
    key, rest = parts[0], parts[1:]
    if not rest:
        if key in obj:
            obj[key] = _MASK
        return
    if key in obj:
        _redact_path(obj[key], rest)
