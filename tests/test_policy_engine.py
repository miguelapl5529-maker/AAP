from aap.core.policy.engine import PolicyEngine
from aap.core.tools.spec import ToolSpec
from tests.conftest import make_policy_context

engine = PolicyEngine()


def _spec(**overrides) -> ToolSpec:
    defaults = dict(id="dummy.tool", title="Dummy", description="para pruebas")
    defaults.update(overrides)
    return ToolSpec(**defaults)


def test_shell_is_always_denied_regardless_of_agent_policy():
    ctx = make_policy_context(shell={"mode": "allow"})
    decision = engine.authorize(ctx, "shell.exec", {}, _spec(id="shell.exec"))
    assert decision.action == "DENY"
    assert "system_policy" in decision.reason


def test_budget_exhausted_denies_before_anything_else():
    ctx = make_policy_context(budget_overrides={"max_tool_calls": 1})
    ctx.budget.consume_tool_call()  # agota el único tool call disponible
    decision = engine.authorize(ctx, "search.web.mock", {}, _spec(permissions=["network.http"]))
    assert decision.action == "DENY"
    assert decision.reason == "budget_exhausted:max_tool_calls"


def test_dry_run_denies_non_read_tools():
    ctx = make_policy_context(dry_run=True)
    spec = _spec(side_effects="write")
    decision = engine.authorize(ctx, "db.upsert.mock", {}, spec)
    assert decision.action == "DENY"
    assert "dry_run" in decision.reason


def test_dry_run_allows_read_tools():
    ctx = make_policy_context(dry_run=True)
    spec = _spec(side_effects="read")
    decision = engine.authorize(ctx, "db.query.mock", {}, spec)
    assert decision.action == "ALLOW"


def test_network_denied_by_policy():
    ctx = make_policy_context(network={"mode": "denied", "domains": []})
    spec = _spec(permissions=["network.http"], network_domain="mock-search.internal.test")
    decision = engine.authorize(ctx, "search.web.mock", {}, spec)
    assert decision.action == "DENY"
    assert "network" in decision.reason


def test_network_allowlist_rejects_domain_not_covered():
    ctx = make_policy_context(network={"mode": "allowlist", "domains": ["*.linkedin.com"]})
    spec = _spec(permissions=["network.http"], network_domain="mock-search.internal.test")
    decision = engine.authorize(ctx, "search.web.mock", {}, spec)
    assert decision.action == "DENY"
    assert "network" in decision.reason


def test_network_allowlist_accepts_matching_domain():
    ctx = make_policy_context(network={"mode": "allowlist", "domains": ["*.internal.test"]})
    spec = _spec(permissions=["network.http"], network_domain="mock-search.internal.test")
    decision = engine.authorize(ctx, "search.web.mock", {}, spec)
    assert decision.action == "ALLOW"


def test_database_table_not_in_allowlist_is_denied():
    """El caso de DENY explícito que pide el brief: agente intenta una tool
    contra un recurso que su política no cubre."""
    ctx = make_policy_context(database={"domain_db": "read_write", "tables": ["companies"]})
    spec = _spec(permissions=["database.write"], side_effects="write")
    decision = engine.authorize(ctx, "db.upsert.mock", {"table": "signals"}, spec)
    assert decision.action == "DENY"
    assert "tabla no permitida" in decision.reason


def test_database_write_denied_when_policy_is_read_only():
    ctx = make_policy_context(database={"domain_db": "read_only", "tables": ["companies"]})
    spec = _spec(permissions=["database.write"], side_effects="write")
    decision = engine.authorize(ctx, "db.upsert.mock", {"table": "companies"}, spec)
    assert decision.action == "DENY"


def test_outbound_messages_require_approval():
    ctx = make_policy_context(outbound_messages={"mode": "require_approval"})
    spec = _spec(permissions=["messaging.send"])
    decision = engine.authorize(ctx, "whatsapp.send.mock", {}, spec)
    assert decision.action == "REQUIRE_APPROVAL"


def test_outbound_messages_denied():
    ctx = make_policy_context(outbound_messages={"mode": "denied"})
    spec = _spec(permissions=["messaging.send"])
    decision = engine.authorize(ctx, "whatsapp.send.mock", {}, spec)
    assert decision.action == "DENY"


def test_destructive_action_requires_approval_by_default():
    ctx = make_policy_context()
    spec = _spec(side_effects="destructive")
    decision = engine.authorize(ctx, "db.delete.mock", {}, spec)
    assert decision.action == "REQUIRE_APPROVAL"


def test_destructive_action_denied_when_policy_says_deny():
    ctx = make_policy_context(destructive_actions="deny")
    spec = _spec(side_effects="destructive")
    decision = engine.authorize(ctx, "db.delete.mock", {}, spec)
    assert decision.action == "DENY"


def test_plain_read_tool_with_no_special_permissions_is_allowed():
    ctx = make_policy_context()
    spec = _spec(permissions=[], side_effects="read")
    decision = engine.authorize(ctx, "llm.extract.mock", {}, spec)
    assert decision.action == "ALLOW"
