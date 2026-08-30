from dataclasses import dataclass

from aap.core.definition.models import Policies
from aap.core.runtime.budget import BudgetManager


@dataclass
class PolicyContext:
    """Lo mínimo que `authorize()` necesita saber de la ejecución en curso."""

    policies: Policies
    budget: BudgetManager
    dry_run: bool = False
