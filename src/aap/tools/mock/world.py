"""El mundo simulado (brief "MOCK WORLD"): antes de scraping real o
servicios externos, un universo pequeño y determinista donde las tools se
comportan como tools reales — incluidos sus fallos.
"""

from dataclasses import dataclass, field

Fault = str  # "timeout" | "error" | "empty" | "duplicate"


@dataclass
class Company:
    id: str
    name: str
    domain: str
    sector: str
    keywords: list[str] = field(default_factory=list)


@dataclass
class MockWorld:
    companies: list[Company] = field(default_factory=list)
    tables: dict[str, list[dict]] = field(default_factory=dict)
    memories: list[dict] = field(default_factory=list)
    fault_queues: dict[str, list[Fault]] = field(default_factory=dict)

    def schedule_fault(self, tool_id: str, fault: Fault) -> None:
        self.fault_queues.setdefault(tool_id, []).append(fault)

    def next_fault(self, tool_id: str) -> Fault | None:
        queue = self.fault_queues.get(tool_id)
        if queue:
            return queue.pop(0)
        return None

    def table(self, name: str) -> list[dict]:
        return self.tables.setdefault(name, [])


def default_world() -> MockWorld:
    """Un puñado de empresas del sector logístico, suficiente para que el
    Demand Hunter Demo (H6) tenga algo real que encontrar."""
    return MockWorld(
        companies=[
            Company(
                id="c1", name="Rutas del Sur SL", domain="rutasdelsur.mock",
                sector="logistica",
                keywords=["automatización", "flota", "procesos manuales"],
            ),
            Company(
                id="c2", name="TransCarga Ibérica", domain="transcarga.mock",
                sector="logistica",
                keywords=["optimización de rutas", "automatización de almacén"],
            ),
            Company(
                id="c3", name="Panadería Artesana Luna", domain="panaderialuna.mock",
                sector="alimentación",
                keywords=["venta al público"],
            ),
        ]
    )
