"""Registro de tools: id -> (spec, función). Genérico a propósito —no
distingue mock de real; eso lo decide quién construye el registro."""

from collections.abc import Callable
from dataclasses import dataclass

from aap.core.tools.spec import ToolSpec

ToolFn = Callable[[dict], dict]


class ToolNotFoundError(KeyError):
    pass


class DuplicateToolError(ValueError):
    pass


@dataclass
class RegisteredTool:
    spec: ToolSpec
    fn: ToolFn


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, spec: ToolSpec, fn: ToolFn) -> None:
        if spec.id in self._tools:
            raise DuplicateToolError(spec.id)
        self._tools[spec.id] = RegisteredTool(spec=spec, fn=fn)

    def get(self, tool_id: str) -> RegisteredTool:
        try:
            return self._tools[tool_id]
        except KeyError:
            raise ToolNotFoundError(tool_id) from None

    def list_specs(self) -> list[ToolSpec]:
        return [t.spec for t in self._tools.values()]
