"""Duplicación de agentes (§16.3). Capa sobre el Control Plane, sin
código de runtime (§6.13): si esto necesitara tocar `core/runtime` o
`core/tools`, sería la señal de que el schema es insuficiente, no de
que la Factory necesita más permisos.

Nunca copia runs, eventos, memorias ni estado — heredar comportamiento
sin heredar historial es la vía más rápida a comportamientos
inexplicables (§16.3).
"""

import copy as _copy

from aap.core.definition import repository as repo


def _deep_merge(base: dict, overrides: dict) -> dict:
    result = _copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = _copy.deepcopy(value)
    return result


def duplicate_agent(
    source_agent_id: str,
    new_agent_id: str,
    new_name: str,
    overrides: dict | None = None,
    owner: str | None = None,
    activate: bool = False,
    notes: str | None = None,
) -> dict:
    """Copia la definición de la versión ACTIVA del agente origen a un
    agente nuevo, aplicando `overrides` antes de guardar. `activate`
    sigue el valor por defecto de §16.3 (`status=draft`): quien duplica
    y no dice lo contrario obtiene un borrador, no algo ya corriendo.
    """
    source_version = repo.get_active_version(source_agent_id)
    definition = _copy.deepcopy(source_version["definition"])
    definition["id"] = new_agent_id
    if overrides:
        definition = _deep_merge(definition, overrides)

    repo.create_agent(new_agent_id, new_name, owner=owner)
    return repo.create_version(
        new_agent_id,
        definition,
        created_by=owner,
        notes=notes or f"duplicado de {source_agent_id} v{source_version['version']}",
        activate=activate,
    )
