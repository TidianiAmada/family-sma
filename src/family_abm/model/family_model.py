"""``FamilyModel`` — le modèle Mesa et l'ordonnancement d'un pas (01 §4, 10 §13).

Toute l'aléa passe par ``RngStreams`` (règle 8) : le générateur propre de Mesa est
initialisé avec la seed mais aucune logique n'y tire. Les soldes initiaux sont posés au
Ledger par des écritures ``OPENING_BALANCE`` au pas −1, exclues des NTA (10 §13).
"""

from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal

import mesa

from family_abm.agents.household import HouseholdAgent
from family_abm.agents.person import PersonAgent
from family_abm.agents.states import (
    AffectiveState,
    CognitiveState,
    EconomicState,
    HouseholdState,
    NeedsState,
    PhysicalState,
)
from family_abm.config.schemas import Member, SimulationConfig
from family_abm.core.errors import ConfigError
from family_abm.core.rng import RngStreams
from family_abm.core.types import (
    MONTHS_PER_YEAR,
    EmploymentStatus,
    HouseholdId,
    NeedKind,
    Role,
    SchoolStatus,
    Step,
    make_household_id,
    make_person_id,
    q,
)
from family_abm.decision.engine import DecisionEngine
from family_abm.economy.accounts import OPENING_STEP, AccountId, AccountKind, FlowCategory
from family_abm.economy.ledger import Ledger
from family_abm.model import scheduler
from family_abm.model.events import ModelEvent
from family_abm.model.scheduler import Phase

type PhaseObserver = Callable[[Step, Phase, HouseholdId | None], None]
"""Observateur de l'ordonnancement : (pas, temps, foyer ou None pour un temps global)."""

EMPLOYED = frozenset({EmploymentStatus.EMPLOYED_FORMAL, EmploymentStatus.EMPLOYED_INFORMAL})


class FamilyModel(mesa.Model):
    """Simulation d'un ou plusieurs foyers indépendants, pas mensuel."""

    def __init__(
        self,
        config: SimulationConfig,
        engine: DecisionEngine,
        *,
        run_id: str = "",
        on_phase: PhaseObserver | None = None,
    ) -> None:
        super().__init__(rng=config.seed)
        self.config = config
        self.run_id = run_id
        self.streams = RngStreams(config.seed)  # « rng » est réservé par Mesa
        self.ledger = Ledger()
        self.engine = engine
        self.step_index: Step = 0
        self.events: list[ModelEvent] = []
        self._on_phase = on_phase
        # V1 : un seul foyer ; population.n_households arrive avec population.yaml (V3).
        self.households: list[HouseholdAgent] = [self._build_household(0)]

    # --- initialisation (10 §13)

    def _build_household(self, index: int) -> HouseholdAgent:
        rules = self.config.household_rules
        baseline = rules.baseline_household
        household_id = make_household_id(index)
        ids = {m.key: make_person_id(household_id, j) for j, m in enumerate(baseline.members)}
        state = HouseholdState(
            weights={ids[key]: w for key, w in rules.allocation.weights.items()},
            ownership={pid: baseline.ownership.get(key, 0.0) for key, pid in ids.items()},
            head_id=ids[baseline.head],
        )
        household = HouseholdAgent(
            self,
            household_id=household_id,
            index=index,
            rules=rules,
            state=state,
            streams=self.streams.for_household(index),
            ledger=self.ledger,
        )
        for position, member in enumerate(baseline.members):
            streams = household.streams.for_member(position)
            household.add_member(self._build_person(member, ids[member.key], household_id, streams))
        self._post_opening_balances(household)
        return household

    def _build_person(
        self, member: Member, person_id: str, household_id: str, streams: RngStreams
    ) -> PersonAgent:
        config = self.config
        try:
            role = Role(member.key)  # étiquette descriptive uniquement (D1)
        except ValueError as exc:
            raise ConfigError(f"membre {member.key!r} : clé sans rôle {list(Role)}") from exc
        profile = config.profiles[member.profile]
        # Âge en mois arrondi au plus proche (demi vers le haut) : seule source de l'âge.
        age_months = int(
            (Decimal(str(member.age)) * MONTHS_PER_YEAR).quantize(Decimal(1), ROUND_HALF_UP)
        )
        age_years = age_months / MONTHS_PER_YEAR
        active = scheduler.active_needs(config.needs, age_years)
        economic = config.economic_params
        wage = (
            q(economic.wages[member.wage_key] * economic.wage_scale)
            if member.wage_key is not None
            else Decimal(0)
        )
        return PersonAgent(
            self,
            person_id=person_id,
            household_id=household_id,
            role=role,
            profile_key=member.profile,
            profiles=config.profiles,
            engine=self.engine,
            streams=streams,
            age_months=age_months,
            school_status=self._initial_school_status(member, age_years),
            econ=EconomicState(
                employment=member.employment,
                wage_monthly=wage,
                labor_supply=1.0 if member.employment in EMPLOYED else 0.0,
                pooling_rate=config.household_rules.pooling.get(member.key, 0.0),
            ),
            phys=PhysicalState(health=1.0),
            # level initial = 1 ; SECURITY = sat_security,0 est posé par T-008 (10 §4).
            needs=NeedsState(level=dict.fromkeys(active, 1.0), satisfaction={}, active=active),
            cog=CognitiveState(aspiration=dict.fromkeys(NeedKind, profile.aspiration_init)),
            aff=AffectiveState(),
        )

    def _initial_school_status(self, member: Member, age_years: float) -> SchoolStatus:
        """``SchoolStatus`` déduit de l'âge et de l'emploi (10 §13)."""
        if age_years < self.config.economic_params.schooling.entry_age:
            return SchoolStatus.NOT_SCHOOL_AGE
        if member.employment is EmploymentStatus.STUDENT:
            return SchoolStatus.ENROLLED
        return SchoolStatus.COMPLETED

    def _post_opening_balances(self, household: HouseholdAgent) -> None:
        assets = household.rules.baseline_household.initial_assets
        bank = AccountId(AccountKind.BANK, None)
        hid = household.household_id
        opening = FlowCategory.OPENING_BALANCE
        for kind, amount in (
            (AccountKind.HOUSEHOLD_POT, assets.pot),
            (AccountKind.HOUSEHOLD_SAVINGS, assets.savings),
        ):
            if amount > 0:
                self.ledger.post(
                    OPENING_STEP, hid, bank, household.account(kind), q(amount), opening
                )
        if assets.loan > 0:
            loan = household.account(AccountKind.HOUSEHOLD_LOAN)
            self.ledger.post(OPENING_STEP, hid, loan, bank, q(assets.loan), opening)

    # --- ordonnancement (01 §4)

    def _phase(self, phase: Phase, household_id: HouseholdId | None = None) -> None:
        if self._on_phase is not None:
            self._on_phase(self.step_index, phase, household_id)

    def step(self) -> None:
        """Un pas mensuel : événements → Temps 1 → Temps 2 → Temps 3 → mesure → âge."""
        step = self.step_index
        self._phase(Phase.EVENTS)  # chocs exogènes : T-015
        for household in self.households:
            self._phase(Phase.TIME1, household.household_id)
            scheduler.time1(household, step)
        for household in self.households:
            self._phase(Phase.TIME2, household.household_id)
            scheduler.time2(household, step)
        for household in self.households:
            self._phase(Phase.TIME3, household.household_id)
            scheduler.time3(household, step)
        self._phase(Phase.MEASURE)  # NTA, invariants, collecte : T-012 à T-014
        for household in self.households:
            self._phase(Phase.AGE, household.household_id)
            self.events.extend(
                scheduler.age(
                    household,
                    step,
                    self.config.household_rules.profile_transitions,
                    self.config.needs,
                )
            )
        self.step_index += 1

    def run(self) -> None:
        """Exécute ``horizon_months`` pas. ``RunResult`` et ``run.json`` : T-014."""
        for _ in range(self.config.horizon_months):
            self.step()
