"""``HouseholdAgent`` — le foyer : membres, état, règles, arbitrage (02 §1, §4.6).

Le foyer agit une seule fois par pas, au Temps 2, entre les deux phases des personnes
(01 §4). Il tient ses caches d'état à jour en s'abonnant au ``Ledger`` (seule source de
vérité, règle 4) et dispose de ses propres flux aléatoires (``streams``), dérivés de son indice : il
produit la même trajectoire qu'il soit simulé seul ou dans une population (01 §7).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
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
    PersonId,
    Step,
)
from family_abm.decision.engine import Allocation, DemandSet
from family_abm.economy import actions, labor, prices
from family_abm.economy.accounts import AccountId, AccountKind
from family_abm.economy.ledger import Ledger, LedgerEntry


@dataclass(frozen=True, slots=True)
class MemberEvent:
    """Événement endogène d'un membre, inscrit au journal du modèle par l'ordonnanceur.

    Distinct de ``model.events.ModelEvent`` : ``agents`` ne peut pas importer ``model``
    (couches, 01 §3) ; l'ordonnanceur complète le pas et le foyer.
    """

    person_id: PersonId
    type: Literal["job_loss", "job_found"]  # types endogènes de 04 §2.7
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
