import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Cada test corre contra su propio directorio de datos: nunca toca ./data real."""
    monkeypatch.setenv("AAP_DATA_DIR", str(tmp_path / "data"))
    yield tmp_path


@pytest.fixture
def demand_hunter_definition() -> dict:
    """Definición mínima válida, usada por H1 en adelante como fixture compartida."""
    return {
        "schema_version": 1,
        "id": "demand-hunter",
        "identity": {
            "name": "Demand Hunter",
            "description": "Detecta empresas con señales de necesidad de automatización",
            "owner": "miguel",
            "tags": ["ventas", "prospección"],
        },
        "goal": {
            "statement": (
                "Encontrar empresas del sector logístico en España con señales de "
                "necesidad de automatización y registrarlas como oportunidades."
            ),
            "success_criteria": [{"type": "metric", "expr": "signals_qualified >= 1"}],
            "failure_criteria": [{"type": "metric", "expr": "tool_error_rate > 0.5"}],
        },
        "runtime": {"autonomy_level": 2, "max_iterations": 10, "resumable": True},
        "brain": {
            "primary": {"capability": "standard", "temperature": 0.2},
            "cheap": {"capability": "cheap", "use_for": ["extract"]},
        },
        "tools": [
            {"id": "search.web.mock", "config": {"max_results": 10}},
            {"id": "llm.extract.mock"},
            {"id": "db.upsert.mock", "config": {"tables": ["companies", "signals"]}},
            {"id": "memory.write.mock"},
        ],
        "memory": {
            "state_schema": {
                "fase": {"type": "string", "enum": ["buscar", "registrar"]},
                "senales_validas": {"type": "integer", "default": 0},
            }
        },
        "policies": {
            "network": {"mode": "allowlist", "domains": ["*.example-mock.test"]},
            "database": {"domain_db": "read_write", "tables": ["companies", "signals"]},
            "budget": {
                "max_steps": 25,
                "max_tool_calls": 60,
                "max_tokens": 400000,
                "max_money_usd": 2.0,
                "max_wallclock_s": 900,
            },
        },
        "triggers": [{"type": "manual"}],
    }
