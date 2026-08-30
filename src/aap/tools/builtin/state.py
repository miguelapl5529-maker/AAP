"""La única tool que todo agente tiene disponible sin declararla en su
Definition: escribir en su propio run_state (§9.2). No es domain-specific
ni parte del mundo mock — es infraestructura del runtime, y por eso el
ejecutor (H5) la registra siempre, no el agente.
"""

from aap.core.runtime.constants import STATE_UPDATE_TOOL_ID as TOOL_ID
from aap.core.runtime.state import get_state, update_state
from aap.core.tools.broker import ToolExecutionError
from aap.core.tools.spec import ToolSpec


def make_state_update_tool(run_id: str, state_schema: dict):
    spec = ToolSpec(
        id=TOOL_ID,
        title="Actualizar estado del run",
        description=(
            "Actualiza una o más claves del estado del run. Solo acepta las "
            "claves declaradas en state_schema; usar cualquier otra clave es "
            "un error explícito, nunca una escritura parcial silenciosa."
        ),
        input_schema={"type": "object"},
        output_schema={
            "type": "object",
            "properties": {"state": {"type": "object"}, "version": {"type": "integer"}},
            "required": ["state", "version"],
        },
        permissions=[],
        side_effects="write",
        idempotent=False,
    )

    def fn(args: dict) -> dict:
        unknown = [k for k in args if k not in state_schema]
        if unknown:
            raise ToolExecutionError(
                f"state.update: claves no declaradas en state_schema: {unknown}"
            )
        current = get_state(run_id)
        new_state = {**current["state"], **args}
        new_version = update_state(run_id, new_state, expected_version=current["version"])
        return {"state": new_state, "version": new_version}

    return spec, fn
