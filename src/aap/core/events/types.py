"""Los 11 tipos de evento del núcleo V1 (§9.4). Los diferidos
(AgentCreated, TaskReceived, ObservationCreated, EvaluationCompleted) no
están aquí a propósito: son control plane, redundantes o su propia tabla.
"""

from typing import Literal

EventType = Literal[
    "run.started",
    "run.finished",
    "step.started",
    "llm.called",
    "decision.made",
    "policy.evaluated",
    "tool.called",
    "tool.result",
    "state.updated",
    "memory.written",
    "error.raised",
]

EventLevel = Literal["DEBUG", "INFO", "WARN", "ERROR", "AUDIT"]
