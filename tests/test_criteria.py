import pytest

from aap.core.runtime.criteria import InvalidCriterionError, evaluate, evaluate_all


def test_simple_comparisons():
    state = {"senales_validas": 3}
    assert evaluate("senales_validas >= 1", state) is True
    assert evaluate("senales_validas >= 10", state) is False
    assert evaluate("senales_validas == 3", state) is True
    assert evaluate("senales_validas != 3", state) is False
    assert evaluate("senales_validas < 10", state) is True
    assert evaluate("senales_validas > 10", state) is False


def test_negative_numbers_are_supported():
    assert evaluate("balance >= -5", {"balance": -3}) is True


def test_unknown_variable_raises():
    with pytest.raises(InvalidCriterionError):
        evaluate("no_declarada >= 1", {"otra": 1})


def test_arbitrary_python_is_rejected():
    """El punto entero de no usar eval(): esto NUNCA debe ejecutarse."""
    with pytest.raises(InvalidCriterionError):
        evaluate("__import__('os').system('echo pwned')", {})
    with pytest.raises(InvalidCriterionError):
        evaluate("(lambda: 1)() >= 1", {})
    with pytest.raises(InvalidCriterionError):
        evaluate("a >= 1 and b >= 1", {"a": 1, "b": 1})


def test_malformed_expression_raises():
    with pytest.raises(InvalidCriterionError):
        evaluate("esto no es una expresión válida ===", {})


class _Criterion:
    def __init__(self, expr):
        self.expr = expr


def test_evaluate_all_requires_every_criterion():
    criteria = [_Criterion("a >= 1"), _Criterion("b >= 1")]
    assert evaluate_all(criteria, {"a": 1, "b": 1}) is True
    assert evaluate_all(criteria, {"a": 1, "b": 0}) is False
