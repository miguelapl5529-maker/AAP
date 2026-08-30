import pytest

from aap.core.definition.validate import DefinitionValidationError, validate_definition


def test_valid_definition_parses(demand_hunter_definition):
    parsed = validate_definition(demand_hunter_definition)
    assert parsed.id == "demand-hunter"
    assert parsed.runtime.autonomy_level == 2
    assert parsed.policies.budget.max_steps == 25


def test_missing_budget_is_rejected(demand_hunter_definition):
    del demand_hunter_definition["policies"]["budget"]
    with pytest.raises(DefinitionValidationError):
        validate_definition(demand_hunter_definition)


def test_unknown_field_is_rejected(demand_hunter_definition):
    """P1: si el schema no lo declara, no se cuela silenciosamente."""
    demand_hunter_definition["a_shell_backdoor"] = {"mode": "allow"}
    with pytest.raises(DefinitionValidationError):
        validate_definition(demand_hunter_definition)


def test_autonomy_level_out_of_range_is_rejected(demand_hunter_definition):
    demand_hunter_definition["runtime"]["autonomy_level"] = 9
    with pytest.raises(DefinitionValidationError):
        validate_definition(demand_hunter_definition)
