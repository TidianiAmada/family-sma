"""``PersonAgent`` — la seule classe de personne (D1, règle 1).

Coquille mince : identité, parcours et états passifs (02 §4). Aucune logique métier ;
l'hétérogénéité vient uniquement du profil cognitif (``profile_key``) et de ses paramètres.
Le rôle est une étiquette descriptive, jamais testée.
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal

import mesa

from family_abm.agents.states import (
    AffectiveState,
    CognitiveState,
    EconomicState,
    NeedsState,
    PhysicalState,
)
from family_abm.config.schemas import CognitiveProfile
from family_abm.core.rng import RngStreams
from family_abm.core.types import (
    MONTHS_PER_YEAR,
    HouseholdId,
    PersonId,
    Role,
    SchoolStatus,
    Step,
)
from family_abm.decision.engine import (
    Allocation,
    DecisionEngine,
    DemandSet,
    EffectiveCognitiveProfile,
    Percept,
)


class PersonAgent(mesa.Agent):
    """Un membre du foyer : perçoit (Temps 1), décide par son ``DecisionEngine``, agit (Temps 3)."""

    def __init__(
        self,
        model: mesa.Model,
        *,
        person_id: PersonId,
        household_id: HouseholdId,
        role: Role,
        profile_key: str,
        profiles: Mapping[str, CognitiveProfile],
        engine: DecisionEngine,
        streams: RngStreams,
        age_months: int,
        school_status: SchoolStatus,
        econ: EconomicState,
        phys: PhysicalState,
        needs: NeedsState,
        cog: CognitiveState,
        aff: AffectiveState,
    ) -> None:
        super().__init__(model)
        self.person_id = person_id
        self.household_id = household_id
        self.role = role
        self.profile_key = profile_key
        self.age_months = age_months
        self.school_status = school_status
        self.refused_edu_months = 0
        self.in_household = True  # V2
        self.econ = econ
        self.phys = phys
        self.needs = needs
        self.cog = cog
        self.aff = aff
        self.last_allocations: tuple[Allocation, ...] = ()
        self._profiles = profiles
        self._engine = engine
        self.streams = streams  # flux propres à la personne (« rng » est réservé par Mesa)

    @property
    def profile(self) -> CognitiveProfile:
        """Profil courant, résolu par sa clé (change par ``profile_transitions``)."""
        return self._profiles[self.profile_key]

    @property
    def age_years(self) -> float:
        return self.age_months / MONTHS_PER_YEAR

    def perceive(self, step: Step, ownership_share: float) -> Percept:
        """Perception du Temps 1 (10 §7.1).

        Squelette T-006 : les exigences monétaires r_k, montants minimaux, enveloppe,
        habitude et écart d'épargne sont renseignés par T-008 (besoins) et T-010 (épargne).
        """
        return Percept(
            step=step,
            person_id=self.person_id,
            age_years=self.age_years,
            needs_level=dict(self.needs.level),
            active_needs=self.needs.active,
            requirements={},
            amount_min={},
            expected_grant_ratio={need: 1.0 for need in self.needs.active},
            envelope=None,
            habitual=None,
            savings_gap=Decimal(0),
            ownership_share=ownership_share,
            sick_first_month=False,
            school_enrolled=self.school_status is SchoolStatus.ENROLLED,
        )

    def decide(self, percept: Percept) -> DemandSet:
        """Délègue au ``DecisionEngine`` avec le profil effectif (non modulé en V1) et le
        flux ``decision_ties`` propre à la personne."""
        base = self.profile
        return self._engine.decide(
            percept,
            EffectiveCognitiveProfile.from_profile(base),
            base,
            dict(self.cog.aspiration),
            self.streams["decision_ties"],
        )

    def act(self, allocations: Sequence[Allocation]) -> None:
        """Temps 3. Squelette T-006 : l'exécution des actions en écritures est livrée par T-011."""
        self.last_allocations = tuple(allocations)
