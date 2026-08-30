from aap.core.definition.canonical import content_hash
from aap.core.definition.validate import validate_definition


def test_same_content_same_hash(demand_hunter_definition):
    a = validate_definition(demand_hunter_definition).model_dump(mode="json")
    b = validate_definition(dict(demand_hunter_definition)).model_dump(mode="json")
    assert content_hash(a) == content_hash(b)


def test_key_order_does_not_affect_hash(demand_hunter_definition):
    reordered = dict(reversed(list(demand_hunter_definition.items())))
    a = validate_definition(demand_hunter_definition).model_dump(mode="json")
    b = validate_definition(reordered).model_dump(mode="json")
    assert content_hash(a) == content_hash(b)


def test_different_content_different_hash(demand_hunter_definition):
    a = validate_definition(demand_hunter_definition).model_dump(mode="json")
    demand_hunter_definition["goal"]["statement"] += " (v2)"
    b = validate_definition(demand_hunter_definition).model_dump(mode="json")
    assert content_hash(a) != content_hash(b)
