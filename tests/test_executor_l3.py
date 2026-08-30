from aap.core.definition.validate import validate_definition
from aap.core.llm.interface import CompletionResult, ToolCall, Usage
from aap.core.llm.providers.mock import MockProvider
from aap.core.runtime.executor import execute_run
from aap.core.runtime.runs import create_run
from aap.tools.mock.world import default_world
from tests.conftest import build_registry_with_state, make_scripted_router


def _l3_definition(base: dict, max_iterations: int = 5) -> dict:
    d = dict(base)
    d["runtime"] = {"autonomy_level": 3, "max_iterations": max_iterations}
    return d


def _usage() -> Usage:
    return Usage(prompt_tokens=40, completion_tokens=15, cost_usd=0.001, latency_ms=4)


def test_l3_replans_across_iterations_and_stops_as_soon_as_the_goal_is_met(demand_hunter_definition):
    definition = validate_definition(_l3_definition(demand_hunter_definition))
    world = default_world()
    run = create_run(definition.id, "v1")
    registry = build_registry_with_state(world, run["id"], definition.memory.state_schema)

    step1 = CompletionResult(
        text=None,
        tool_calls=[ToolCall(id="1", tool_id="search.web.mock", arguments={"query": "automatización"})],
        usage=_usage(), model_used="mock-scripted", finish_reason="tool_calls",
    )
    step2 = CompletionResult(
        text=None,
        tool_calls=[ToolCall(id="2", tool_id="state.update", arguments={"senales_validas": 1})],
        usage=_usage(), model_used="mock-scripted", finish_reason="tool_calls",
    )
    # Un tercer paso que NO debería llegar a consumirse: el criterio de
    # éxito ya se cumple al terminar step2.
    step3 = CompletionResult(
        text="no debería llamarse", tool_calls=[], usage=_usage(),
        model_used="mock-scripted", finish_reason="stop",
    )
    provider = MockProvider(script=[step1, step2, step3])
    router = make_scripted_router(provider)

    result = execute_run(definition, router, registry, run["id"], {"sector": "logistica"})

    assert provider.calls_made == 2
    assert result["steps"] == 2
    assert result["status"] == "completed"
    assert result["termination_reason"] == "completed"


def test_l3_finishes_when_the_model_stops_proposing_tool_calls(demand_hunter_definition):
    definition = validate_definition(_l3_definition(demand_hunter_definition))
    world = default_world()
    run = create_run(definition.id, "v1")
    registry = build_registry_with_state(world, run["id"], definition.memory.state_schema)

    final = CompletionResult(
        text="ya terminé, no encontré nada más", tool_calls=[], usage=_usage(),
        model_used="mock-scripted", finish_reason="stop",
    )
    router = make_scripted_router(MockProvider(script=[final]))

    result = execute_run(definition, router, registry, run["id"], {})

    assert result["status"] == "completed"
    assert result["termination_reason"] == "model_finished"
    assert result["output"]["text"] == "ya terminé, no encontré nada más"


def test_l3_exhausts_after_max_iterations_without_ever_finishing(demand_hunter_definition):
    definition = validate_definition(_l3_definition(demand_hunter_definition, max_iterations=2))
    world = default_world()
    run = create_run(definition.id, "v1")
    registry = build_registry_with_state(world, run["id"], definition.memory.state_schema)

    never_finishes = CompletionResult(
        text=None,
        tool_calls=[ToolCall(id="x", tool_id="search.web.mock", arguments={"query": "automatización"})],
        usage=_usage(), model_used="mock-scripted", finish_reason="tool_calls",
    )
    provider = MockProvider(script=[never_finishes, never_finishes])
    router = make_scripted_router(provider)

    result = execute_run(definition, router, registry, run["id"], {})

    assert result["status"] == "exhausted"
    assert result["termination_reason"] == "max_iterations"
    assert result["steps"] == 2
    assert provider.calls_made == 2


def test_l3_feeds_tool_results_back_into_the_conversation():
    """No es solo el contrato: el mensaje 'tool' realmente lleva el
    resultado, para que un LLM real pudiera usarlo en la siguiente vuelta."""
    seen_messages = []

    class _RecordingProvider:
        def __init__(self, script):
            self._script = list(script)

        def complete(self, req):
            seen_messages.append(list(req.messages))
            return self._script.pop(0)

    step1 = CompletionResult(
        text=None,
        tool_calls=[ToolCall(id="1", tool_id="search.web.mock", arguments={"query": "automatización"})],
        usage=_usage(), model_used="mock-scripted", finish_reason="tool_calls",
    )
    step2 = CompletionResult(text="listo", tool_calls=[], usage=_usage(), model_used="mock-scripted", finish_reason="stop")

    from aap.core.definition.validate import validate_definition as _validate

    def_dict = {
        "schema_version": 1, "id": "demo",
        "identity": {"name": "Demo", "description": ""},
        "goal": {"statement": "probar"},
        "runtime": {"autonomy_level": 3, "max_iterations": 5},
        "brain": {"primary": {"capability": "standard"}},
        "tools": [{"id": "search.web.mock"}],
        "policies": {
            "network": {"mode": "allowlist", "domains": ["*.internal.test"]},
            "budget": {
                "max_steps": 10, "max_tool_calls": 10, "max_tokens": 100000,
                "max_money_usd": 1.0, "max_wallclock_s": 60,
            },
        },
    }
    definition = _validate(def_dict)
    world = default_world()
    run = create_run(definition.id, "v1")
    registry = build_registry_with_state(world, run["id"], definition.memory.state_schema)
    router = make_scripted_router(_RecordingProvider([step1, step2]))

    execute_run(definition, router, registry, run["id"], {})

    second_call_messages = seen_messages[1]
    tool_messages = [m for m in second_call_messages if m.role == "tool"]
    assert len(tool_messages) == 1
    assert "results" in tool_messages[0].content
