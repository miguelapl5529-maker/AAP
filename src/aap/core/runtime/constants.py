"""Constantes compartidas entre core/runtime/ y las tools que implementan
capacidades del propio runtime (§20.2: core/ no importa de tools/, así
que el ID va aquí y tools/builtin/state.py lo importa de aquí, no al
revés)."""

STATE_UPDATE_TOOL_ID = "state.update"
