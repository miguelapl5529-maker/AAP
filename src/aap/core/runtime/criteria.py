"""Mini-lenguaje de comparación sobre variables de estado (§14.3, punto 1).

Las `expr` de `goal.success_criteria`/`failure_criteria` NUNCA se evalúan
con `eval()` de Python — sería una vía de ejecución arbitraria que rompe
todo el modelo de seguridad del sistema. Se parsean con `ast` y solo se
admite una comparación simple: `NOMBRE OPERADOR NUMERO`.
"""

import ast
import operator

_OPS = {
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}


class InvalidCriterionError(ValueError):
    pass


def evaluate(expr: str, state: dict) -> bool:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise InvalidCriterionError(f"expresión inválida: {expr!r}") from exc

    node = tree.body
    if not isinstance(node, ast.Compare) or len(node.ops) != 1 or len(node.comparators) != 1:
        raise InvalidCriterionError(f"solo se admite una comparación simple: {expr!r}")

    op_type = type(node.ops[0])
    if op_type not in _OPS:
        raise InvalidCriterionError(f"operador no soportado en: {expr!r}")

    left = _resolve_operand(node.left, state, expr)
    right = _resolve_operand(node.comparators[0], state, expr)
    return _OPS[op_type](left, right)


def _resolve_operand(node: ast.expr, state: dict, expr: str):
    if isinstance(node, ast.Name):
        if node.id not in state:
            raise InvalidCriterionError(f"variable de estado desconocida ({node.id!r}) en: {expr!r}")
        return state[node.id]
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_resolve_operand(node.operand, state, expr)
    raise InvalidCriterionError(f"operando no soportado en: {expr!r}")


def evaluate_all(criteria, state: dict) -> bool:
    """True si TODAS las expr se cumplen. `criteria` es una lista de
    objetos con atributo `.expr` (p.ej. `SuccessCriterion`)."""
    return all(evaluate(c.expr, state) for c in criteria)
