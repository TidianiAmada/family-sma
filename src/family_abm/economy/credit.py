"""Dette, intérêts, plafond de crédit, écritures de financement (10 §8.4–8.5).

``debt_t = debt_t−1 + INTEREST_ACCRUED_t + BORROWING_t − DEBT_REPAYMENT_t`` (INV-07) découle
des écritures : la dette est l'opposé du solde du compte ``HOUSEHOLD_LOAN``. Aucune pénalité
en V1 : les intérêts continuent de courir pendant les arriérés.
"""

from collections.abc import Sequence
from decimal import Decimal

from family_abm.core.types import HouseholdId, Money, Step, q
from family_abm.economy.accounts import AccountId, AccountKind, FlowCategory
from family_abm.economy.ledger import Ledger
from family_abm.economy.prices import monthly_rate


def monthly_interest(balance: Money, annual_rate: float) -> Money:
    """Intérêt du mois au taux mensuel équivalent : ``q(solde × ((1 + r)^(1/12) − 1))``."""
    return q(balance * monthly_rate(annual_rate))


def credit_limit(
    limit_months_income: float, income_history: Sequence[Money], current_labor_income: Money
) -> Money:
    """``κ × moyenne(income_total des 12 derniers mois)`` ; sans historique (pas 0), le revenu
    du travail du mois (10 §8.1, étape 4)."""
    recent = list(income_history)[-12:]
    reference = sum(recent, Decimal(0)) / len(recent) if recent else current_labor_income
    return q(Decimal(repr(limit_months_income)) * reference)


def minimum_repayment(share: float, previous_debt: Money, interest: Money) -> Money:
    """Échéance = ``min_repayment_share × (dette_t−1 + intérêts du mois)``."""
    return q(Decimal(repr(share)) * (previous_debt + interest))


def post_interest(
    ledger: Ledger,
    step: Step,
    household_id: HouseholdId,
    asset_income: Money,
    interest_accrued: Money,
) -> None:
    """``ASSET_INCOME`` banque → épargne ; ``INTEREST_ACCRUED`` prêt → banque (dette ↑)."""
    bank = AccountId(AccountKind.BANK, None)
    if asset_income > 0:
        savings = AccountId(AccountKind.HOUSEHOLD_SAVINGS, household_id)
        ledger.post(step, household_id, bank, savings, asset_income, FlowCategory.ASSET_INCOME)
    if interest_accrued > 0:
        loan = AccountId(AccountKind.HOUSEHOLD_LOAN, household_id)
        ledger.post(step, household_id, loan, bank, interest_accrued, FlowCategory.INTEREST_ACCRUED)


def post_financing(
    ledger: Ledger,
    step: Step,
    household_id: HouseholdId,
    *,
    withdrawal: Money,
    borrowing: Money,
    repayment: Money,
    deposit: Money,
) -> None:
    """Écritures de financement du Temps 2, dans l'ordre retrait, emprunt, remboursement,
    dépôt (10 §8.1, étape 7) ; les montants nuls ne sont pas écrits."""
    pot = AccountId(AccountKind.HOUSEHOLD_POT, household_id)
    savings = AccountId(AccountKind.HOUSEHOLD_SAVINGS, household_id)
    loan = AccountId(AccountKind.HOUSEHOLD_LOAN, household_id)
    flows = (
        (savings, pot, withdrawal, FlowCategory.SAVING_WITHDRAWAL),
        (loan, pot, borrowing, FlowCategory.BORROWING),
        (pot, loan, repayment, FlowCategory.DEBT_REPAYMENT),
        (pot, savings, deposit, FlowCategory.SAVING_DEPOSIT),
    )
    for src, dst, amount, category in flows:
        if amount > 0:
            ledger.post(step, household_id, src, dst, amount, category)
