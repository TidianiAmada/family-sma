"""``HouseholdAgent`` — le foyer : membres, état, règles, arbitrage (02 §1, §4.6).

Le foyer agit une seule fois par pas, au Temps 2, entre les deux phases des personnes
(01 §4). Il tient ses caches d'état à jour en s'abonnant au ``Ledger`` (seule source de
vérité, règle 4) et dispose de ses propres flux aléatoires (``streams``), dérivés de son indice : il
produit la même trajectoire qu'il soit simulé seul ou dans une population (01 §7).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

import mesa

from family_abm.agents.person import PersonAgent
from family_abm.agents.states import EconomicState, HouseholdState
from family_abm.config.schemas import EconomicParams, HouseholdRules
from family_abm.core.rng import RngStreams
from family_abm.core.types import (
    Capability,
    EmploymentStatus,
    HouseholdId,
    Money,
    NeedKind,
    PersonId,
    SchoolStatus,
    Step,
    q,
)
from family_abm.decision.engine import Allocation, DemandSet
from family_abm.economy import actions, labor, prices
from family_abm.economy.accounts import AccountId, AccountKind
from family_abm.economy.ledger import Ledger, LedgerEntry
from family_abm.health import health


@dataclass(frozen=True, slots=True)
class MemberEvent:
    """Événement endogène d'un membre, inscrit au journal du modèle par l'ordonnanceur.

    Distinct de ``model.events.ModelEvent`` : ``agents`` ne peut pas importer ``model``
    (couches, 01 §3) ; l'ordonnanceur complète le pas et le foyer.
    """

    person_id: PersonId
    type: Literal[
        "job_loss",
        "job_found",
        "health_episode",
        "recovered",
        "school_enrolled",
        "school_completed",
    ]  # types endogènes de 04 §2.7
    detail: Mapping[str, str] = field(default_factory=dict)


class HouseholdAgent(mesa.Agent):
    """Un foyer : collecte les demandes du Temps 1 et rend les allocations du Temps 2."""

    def __init__(
        self,
        model: mesa.Model,
        *,
        household_id: HouseholdId,
        index: int,
        rules: HouseholdRules,
        economic: EconomicParams,
        state: HouseholdState,
        streams: RngStreams,
        ledger: Ledger,
    ) -> None:
        super().__init__(model)
        self.household_id = household_id
        self.index = index
        self.rules = rules
        self.economic = economic
        self._price_index: dict[Step, Decimal] = {}  # P_t par pas (cache)
        self._reference_spending: Money | None = None  # dépense du pas 0 (10 §4)
        self.state = state
        self.streams = streams
        self.ledger = ledger
        self.members: list[PersonAgent] = []
        self.demand_sets: dict[PersonId, DemandSet] = {}
        self.allocations: dict[PersonId, tuple[Allocation, ...]] = {}
        ledger.subscribe(self._sync_caches)

    def add_member(self, person: PersonAgent) -> None:
        self.members.append(person)

    def member(self, person_id: PersonId) -> PersonAgent:
        for person in self.members:
            if person.person_id == person_id:
                return person
        raise KeyError(f"{person_id} n'est pas membre de {self.household_id}")

    def account(self, kind: AccountKind) -> AccountId:
        """Compte du foyer (pot, épargne, prêt)."""
        return AccountId(kind, self.household_id)

    # --- Temps 1 → Temps 2

    def start_step(self) -> None:
        """Vide les demandes et allocations du pas précédent."""
        self.demand_sets = {}
        self.allocations = {}

    def price_index(self, step: Step) -> Decimal:
        """``P_t`` du pas, calculé une fois (chocs de prix : T-015)."""
        if step not in self._price_index:
            self._price_index[step] = prices.price_index(step, self.economic)
        return self._price_index[step]

    def start_of_month(self, step: Step) -> list[MemberEvent]:
        """Début du Temps 1 : santé (10 §5) puis scolarité liée à l'âge (10 §6).

        Différés : l'abandon scolaire après refus des frais et ``refused_edu_months`` suivent
        l'exécution des allocations (T-011, 10 §9) ; ``health.care_paid_by = gov`` et les
        chocs de prix sont branchés avec les scénarios (T-015).
        """
        p_t = self.price_index(step)
        events: list[MemberEvent] = []
        for person in self.members:
            events.extend(self._update_health(person, p_t))
            events.extend(self._update_school(person))
        return events

    def _update_health(self, person: PersonAgent, p_t: Decimal) -> list[MemberEvent]:
        economic = self.economic
        phys = person.phys
        update = health.update_health(
            health.HealthState(
                health=phys.health,
                sick=phys.sick,
                cared=phys.cared,
                episode_months=phys.episode_months,
                health_pre_episode=phys.health_pre_episode,
                care_need=phys.care_need,
                labor_capacity=phys.labor_capacity,
            ),
            age_years=person.age_years,
            cfg=economic.health,
            episode_cost=economic.consumption_requirements.health.episode_cost,
            price_index=p_t,
            draw=health.draw_health(person.streams["health"], economic.health),
        )
        new = update.state
        phys.health, phys.sick, phys.cared = new.health, new.sick, new.cared
        phys.episode_months = new.episode_months
        phys.health_pre_episode = new.health_pre_episode
        phys.care_need, phys.labor_capacity = new.care_need, new.labor_capacity
        if update.event == "health_episode":
            detail = {"severity": repr(update.severity)}
            return [MemberEvent(person.person_id, "health_episode", detail)]
        if update.event == "recovered":
            return [MemberEvent(person.person_id, "recovered")]
        return []

    def _update_school(self, person: PersonAgent) -> list[MemberEvent]:
        before = person.school_status
        after = actions.school_status_by_age(before, person.age_years, self.economic.schooling)
        person.school_status = after
        if after is before:
            return []
        if after is SchoolStatus.ENROLLED:
            return [MemberEvent(person.person_id, "school_enrolled")]
        return [MemberEvent(person.person_id, "school_completed")]

    def requirements(self, person: PersonAgent, step: Step) -> dict[NeedKind, Money]:
        """Exigences r_k·P_t de la personne, restreintes à ses besoins actifs (10 §4)."""
        required = self._all_requirements(person, step)
        return {need: r for need, r in required.items() if need in person.needs.active}

    def _all_requirements(self, person: PersonAgent, step: Step) -> dict[NeedKind, Money]:
        return actions.monthly_requirements(
            person.age_years,
            school_enrolled=person.school_status is SchoolStatus.ENROLLED,
            price_index=self.price_index(step),
            requirements=self.economic.consumption_requirements,
        )

    def housing_shares(self, step: Step) -> dict[PersonId, Money]:
        """Parts du coût du logement × P_t selon l'échelle OCDE modifiée (10 §4, §9)."""
        housing = self.economic.housing
        cost = q(Decimal(repr(housing.monthly_cost_household)) * self.price_index(step))
        weights = actions.equivalence_weights(
            {p.person_id: p.age_years for p in self.members},
            self.state.head_id,
            housing.equivalence_weights,
        )
        return actions.housing_shares(cost, weights)

    def initial_spending(self) -> Money:
        """Dépense mensuelle du pas 0 qui tient lieu de ``spend_avg_12m`` : logement +
        Σ (alimentation + soins de routine + frais d'éducation si inscrit), à P_0 (10 §4).

        Calculée une fois, sur le foyer initial, puis conservée.
        """
        if self._reference_spending is not None:
            return self._reference_spending
        total = sum(self.housing_shares(0).values(), Decimal(0))
        for person in self.members:  # « r_edu si inscrit » : sans filtre par besoin actif
            total += sum(self._all_requirements(person, 0).values(), Decimal(0))
        self._reference_spending = total
        return total

    def savings_target(self) -> Money:
        """Cible d'épargne du foyer : ``target_buffer_months × dépense de référence``.

        La dépense de référence est la dépense initiale (10 §4) ; la moyenne glissante sur
        12 mois des consommations privées la remplace avec T-011.
        """
        months = Decimal(repr(self.rules.savings.target_buffer_months))
        return q(months * self.initial_spending())

    def security_level(self) -> float | None:
        """Niveau courant du besoin SECURITY, commun au foyer (None si aucun membre ne l'a)."""
        for person in self.members:
            if NeedKind.SECURITY in person.needs.level:
                return person.needs.level[NeedKind.SECURITY]
        return None

    def init_security_level(self) -> None:
        """Niveau initial du besoin SECURITY = ``sat_security,0`` (10 §4), commun au foyer."""
        sat = actions.security_satisfaction(
            self.ledger.balance(self.account(AccountKind.HOUSEHOLD_SAVINGS)),
            self.initial_spending(),
            self.rules.savings.target_buffer_months,
        )
        for person in self.members:
            if NeedKind.SECURITY in person.needs.active:
                person.needs.level[NeedKind.SECURITY] = sat

    def submit(self, demand_set: DemandSet) -> None:
        self.demand_sets[demand_set.person_id] = demand_set

    def run_time2(self, step: Step) -> list[MemberEvent]:
        """Temps 2 (10 §8.1) : emploi et revenus, puis mise en commun, puis arbitrage.

        Livrés par T-007 : étapes 1 (transitions d'emploi, ``LABOR_INCOME``, ``TAX``) et 3c
        (``POOLING``). Transferts publics (2) : T-015 ; intérêts (3), plafond de crédit (4),
        engagements (5) et ``allocate()`` (6–8) : T-010.
        """
        net_income, events = self.pay_labor_income(step)
        self.pool_income(step, net_income)
        self.arbitrate()
        return events

    def pay_labor_income(self, step: Step) -> tuple[dict[PersonId, Money], list[MemberEvent]]:
        """Transitions d'emploi du mois, puis versement du revenu brut et de l'impôt (10 §3).

        Rend le revenu net d'impôt de chaque personne payée et les événements d'emploi.
        """
        economic = self.economic
        w_t = prices.wage_index(step, economic)
        volatility = economic.income_shocks.informal.volatility
        net_income: dict[PersonId, Money] = {}
        events: list[MemberEvent] = []
        for person in self.members:
            econ = person.econ
            can_work = Capability.WORK in person.profile.capabilities
            draw = labor.draw_employment(person.streams["employment"])
            multiplier = labor.income_multiplier(person.streams["income_shocks"], volatility)
            before = econ.employment
            after = labor.next_employment(
                before,
                last_sector=econ.last_sector,
                school_status=person.school_status,
                age_years=person.age_years,
                can_work=can_work,
                params=economic,
                draw=draw,
            )
            events.extend(_employment_events(person.person_id, before, after))
            _update_employment(econ, after)
            if after not in labor.EMPLOYED or not can_work:
                continue
            gross = labor.gross_labor_income(
                wage_monthly=econ.wage_monthly,
                wage_index=w_t,
                labor_supply=econ.labor_supply,
                labor_capacity=person.phys.labor_capacity,
                multiplier=labor.effective_multiplier(after, multiplier),
            )
            tax = labor.labor_tax(gross, after, economic.tax)
            actions.post_labor_income(
                self.ledger, step, self.household_id, person.person_id, gross, tax
            )
            net_income[person.person_id] = gross - tax
        return net_income, events

    def pool_income(self, step: Step, net_income: Mapping[PersonId, Money]) -> None:
        """Mise en commun : ``pooling_rate × (Yl − impôt)`` du portefeuille vers le pot."""
        for person_id, net in net_income.items():
            amount = labor.pooled_amount(net, self.member(person_id).econ.pooling_rate)
            actions.post_pooling(self.ledger, step, self.household_id, person_id, amount)

    def arbitrate(self) -> Mapping[PersonId, Sequence[Allocation]]:
        """Arbitrage des demandes. Squelette : aucune allocation ; ``allocate()`` : T-010."""
        self.allocations = {person_id: () for person_id in self.demand_sets}
        return self.allocations

    # --- caches du Ledger

    def _sync_caches(self, entry: LedgerEntry) -> None:
        if entry.household_id != self.household_id:
            return
        for account in (entry.src, entry.dst):
            balance = self.ledger.balance(account)
            if account.kind is AccountKind.PERSON_WALLET and account.owner is not None:
                self.member(account.owner).econ.wallet_cached = balance
            elif account.kind is AccountKind.HOUSEHOLD_POT:
                self.state.cached_pot = balance
            elif account.kind is AccountKind.HOUSEHOLD_SAVINGS:
                self.state.cached_savings = balance
            elif account.kind is AccountKind.HOUSEHOLD_LOAN:
                self.state.cached_loan = balance


def _employment_events(
    person_id: PersonId, before: EmploymentStatus, after: EmploymentStatus
) -> list[MemberEvent]:
    if before in labor.EMPLOYED and after is EmploymentStatus.UNEMPLOYED:
        return [MemberEvent(person_id, "job_loss", {"sector": before.value})]
    if before is EmploymentStatus.UNEMPLOYED and after in labor.EMPLOYED:
        return [MemberEvent(person_id, "job_found", {"sector": after.value})]
    return []


def _update_employment(econ: EconomicState, status: EmploymentStatus) -> None:
    spell = labor.update_spell(
        status,
        months_employed=econ.months_employed,
        months_unemployed=econ.months_unemployed,
        last_sector=econ.last_sector,
    )
    econ.employment = status
    econ.labor_supply = spell.labor_supply
    econ.months_employed = spell.months_employed
    econ.months_unemployed = spell.months_unemployed
    econ.last_sector = spell.last_sector
