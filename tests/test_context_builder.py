from aap.core.definition.validate import validate_definition
from aap.core.runtime.context import build_system_message, build_tool_specs
from aap.tools.builtin.state import make_state_update_tool
from aap.tools.mock.tools import build_mock_registry
from aap.tools.mock.world import default_world


def test_system_message_mentions_identity_goal_and_tools(demand_hunter_definition):
    definition = validate_definition(demand_hunter_definition)
    message = build_system_message(definition, phase="react")
    assert "Demand Hunter" in message.content
    assert definition.goal.statement in message.content
    assert "search.web.mock" in message.content


def test_plan_phase_and_react_phase_have_different_framing(demand_hunter_definition):
    definition = validate_definition(demand_hunter_definition)
    plan_msg = build_system_message(definition, phase="plan")
    react_msg = build_system_message(definition, phase="react")
    assert plan_msg.content != react_msg.content


def test_tool_specs_include_only_declared_tools(demand_hunter_definition):
    definition = validate_definition(demand_hunter_definition)
    registry = build_mock_registry(default_world())
    specs = build_tool_specs(definition, registry)
    ids = {s.id for s in specs}
    assert ids == {t.id for t in definition.tools}


def test_state_update_is_added_when_registered(demand_hunter_definition):
    definition = validate_definition(demand_hunter_definition)
    registry = build_mock_registry(default_world())
    spec, fn = make_state_update_tool("run-1", definition.memory.state_schema)
    registry.register(spec, fn)

    specs = build_tool_specs(definition, registry)
    assert "state.update" in {s.id for s in specs}


def test_state_update_is_absent_when_not_registered(demand_hunter_definition):
    definition = validate_definition(demand_hunter_definition)
    registry = build_mock_registry(default_world())

    specs = build_tool_specs(definition, registry)
    assert "state.update" not in {s.id for s in specs}
