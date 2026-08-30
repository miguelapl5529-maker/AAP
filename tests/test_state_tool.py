import pytest

from aap.core.runtime.state import get_state, init_state
from aap.core.tools.broker import ToolExecutionError
from aap.tools.builtin.state import make_state_update_tool


def test_state_update_writes_declared_keys():
    init_state("run-1", {"fase": "buscar", "senales_validas": 0})
    schema = {"fase": {"type": "string"}, "senales_validas": {"type": "integer"}}
    _, fn = make_state_update_tool("run-1", schema)

    result = fn({"senales_validas": 3})
    assert result["state"] == {"fase": "buscar", "senales_validas": 3}
    assert result["version"] == 2
    assert get_state("run-1")["state"]["senales_validas"] == 3


def test_state_update_rejects_undeclared_keys():
    init_state("run-1", {"fase": "buscar"})
    schema = {"fase": {"type": "string"}}
    _, fn = make_state_update_tool("run-1", schema)

    with pytest.raises(ToolExecutionError):
        fn({"clave_inventada": True})


def test_state_update_merges_instead_of_replacing():
    init_state("run-1", {"fase": "buscar", "senales_validas": 0})
    schema = {"fase": {"type": "string"}, "senales_validas": {"type": "integer"}}
    _, fn = make_state_update_tool("run-1", schema)

    fn({"senales_validas": 1})
    result = fn({"fase": "registrar"})
    assert result["state"] == {"fase": "registrar", "senales_validas": 1}
