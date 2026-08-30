"""El presupuesto es una política, no una métrica (§11.3).

Se consulta ANTES de cada llamada al LLM y de cada tool call —eso lo hace
el Policy Engine llamando a este manager dentro de `authorize()`— y se
decrementa DESPUÉS, cuando la llamada realmente se intentó.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from aap.core.definition.models import BudgetPolicy
from aap.core.llm.interface import Usage


@dataclass
class BudgetUsage:
    steps: int = 0
    tool_calls: int = 0
    tokens: int = 0
    money_usd: float = 0.0


class BudgetManager:
    def __init__(self, policy: BudgetPolicy, clock: Callable[[], float] = time.monotonic):
        self._policy = policy
        self._usage = BudgetUsage()
        self._clock = clock
        self._started_at = clock()

    @property
    def policy(self) -> BudgetPolicy:
        return self._policy

    @property
    def usage(self) -> BudgetUsage:
        return self._usage

    def elapsed_s(self) -> float:
        return self._clock() - self._started_at

    def can_afford_step(self) -> bool:
        return self._usage.steps < self._policy.max_steps

    def can_afford_tool_call(self) -> bool:
        return self._usage.tool_calls < self._policy.max_tool_calls

    def wallclock_exceeded(self) -> bool:
        return self.elapsed_s() > self._policy.max_wallclock_s

    def exhausted_dimension(self) -> str | None:
        """La primera dimensión agotada, en el orden en que más duele perderla."""
        if self.wallclock_exceeded():
            return "max_wallclock_s"
        if self._usage.money_usd >= self._policy.max_money_usd:
            return "max_money_usd"
        if self._usage.tokens >= self._policy.max_tokens:
            return "max_tokens"
        if not self.can_afford_tool_call():
            return "max_tool_calls"
        if not self.can_afford_step():
            return "max_steps"
        return None

    def consume_step(self) -> None:
        self._usage.steps += 1

    def consume_tool_call(self) -> None:
        self._usage.tool_calls += 1

    def consume_tokens(self, n: int) -> None:
        self._usage.tokens += n

    def consume_money(self, amount: float) -> None:
        self._usage.money_usd += amount

    def consume_llm_usage(self, usage: Usage) -> None:
        self.consume_tokens(usage.prompt_tokens + usage.completion_tokens)
        self.consume_money(usage.cost_usd)

    def remaining(self) -> dict:
        return {
            "steps": max(0, self._policy.max_steps - self._usage.steps),
            "tool_calls": max(0, self._policy.max_tool_calls - self._usage.tool_calls),
            "tokens": max(0, self._policy.max_tokens - self._usage.tokens),
            "money_usd": max(0.0, self._policy.max_money_usd - self._usage.money_usd),
            "wallclock_s": max(0.0, self._policy.max_wallclock_s - self.elapsed_s()),
        }
