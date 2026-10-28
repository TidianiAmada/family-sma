"""Écritures du Ledger produites par les actions des agents (10 §3, §9).

T-007 : versement du revenu du travail (``LABOR_INCOME`` → ``TAX``) et mise en commun
(``POOLING``). Un montant nul ne produit aucune écriture (le Ledger refuse tout montant
≤ 0). Les écritures de consommation du Temps 3 sont livrées par T-011.
"""

from family_abm.core.types import HouseholdId, Money, PersonId, Step
from family_abm.economy.accounts import AccountId, AccountKind, FlowCategory
from family_abm.economy.ledger import Ledger


def _wallet(person_id: PersonId) -> AccountId:
    return AccountId(AccountKind.PERSON_WALLET, person_id)


def post_labor_income(
    ledger: Ledger,
    step: Step,
    household_id: HouseholdId,
    person_id: PersonId,
    gross: Money,
    tax: Money,
) -> None:
    """``LABOR_INCOME`` employeur → portefeuille, puis ``TAX`` portefeuille → État."""
    if gross > 0:
        employer = AccountId(AccountKind.EMPLOYER, None)
        ledger.post(
            step,
            household_id,
            employer,
            _wallet(person_id),
            gross,
            FlowCategory.LABOR_INCOME,
            initiator=person_id,
        )
    if tax > 0:
        gov = AccountId(AccountKind.GOV, None)
        ledger.post(
            step,
            household_id,
            _wallet(person_id),
            gov,
            tax,
            FlowCategory.TAX,
            initiator=person_id,
        )


def post_pooling(
    ledger: Ledger, step: Step, household_id: HouseholdId, person_id: PersonId, amount: Money
) -> None:
    """``POOLING`` portefeuille → pot commun du foyer."""
    if amount > 0:
        pot = AccountId(AccountKind.HOUSEHOLD_POT, household_id)
        ledger.post(
            step,
            household_id,
            _wallet(person_id),
            pot,
            amount,
            FlowCategory.POOLING,
            initiator=person_id,
        )
