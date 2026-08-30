from aap.core.policy.engine import PolicyEngine
from aap.core.tools.broker import ToolBroker
from aap.core.tools.registry import ToolRegistry
from aap.core.tools.spec import ToolSpec
from aap.domain.entities import query_entities
from aap.tools.mock.tools import build_mock_registry
from aap.tools.mock.world import default_world
from tests.conftest import make_policy_context


def _broker(registry: ToolRegistry) -> ToolBroker:
    return ToolBroker(registry, PolicyEngine())


def test_successful_call_returns_ok_and_consumes_budget():
    world = default_world()
    broker = _broker(build_mock_registry(world))
    ctx = make_policy_context()

    result = broker.invoke(ctx, "search.web.mock", {"query": "automatización"})

    assert result.status == "ok"
    assert result.policy_decision == "ALLOW"
    assert len(result.result["results"]) >= 1
    assert ctx.budget.usage.tool_calls == 1


def test_timeout_fault_is_reported_and_still_consumes_budget():
    world = default_world()
    world.schedule_fault("search.web.mock", "timeout")
    broker = _broker(build_mock_registry(world))
    ctx = make_policy_context()

    result = broker.invoke(ctx, "search.web.mock", {"query": "automatización"})

    assert result.status == "timeout"
    assert ctx.budget.usage.tool_calls == 1


def test_error_fault_is_reported():
    world = default_world()
    world.schedule_fault("search.web.mock", "error")
    broker = _broker(build_mock_registry(world))
    ctx = make_policy_context()

    result = broker.invoke(ctx, "search.web.mock", {"query": "automatización"})
    assert result.status == "error"
    assert "error simulado" in result.error


def test_empty_fault_returns_ok_with_no_results():
    world = default_world()
    world.schedule_fault("search.web.mock", "empty")
    broker = _broker(build_mock_registry(world))
    ctx = make_policy_context()

    result = broker.invoke(ctx, "search.web.mock", {"query": "automatización"})
    assert result.status == "ok"
    assert result.result["results"] == []


def test_duplicate_on_upsert_does_not_create_a_new_row():
    world = default_world()
    broker = _broker(build_mock_registry(world))
    ctx = make_policy_context()

    args = {"table": "companies", "natural_key": "rutasdelsur.mock", "values": {"name": "Rutas del Sur SL"}}
    first = broker.invoke(ctx, "db.upsert.mock", args)
    second = broker.invoke(ctx, "db.upsert.mock", args)

    assert first.result["status"] == "created"
    assert second.result["status"] == "duplicate"
    assert second.result["id"] == first.result["id"]
    assert len(query_entities("companies")) == 1


def test_policy_deny_end_to_end():
    """El escenario que pide el brief: el agente intenta una tool que su
    política no cubre y el broker devuelve DENY sin ejecutar nada."""
    world = default_world()
    broker = _broker(build_mock_registry(world))
    ctx = make_policy_context(database={"domain_db": "read_write", "tables": ["companies"]})

    result = broker.invoke(
        ctx, "db.upsert.mock",
        {"table": "signals", "natural_key": "x", "values": {}},
    )

    assert result.status == "denied"
    assert result.policy_decision == "DENY"
    assert "tabla no permitida" in result.error
    assert ctx.budget.usage.tool_calls == 0  # nunca se ejecutó: no cuenta contra el presupuesto


def test_require_approval_does_not_execute_either():
    world = default_world()
    ctx = make_policy_context(destructive_actions="require_approval")
    registry = build_mock_registry(world)
    registry.register(
        ToolSpec(id="db.delete.mock", title="Delete", description="destructiva", side_effects="destructive"),
        lambda args: {"deleted": True},
    )
    broker = _broker(registry)

    result = broker.invoke(ctx, "db.delete.mock", {})
    assert result.status == "pending_approval"
    assert ctx.budget.usage.tool_calls == 0


def test_invalid_input_is_rejected_before_execution():
    world = default_world()
    broker = _broker(build_mock_registry(world))
    ctx = make_policy_context()

    result = broker.invoke(ctx, "search.web.mock", {})  # falta "query", obligatorio
    assert result.status == "error"
    assert "input inválido" in result.error


def test_tool_returning_malformed_output_is_a_tool_bug_not_a_denial():
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            id="broken.tool",
            title="Broken",
            description="devuelve basura",
            output_schema={"type": "object", "required": ["expected_field"]},
        ),
        lambda args: {"unexpected": True},
    )
    broker = _broker(registry)
    ctx = make_policy_context()

    result = broker.invoke(ctx, "broken.tool", {})
    assert result.status == "error"
    assert "bug de la tool" in result.error
