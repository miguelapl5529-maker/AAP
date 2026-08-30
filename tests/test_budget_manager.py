from aap.core.llm.interface import Usage
from aap.core.runtime.budget import BudgetManager
from tests.conftest import make_budget_policy


def test_fresh_budget_has_no_exhausted_dimension():
    manager = BudgetManager(make_budget_policy())
    assert manager.exhausted_dimension() is None


def test_max_steps_exhausts():
    manager = BudgetManager(make_budget_policy(max_steps=2))
    manager.consume_step()
    manager.consume_step()
    assert manager.exhausted_dimension() == "max_steps"


def test_max_tool_calls_exhausts():
    manager = BudgetManager(make_budget_policy(max_tool_calls=1))
    assert manager.can_afford_tool_call()
    manager.consume_tool_call()
    assert not manager.can_afford_tool_call()
    assert manager.exhausted_dimension() == "max_tool_calls"


def test_max_tokens_and_money_exhaust_via_llm_usage():
    manager = BudgetManager(make_budget_policy(max_tokens=100, max_money_usd=0.01))
    manager.consume_llm_usage(
        Usage(prompt_tokens=80, completion_tokens=30, cost_usd=0.02, latency_ms=1)
    )
    assert manager.exhausted_dimension() in {"max_tokens", "max_money_usd"}


def test_wallclock_exhausts_with_injectable_clock():
    fake_time = [0.0]
    manager = BudgetManager(make_budget_policy(max_wallclock_s=10), clock=lambda: fake_time[0])
    assert manager.exhausted_dimension() is None
    fake_time[0] = 11.0
    assert manager.exhausted_dimension() == "max_wallclock_s"


def test_remaining_reflects_consumption():
    manager = BudgetManager(make_budget_policy(max_tool_calls=5))
    manager.consume_tool_call()
    manager.consume_tool_call()
    assert manager.remaining()["tool_calls"] == 3
