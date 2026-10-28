"""Ledger double entrée : source unique de vérité monétaire (S2, 02 §8.2, 10 §10).

Chaque écriture déplace un montant > 0, quantifié au centime, d'un compte source vers un
compte destination : la somme des soldes de tous les comptes, externes compris, reste nulle.
``post`` valide l'écriture **avant** de la journaliser ; une écriture refusée (``LedgerError``)
ne laisse aucune trace. Une écriture acceptée est acquise avant la notification des abonnés :
si un abonné lève, l'exception se propage et le run doit être tenu pour échoué (les caches
d'état divergent du Ledger ; INV-02 le détecterait). Stockage : liste append-only, soldes
courants, index par pas.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from family_abm.core.errors import LedgerError
from family_abm.core.types import MONEY_QUANTUM, HouseholdId, Money, NeedKind, PersonId, Step
from family_abm.economy.accounts import (
    ALLOWED,
    CONSUMPTION_CATEGORIES,
    HOUSEHOLD_ACCOUNTS,
    LIABILITY_ACCOUNTS,
    NEED_REQUIRED_CATEGORIES,
    OPENING_STEP,
    PERSON_ACCOUNTS,
    AccountId,
    FlowCategory,
    is_internal,
)

_ZERO = Decimal(0)
_QUANTUM_EXPONENT = MONEY_QUANTUM.as_tuple().exponent
_MEMBER_INDEX = re.compile(r"[0-9]+")


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """Une écriture : ``amount`` passe de ``src`` à ``dst`` au pas ``step`` (02 §8.2)."""

    entry_id: int  # séquentiel par run
    step: Step
    household_id: HouseholdId
    src: AccountId
    dst: AccountId
    amount: Money  # > 0, toujours
    category: FlowCategory
    need: NeedKind | None = None
    beneficiary: PersonId | None = None  # obligatoire pour toute consommation
    initiator: str = ""  # agent ayant déclenché l'écriture
    ref: str | None = None  # demand_id, plan_id, event_id


def _is_member(person_id: str, household_id: HouseholdId) -> bool:
    # PersonId = "{household_id}-p{index}" (02 §3)
    prefix = f"{household_id}-p"
    return person_id.startswith(prefix) and bool(_MEMBER_INDEX.fullmatch(person_id[len(prefix) :]))


class Ledger:
    """Journal append-only et soldes courants de tous les comptes."""

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []
        self._by_step: dict[Step, list[LedgerEntry]] = {}
        self._balances: dict[AccountId, Money] = {}
        self._subscribers: list[Callable[[LedgerEntry], None]] = []

    # --- écriture

    def post(
        self,
        step: Step,
        household_id: HouseholdId,
        src: AccountId,
        dst: AccountId,
        amount: Money,
        category: FlowCategory,
        *,
        need: NeedKind | None = None,
        beneficiary: PersonId | None = None,
        initiator: str = "",
        ref: str | None = None,
    ) -> LedgerEntry:
        """Valide puis journalise une écriture ; lève ``LedgerError`` si elle est refusée."""
        self._validate(step, household_id, src, dst, amount, category, need, beneficiary)
        entry = LedgerEntry(
            entry_id=len(self._entries),
            step=step,
            household_id=household_id,
            src=src,
            dst=dst,
            amount=amount,
            category=category,
            need=need,
            beneficiary=beneficiary,
            initiator=initiator,
            ref=ref,
        )
        self._entries.append(entry)
        self._by_step.setdefault(step, []).append(entry)
        self._balances[src] = self.balance(src) - amount
        self._balances[dst] = self.balance(dst) + amount
        for callback in self._subscribers:
            callback(entry)
        return entry

    def _validate(
        self,
        step: Step,
        household_id: HouseholdId,
        src: AccountId,
        dst: AccountId,
        amount: Money,
        category: FlowCategory,
        need: NeedKind | None,
        beneficiary: PersonId | None,
    ) -> None:
        context = f"{category} {src} → {dst} au pas {step} (foyer {household_id})"
        if not isinstance(amount, Decimal) or amount.as_tuple().exponent != _QUANTUM_EXPONENT:
            raise LedgerError(f"{context} : montant non quantifié au centime : {amount!r}")
        if amount <= 0:
            raise LedgerError(f"{context} : montant ≤ 0 : {amount}")
        if type(step) is not int or (step < 0 and step != OPENING_STEP):
            raise LedgerError(f"{context} : pas invalide {step!r} (entier ≥ 0, ou {OPENING_STEP})")
        if (category is FlowCategory.OPENING_BALANCE) != (step == OPENING_STEP):
            raise LedgerError(
                f"{context} : OPENING_BALANCE au pas {OPENING_STEP} uniquement, et seulement elle"
            )
        if src == dst:
            raise LedgerError(f"{context} : source et destination identiques")
        if (src.kind, dst.kind) not in ALLOWED[category]:
            raise LedgerError(f"{context} : couple (source, destination) incompatible")
        for account in (src, dst):
            self._check_owner(account, household_id, context)
        if category in CONSUMPTION_CATEGORIES and beneficiary is None:
            raise LedgerError(f"{context} : consommation sans bénéficiaire")
        if beneficiary is not None and not _is_member(beneficiary, household_id):
            raise LedgerError(f"{context} : bénéficiaire {beneficiary} non membre du foyer")
        if category in NEED_REQUIRED_CATEGORIES and need is None:
            raise LedgerError(f"{context} : consommation sans besoin")
        self._check_balances(src, dst, amount, context)

    @staticmethod
    def _check_owner(account: AccountId, household_id: HouseholdId, context: str) -> None:
        if account.kind in PERSON_ACCOUNTS:
            valid = account.owner is not None and _is_member(account.owner, household_id)
        elif account.kind in HOUSEHOLD_ACCOUNTS:
            valid = account.owner == household_id
        else:
            if account.owner is not None:
                raise LedgerError(f"{context} : compte externe avec propriétaire {account}")
            return
        if not valid:
            raise LedgerError(f"{context} : compte {account} hors du foyer {household_id}")

    def _check_balances(self, src: AccountId, dst: AccountId, amount: Money, context: str) -> None:
        # Pas de découvert implicite : l'emprunt est toujours une écriture BORROWING (02 §8.2).
        is_asset = is_internal(src.kind) and src.kind not in LIABILITY_ACCOUNTS
        if is_asset and self.balance(src) < amount:
            raise LedgerError(
                f"{context} : découvert de {src} (solde {self.balance(src)}, débit {amount})"
            )
        # Le prêt est un passif : un crédit (remboursement) ne peut pas dépasser la dette.
        if dst.kind in LIABILITY_ACCOUNTS and self.balance(dst) + amount > 0:
            raise LedgerError(
                f"{context} : remboursement {amount} au-delà de la dette {-self.balance(dst)}"
            )

    # --- lecture

    def balance(self, account: AccountId) -> Money:
        """Solde courant ; 0 pour un compte jamais mouvementé."""
        return self._balances.get(account, _ZERO)

    def entries(self, step: Step, household_id: HouseholdId | None = None) -> Sequence[LedgerEntry]:
        """Écritures d'un pas, éventuellement filtrées par foyer, dans l'ordre de passage."""
        step_entries = self._by_step.get(step, [])
        if household_id is None:
            return tuple(step_entries)
        return tuple(e for e in step_entries if e.household_id == household_id)

    def all_entries(self) -> Sequence[LedgerEntry]:
        """Copie du journal complet (O(n)) : réservé aux tests et à l'export, pas à chaque pas."""
        return tuple(self._entries)

    def balances_snapshot(self) -> dict[AccountId, Money]:
        return dict(self._balances)

    def subscribe(self, callback: Callable[[LedgerEntry], None]) -> None:
        """Abonne ``callback`` à chaque écriture acceptée (mise à jour des caches d'état)."""
        self._subscribers.append(callback)
