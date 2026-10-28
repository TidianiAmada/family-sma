"""Comptes et catégories de flux du Ledger (02 §8.1, §8.3).

Un compte est identifié par ``AccountId(kind, owner)``. Les comptes internes appartiennent
à une personne (portefeuille) ou au foyer (pot, épargne, prêt) ; les comptes externes n'ont
pas de propriétaire et un solde libre. ``ALLOWED`` encode la table 02 §8.3 : pour chaque
catégorie, les couples (source, destination) admis.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import NamedTuple

from family_abm.core.types import Step


class AccountKind(StrEnum):
    # internes
    PERSON_WALLET = "person_wallet"
    HOUSEHOLD_POT = "household_pot"
    HOUSEHOLD_SAVINGS = "household_savings"
    HOUSEHOLD_LOAN = "household_loan"  # passif : solde ≤ 0, −solde = dette
    # externes
    EMPLOYER = "employer"
    MARKET = "market"
    GOV = "gov"
    BANK = "bank"
    OTHER_HOUSEHOLDS = "other_households"


class AccountId(NamedTuple):
    kind: AccountKind
    owner: str | None  # PersonId, HouseholdId, ou None pour un compte externe


class FlowCategory(StrEnum):
    LABOR_INCOME = "labor_income"
    TAX = "tax"
    PUBLIC_CASH_TRANSFER = "public_cash_transfer"
    PUBLIC_INKIND = "public_inkind"
    POOLING = "pooling"
    ALLOCATION_CASH = "allocation_cash"
    PRIVATE_CONSUMPTION = "private_consumption"
    SAVING_DEPOSIT = "saving_deposit"
    SAVING_WITHDRAWAL = "saving_withdrawal"
    ASSET_INCOME = "asset_income"
    INTEREST_ACCRUED = "interest_accrued"
    BORROWING = "borrowing"
    DEBT_REPAYMENT = "debt_repayment"
    INTER_HOUSEHOLD_TRANSFER = "inter_household_transfer"
    OPENING_BALANCE = "opening_balance"


PERSON_ACCOUNTS = frozenset({AccountKind.PERSON_WALLET})
HOUSEHOLD_ACCOUNTS = frozenset(
    {AccountKind.HOUSEHOLD_POT, AccountKind.HOUSEHOLD_SAVINGS, AccountKind.HOUSEHOLD_LOAN}
)
LIABILITY_ACCOUNTS = frozenset({AccountKind.HOUSEHOLD_LOAN})

OPENING_STEP: Step = -1
"""Pas des écritures d'ouverture, exclues de tout calcul NTA (10 §20.11)."""

CONSUMPTION_CATEGORIES = frozenset({FlowCategory.PRIVATE_CONSUMPTION, FlowCategory.PUBLIC_INKIND})
"""Catégories qui exigent un bénéficiaire membre du foyer (02 §8.3, INV-08)."""
NEED_REQUIRED_CATEGORIES = CONSUMPTION_CATEGORIES
"""Catégories qui exigent un besoin : toute consommation, privée ou publique en nature
(10 §10, INV-08 ; 02 §8.3 ne le précise que pour la consommation privée)."""


def is_internal(kind: AccountKind) -> bool:
    """Vrai pour un compte du foyer ou d'une personne (solde contraint)."""
    return kind in PERSON_ACCOUNTS or kind in HOUSEHOLD_ACCOUNTS


_K = AccountKind
ALLOWED: Mapping[FlowCategory, frozenset[tuple[AccountKind, AccountKind]]] = MappingProxyType(
    {
        FlowCategory.LABOR_INCOME: frozenset({(_K.EMPLOYER, _K.PERSON_WALLET)}),
        FlowCategory.TAX: frozenset({(_K.PERSON_WALLET, _K.GOV)}),
        FlowCategory.PUBLIC_CASH_TRANSFER: frozenset(
            {(_K.GOV, _K.PERSON_WALLET), (_K.GOV, _K.HOUSEHOLD_POT)}
        ),
        FlowCategory.PUBLIC_INKIND: frozenset({(_K.GOV, _K.MARKET)}),
        FlowCategory.POOLING: frozenset({(_K.PERSON_WALLET, _K.HOUSEHOLD_POT)}),
        FlowCategory.ALLOCATION_CASH: frozenset({(_K.HOUSEHOLD_POT, _K.PERSON_WALLET)}),
        FlowCategory.PRIVATE_CONSUMPTION: frozenset(
            {(_K.PERSON_WALLET, _K.MARKET), (_K.HOUSEHOLD_POT, _K.MARKET)}
        ),
        FlowCategory.SAVING_DEPOSIT: frozenset({(_K.HOUSEHOLD_POT, _K.HOUSEHOLD_SAVINGS)}),
        FlowCategory.SAVING_WITHDRAWAL: frozenset({(_K.HOUSEHOLD_SAVINGS, _K.HOUSEHOLD_POT)}),
        FlowCategory.ASSET_INCOME: frozenset({(_K.BANK, _K.HOUSEHOLD_SAVINGS)}),
        FlowCategory.INTEREST_ACCRUED: frozenset({(_K.HOUSEHOLD_LOAN, _K.BANK)}),
        FlowCategory.BORROWING: frozenset({(_K.HOUSEHOLD_LOAN, _K.HOUSEHOLD_POT)}),
        FlowCategory.DEBT_REPAYMENT: frozenset({(_K.HOUSEHOLD_POT, _K.HOUSEHOLD_LOAN)}),
        FlowCategory.INTER_HOUSEHOLD_TRANSFER: frozenset(
            {
                (_K.HOUSEHOLD_POT, _K.OTHER_HOUSEHOLDS),
                (_K.PERSON_WALLET, _K.OTHER_HOUSEHOLDS),
                (_K.OTHER_HOUSEHOLDS, _K.HOUSEHOLD_POT),
                (_K.OTHER_HOUSEHOLDS, _K.PERSON_WALLET),
            }
        ),
        FlowCategory.OPENING_BALANCE: frozenset(
            {
                (_K.BANK, _K.HOUSEHOLD_POT),
                (_K.BANK, _K.HOUSEHOLD_SAVINGS),
                (_K.HOUSEHOLD_LOAN, _K.BANK),
            }
        ),
    }
)
