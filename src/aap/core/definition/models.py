"""El "lenguaje" que el runtime interpreta (docs/ARCHITECTURE.md §14.2).

Pydantic es la fuente única: el JSON Schema que consumirán la UI y la API
(`GET /schema/agent-definition`, H10) se deriva de estos modelos con
`AgentDefinition.model_json_schema()`, en vez de mantener un `schema.json`
escrito a mano en paralelo que inevitablemente diverge (P8).

Simplificado a propósito para V1: sin `workflow.graph` (el canvas es B2,
fuera de esta fase) y sin `version`/`status`, que no son parte del
comportamiento del agente sino metadatos de la fila en `agent_versions`
(así el hash de contenido no cambia al promocionar una versión).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1

Capability = Literal["cheap", "standard", "heavy", "coding", "embedding"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SuccessCriterion(StrictModel):
    type: Literal["metric"] = "metric"
    expr: str


class Identity(StrictModel):
    name: str
    description: str = ""
    owner: str | None = None
    tags: list[str] = Field(default_factory=list)
    icon: str | None = None


class Goal(StrictModel):
    statement: str
    success_criteria: list[SuccessCriterion] = Field(default_factory=list)
    failure_criteria: list[SuccessCriterion] = Field(default_factory=list)


class RuntimeConfig(StrictModel):
    autonomy_level: int = Field(ge=0, le=4)
    max_iterations: int = Field(default=10, ge=1)
    concurrency: int = Field(default=1, ge=1)
    resumable: bool = True


class BrainSlot(StrictModel):
    capability: Capability
    temperature: float = 0.2
    use_for: list[str] = Field(default_factory=list)


class Brain(StrictModel):
    primary: BrainSlot
    reasoning: BrainSlot | None = None
    cheap: BrainSlot | None = None
    system_prompt_ref: str | None = None
    response_format: Literal["tool_calling", "json_schema", "text"] = "tool_calling"


class ToolRef(StrictModel):
    id: str
    config: dict = Field(default_factory=dict)


class KnowledgeSource(StrictModel):
    id: str
    type: Literal["document"] = "document"
    path: str


class Knowledge(StrictModel):
    sources: list[KnowledgeSource] = Field(default_factory=list)
    retrieval: dict = Field(default_factory=lambda: {"mode": "top_k", "k": 4, "min_score": 0.5})


class LongTermMemory(StrictModel):
    enabled: bool = False
    max_entries: int = Field(default=500, ge=1)
    types: list[str] = Field(default_factory=list)
    retrieval: dict = Field(default_factory=lambda: {"k": 6, "recency_weight": 0.3})


class Memory(StrictModel):
    long_term: LongTermMemory = Field(default_factory=LongTermMemory)
    state_schema: dict = Field(default_factory=dict)


class NetworkPolicy(StrictModel):
    mode: Literal["denied", "allowlist", "open"] = "denied"
    domains: list[str] = Field(default_factory=list)


class DatabasePolicy(StrictModel):
    domain_db: Literal["denied", "read_only", "read_write"] = "denied"
    tables: list[str] = Field(default_factory=list)


class OutboundMessagesPolicy(StrictModel):
    mode: Literal["denied", "allow", "require_approval"] = "denied"
    max_per_run: int | None = None
    max_per_day: int | None = None


class ApprovalPolicy(StrictModel):
    channel: Literal["ui", "none"] = "ui"
    timeout_s: int = 3600
    on_timeout: Literal["block", "deny"] = "block"


class BudgetPolicy(StrictModel):
    """Sin valor por defecto infinito — un agente sin presupuesto no es admisible (R3)."""

    max_steps: int = Field(ge=1)
    max_tool_calls: int = Field(ge=1)
    max_tokens: int = Field(ge=1)
    max_money_usd: float = Field(gt=0)
    max_wallclock_s: int = Field(ge=1)


class Policies(StrictModel):
    filesystem: dict = Field(default_factory=lambda: {"mode": "workspace_only", "write": True})
    network: NetworkPolicy = Field(default_factory=NetworkPolicy)
    database: DatabasePolicy = Field(default_factory=DatabasePolicy)
    shell: dict = Field(default_factory=lambda: {"mode": "denied"})
    destructive_actions: Literal["allow", "require_approval", "deny"] = "require_approval"
    outbound_messages: OutboundMessagesPolicy = Field(default_factory=OutboundMessagesPolicy)
    budget: BudgetPolicy
    approval: ApprovalPolicy = Field(default_factory=ApprovalPolicy)


class Trigger(StrictModel):
    type: Literal["schedule", "manual", "api"]
    cron: str | None = None
    timezone: str | None = None


class IOSchema(StrictModel):
    input_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)


class Evaluation(StrictModel):
    eval_set_ref: str | None = None
    metrics: list[str] = Field(default_factory=list)
    outcome_links: list[str] = Field(default_factory=list)


class Limits(StrictModel):
    max_runs_per_day: int | None = None
    max_concurrent_runs: int = Field(default=1, ge=1)


class AgentDefinition(StrictModel):
    """El documento completo. Es lo único que el runtime necesita para ejecutar un agente."""

    schema_version: int = SCHEMA_VERSION
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    identity: Identity
    goal: Goal
    runtime: RuntimeConfig
    brain: Brain
    tools: list[ToolRef] = Field(default_factory=list)
    knowledge: Knowledge = Field(default_factory=Knowledge)
    memory: Memory = Field(default_factory=Memory)
    policies: Policies
    triggers: list[Trigger] = Field(default_factory=lambda: [Trigger(type="manual")])
    io: IOSchema = Field(default_factory=IOSchema)
    evaluation: Evaluation = Field(default_factory=Evaluation)
    limits: Limits = Field(default_factory=Limits)
