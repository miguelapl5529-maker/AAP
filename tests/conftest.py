import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Cada test corre contra su propio directorio de datos: nunca toca ./data real."""
    monkeypatch.setenv("AAP_DATA_DIR", str(tmp_path / "data"))
    yield tmp_path
