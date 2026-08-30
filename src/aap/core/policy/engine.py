"""El punto de paso obligatorio entre decisión y ejecución (§11.1).

`authorize()` es lo único que decide si una tool se ejecuta. No hay
`skip_policy=True`, no hay ruta alternativa: el ToolBroker (H3) no tiene
ninguna otra forma de invocar una tool.

Tres niveles que se componen, del más general al más específico
(§11.2): sistema (inmutable, en código) → agente (declarado en la
Definición) → run (puede restringir aún más, p.ej. `dry_run`). Cada
nivel solo puede restringir, nunca ampliar.
"""

import fnmatch
from dataclasses import dataclass
from typing import Literal

from aap.core.policy.context import PolicyContext
from aap.core.tools.spec import ToolSpec

PolicyAction = Literal["ALLOW", "DENY", "REQUIRE_APPROVAL"]

# Nivel SISTEMA: inmutable, nunca configurable desde una Definición.
# shell.exec está fuera de V1 por completo (§10.2) — denegado siempre,
# pase lo que pase en la política del agente.
_SYSTEM_DENIED_PREFIXES = ("shell.",)


@dataclass
class PolicyDecision:
    action: PolicyAction
    reason: str | None = None


class PolicyEngine:
    def authorize(
        self, ctx: PolicyContext, tool_id: str, arguments: dict, spec: ToolSpec
    ) -> PolicyDecision:
        system_decision = self._check_system_policy(tool_id)
        if system_decision:
            return system_decision

        budget_decision = self._check_budget(ctx)
        if budget_decision:
            return budget_decision

        if ctx.dry_run and spec.side_effects != "read":
            return PolicyDecision("DENY", "dry_run: solo se permiten tools de lectura")

        decision = self._check_network(ctx, spec)
        if decision:
            return decision
        decision = self._check_database(ctx, spec, arguments)
        if decision:
            return decision
        decision = self._check_outbound_messages(ctx, spec)
        if decision:
            return decision
        decision = self._check_destructive(ctx, spec)
        if decision:
            return decision

        return PolicyDecision("ALLOW")

    def _check_system_policy(self, tool_id: str) -> PolicyDecision | None:
        if tool_id.startswith(_SYSTEM_DENIED_PREFIXES):
            return PolicyDecision("DENY", f"system_policy: {tool_id} no está permitido en V1")
        return None

    def _check_budget(self, ctx: PolicyContext) -> PolicyDecision | None:
        exhausted = ctx.budget.exhausted_dimension()
        if exhausted:
            return PolicyDecision("DENY", f"budget_exhausted:{exhausted}")
        return None

    def _check_network(self, ctx: PolicyContext, spec: ToolSpec) -> PolicyDecision | None:
        if "network.http" not in spec.permissions:
            return None
        net = ctx.policies.network
        if net.mode == "denied":
            return PolicyDecision("DENY", "network: acceso a red denegado por política")
        if net.mode == "allowlist":
            domain = spec.network_domain or ""
            if not any(fnmatch.fnmatch(domain, pattern) for pattern in net.domains):
                return PolicyDecision("DENY", f"network: dominio no permitido ({domain or 'desconocido'})")
        return None

    def _check_database(
        self, ctx: PolicyContext, spec: ToolSpec, arguments: dict
    ) -> PolicyDecision | None:
        wants_write = "database.write" in spec.permissions
        wants_read = "database.read" in spec.permissions
        if not (wants_write or wants_read):
            return None
        db = ctx.policies.database
        if db.domain_db == "denied":
            return PolicyDecision("DENY", "database: acceso denegado por política")
        if wants_write and db.domain_db != "read_write":
            return PolicyDecision("DENY", "database: la política solo permite lectura")
        table = arguments.get("table")
        if table and db.tables and table not in db.tables:
            return PolicyDecision("DENY", f"database: tabla no permitida ({table})")
        return None

    def _check_outbound_messages(self, ctx: PolicyContext, spec: ToolSpec) -> PolicyDecision | None:
        if "messaging.send" not in spec.permissions:
            return None
        mode = ctx.policies.outbound_messages.mode
        if mode == "denied":
            return PolicyDecision("DENY", "outbound_messages: denegado por política")
        if mode == "require_approval":
            return PolicyDecision("REQUIRE_APPROVAL", "outbound_messages requiere aprobación humana")
        return None

    def _check_destructive(self, ctx: PolicyContext, spec: ToolSpec) -> PolicyDecision | None:
        if spec.side_effects != "destructive":
            return None
        mode = ctx.policies.destructive_actions
        if mode == "deny":
            return PolicyDecision("DENY", "destructive_actions: denegado por política")
        if mode == "require_approval":
            return PolicyDecision("REQUIRE_APPROVAL", "acción destructiva requiere aprobación humana")
        return None
