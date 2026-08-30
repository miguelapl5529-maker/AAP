"""JSON Schema público de la Agent Definition.

Derivado de los modelos Pydantic, nunca escrito a mano en paralelo: así la
UI (H10, `GET /schema/agent-definition`) nunca puede divergir del
validador real (P8 — nada de dos fuentes de verdad para lo mismo).
"""

from aap.core.definition.models import AgentDefinition


def get_schema() -> dict:
    return AgentDefinition.model_json_schema()
