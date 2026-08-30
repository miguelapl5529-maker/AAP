"""Context Builder (§5.1, capa 3): ensambla lo que el LLM ve.

Sin recuperación de knowledge todavía (RAG queda fuera de esta fase): el
prompt de sistema se construye solo a partir de identity + goal + tools
declaradas. Cuando exista knowledge.search (H futuro) esto es lo único
que hay que tocar — el executor no sabe cómo se construye un prompt.
"""

from aap.core.definition.models import AgentDefinition
from aap.core.llm.interface import Message
from aap.core.llm.interface import ToolSpec as LLMToolSpec
from aap.core.runtime.constants import STATE_UPDATE_TOOL_ID
from aap.core.tools.registry import ToolNotFoundError, ToolRegistry

_FRAMING = {
    "plan": (
        "Devuelve de una vez el plan completo de acciones necesarias para "
        "cumplir el objetivo, como llamadas a tools. No se te volverá a "
        "preguntar: tras esta respuesta, el plan se ejecuta tal cual."
    ),
    "react": (
        "Decide la siguiente acción a tomar. Si el objetivo ya está "
        "cumplido, responde con texto y sin tool_calls."
    ),
}


def build_system_message(definition: AgentDefinition, phase: str = "react") -> Message:
    tool_lines = "\n".join(f"- {t.id}" for t in definition.tools) or "(ninguna declarada)"
    content = (
        f"Eres el agente «{definition.identity.name}». {definition.identity.description}\n\n"
        f"Objetivo: {definition.goal.statement}\n\n"
        f"Tools disponibles:\n{tool_lines}\n\n{_FRAMING[phase]}"
    )
    return Message(role="system", content=content)


def _tool_is_registered(registry: ToolRegistry, tool_id: str) -> bool:
    try:
        registry.get(tool_id)
        return True
    except ToolNotFoundError:
        return False


def build_tool_specs(definition: AgentDefinition, registry: ToolRegistry) -> list[LLMToolSpec]:
    tool_ids = [t.id for t in definition.tools]
    if _tool_is_registered(registry, STATE_UPDATE_TOOL_ID):
        tool_ids.append(STATE_UPDATE_TOOL_ID)

    specs = []
    for tool_id in tool_ids:
        registered = registry.get(tool_id)
        specs.append(
            LLMToolSpec(
                id=registered.spec.id,
                description=registered.spec.description,
                parameters=registered.spec.input_schema,
            )
        )
    return specs
