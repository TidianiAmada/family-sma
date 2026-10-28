"""``HouseholdAgent`` — le foyer : membres, état, règles, arbitrage (02 §1, §4.6).

Le foyer agit une seule fois par pas, au Temps 2, entre les deux phases des personnes
(01 §4). Il tient ses caches d'état à jour en s'abonnant au ``Ledger`` (seule source de
vérité, règle 4) et dispose de ses propres flux aléatoires (``streams``), dérivés de son indice : il
produit la même trajectoire qu'il soit simulé seul ou dans une population (01 §7).
"""

from collections.abc import Mapping, Sequence

import mesa

from family_abm.agents.person import PersonAgent
from family_abm.agents.states import HouseholdState
from family_abm.config.schemas import HouseholdRules
from family_abm.core.rng import RngStreams
from family_abm.core.types import HouseholdId, PersonId
from family_abm.decision.engine import Allocation, DemandSet
from family_abm.economy.accounts import AccountId, AccountKind
from family_abm.economy.ledger import Ledger, LedgerEntry


class HouseholdAgent(mesa.Agent):
    """Un foyer : collecte les demandes du Temps 1 et rend les allocations du Temps 2."""

    def __init__(
        self,
        model: mesa.Model,
        *,
        household_id: HouseholdId,
        index: int,
        rules: HouseholdRules,
        state: HouseholdState,
        streams: RngStreams,
        ledger: Ledger,
    ) -> None:
        super().__init__(model)
        self.household_id = household_id
        self.index = index
        self.rules = rules
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

    def arbitrate(self) -> Mapping[PersonId, Sequence[Allocation]]:
        """Temps 2. Squelette T-006 : aucune allocation. Revenus, mise en commun, engagements
        et ``allocate()`` sont livrés par T-007 et T-010."""
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
