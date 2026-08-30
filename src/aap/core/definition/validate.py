"""Punto único de validación de una Agent Definition (P1: definition-first).

Nadie —CLI, API, repositorio— valida una definición de otra forma. Si el
schema necesita un campo nuevo, se extiende `models.py`; nunca se hace un
`if` a mano en el runtime para tolerar una forma distinta.
"""

from pydantic import ValidationError as PydanticValidationError

from aap.core.definition.models import AgentDefinition


class DefinitionValidationError(ValueError):
    def __init__(self, errors: list[dict]):
        self.errors = errors
        summary = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in errors)
        super().__init__(f"Definición de agente inválida: {summary}")


def validate_definition(data: dict) -> AgentDefinition:
    try:
        return AgentDefinition.model_validate(data)
    except PydanticValidationError as exc:
        raise DefinitionValidationError(exc.errors()) from exc
