"""Journal des événements du modèle (01 §2).

T-006 y inscrit les transitions de profil, T-007 les pertes et retours à l'emploi ; les
chocs exogènes des scénarios et la table ``events`` sont livrés par T-015.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from family_abm.core.types import HouseholdId, PersonId, Step


@dataclass(frozen=True, slots=True)
class ModelEvent:
    step: Step
    type: str  # types endogènes (04 §2.7) puis types de scénario (03 §10)
    household_id: HouseholdId
    person_id: PersonId | None = None
    detail: Mapping[str, str] = field(default_factory=dict)
    origin: str = "endogenous"  # "endogenous" | "scenario" (04 §2.7)
