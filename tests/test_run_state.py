import pytest

from aap.core.runtime.state import (
    StateConflictError,
    StateNotFoundError,
    compute_diff,
    get_state,
    init_state,
    update_state,
)


def test_init_and_get_state():
    init_state("run-1", {"fase": "buscar", "senales_validas": 0})
    state = get_state("run-1")
    assert state["version"] == 1
    assert state["state"] == {"fase": "buscar", "senales_validas": 0}


def test_update_state_bumps_version():
    init_state("run-1", {"fase": "buscar"})
    new_version = update_state("run-1", {"fase": "registrar"}, expected_version=1)
    assert new_version == 2
    state = get_state("run-1")
    assert state["state"] == {"fase": "registrar"}
    assert state["version"] == 2


def test_update_with_stale_version_raises_conflict():
    init_state("run-1", {"fase": "buscar"})
    update_state("run-1", {"fase": "registrar"}, expected_version=1)
    with pytest.raises(StateConflictError):
        update_state("run-1", {"fase": "otra_cosa"}, expected_version=1)


def test_operations_on_unknown_run_raise_not_found():
    with pytest.raises(StateNotFoundError):
        get_state("run-nonexistent")
    with pytest.raises(StateNotFoundError):
        update_state("run-nonexistent", {}, expected_version=1)


def test_compute_diff_added_changed_removed():
    old = {"fase": "buscar", "cursor": "abc"}
    new = {"fase": "registrar", "senales_validas": 3}
    diff = compute_diff(old, new)
    assert diff["added"] == {"senales_validas": 3}
    assert diff["changed"] == {"fase": {"from": "buscar", "to": "registrar"}}
    assert diff["removed"] == ["cursor"]
