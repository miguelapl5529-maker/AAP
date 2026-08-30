"""Estimación de tokens deliberadamente ingenua.

Un tokenizador real (tiktoken u otro) es una dependencia que esta fase no
necesita: para contabilidad de coste y para el presupuesto (P5) basta con
un recuento aproximado y estable. Se sustituye el día que un provider
concreto lo exija (P8: no se abstrae antes de la segunda repetición).
"""


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text.split()))
