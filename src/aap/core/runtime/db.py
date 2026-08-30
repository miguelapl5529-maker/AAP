"""Bootstrap de runtime.db: las cinco tablas que le pertenecen (§21.1)."""

from pathlib import Path

from aap.core.evaluation.store import init_evaluations_table
from aap.core.events.log import init_events_table
from aap.core.runtime.runs import init_runs_table
from aap.core.runtime.state import init_run_state_table
from aap.core.runtime.tool_calls import init_tool_calls_table


def init_runtime_db(path: Path | None = None) -> None:
    init_runs_table(path)
    init_events_table(path)
    init_tool_calls_table(path)
    init_run_state_table(path)
    init_evaluations_table(path)
