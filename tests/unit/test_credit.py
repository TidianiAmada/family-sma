"""Crédit, intérêts, plafond, échéance (T-010, 10 §8.4–8.5)."""

from decimal import Decimal

from family_abm.economy.credit import credit_limit, minimum_repayment, monthly_interest

D = Decimal


def test_monthly_interest_matches_trace() -> None:
    assert monthly_interest(D("150000.00"), 0.03) == D("369.94")  # 10 §15
    assert monthly_interest(D(0), 0.18) == 0


def test_credit_limit_uses_labor_income_without_history() -> None:
    assert credit_limit(3.0, [], D("370000.00")) == D("1110000.00")  # 10 §15


def test_credit_limit_uses_last_twelve_months() -> None:
    history = [D(1000)] * 5 + [D(100)] * 12
    assert credit_limit(2.0, history, D(10**6)) == D(200)
    assert credit_limit(3.0, [D(100), D(200)], D(0)) == D(450)


def test_minimum_repayment() -> None:
    assert minimum_repayment(0.05, D(10000), D(150)) == D("507.50")
    assert minimum_repayment(0.05, D(0), D(0)) == 0
