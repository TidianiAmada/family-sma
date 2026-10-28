"""Tests du Ledger double entrée (02 §8, 10 §10, 10 §16 ``unit/test_ledger.py``)."""

from decimal import Decimal

import pytest

from family_abm.core.errors import LedgerError
from family_abm.core.types import NeedKind, q
from family_abm.economy.accounts import (
    ALLOWED,
    OPENING_STEP,
    AccountId,
    AccountKind,
    FlowCategory,
    is_internal,
)
from family_abm.economy.ledger import Ledger, LedgerEntry

H = "h0001"
FATHER = "h0001-p0"
BABY = "h0001-p5"
WALLET = AccountId(AccountKind.PERSON_WALLET, FATHER)
POT = AccountId(AccountKind.HOUSEHOLD_POT, H)
SAVINGS = AccountId(AccountKind.HOUSEHOLD_SAVINGS, H)
LOAN = AccountId(AccountKind.HOUSEHOLD_LOAN, H)
EMPLOYER = AccountId(AccountKind.EMPLOYER, None)
MARKET = AccountId(AccountKind.MARKET, None)
GOV = AccountId(AccountKind.GOV, None)
BANK = AccountId(AccountKind.BANK, None)
OTHERS = AccountId(AccountKind.OTHER_HOUSEHOLDS, None)


def _funded_ledger() -> Ledger:
    ledger = Ledger()
    ledger.post(OPENING_STEP, H, BANK, POT, q(50000), FlowCategory.OPENING_BALANCE)
    ledger.post(OPENING_STEP, H, BANK, SAVINGS, q(150000), FlowCategory.OPENING_BALANCE)
    ledger.post(0, H, EMPLOYER, WALLET, q(250000), FlowCategory.LABOR_INCOME)
    return ledger


# --- écritures valides


def test_post_moves_value_and_records_entry() -> None:
    ledger = _funded_ledger()
    entry = ledger.post(0, H, WALLET, POT, q(100000), FlowCategory.POOLING, initiator=FATHER)
    assert isinstance(entry, LedgerEntry)
    assert ledger.balance(WALLET) == q(150000)
    assert ledger.balance(POT) == q(150000)
    assert entry.entry_id == 3 and entry.initiator == FATHER


def test_entry_ids_are_sequential() -> None:
    ledger = _funded_ledger()
    assert [e.entry_id for e in ledger.all_entries()] == [0, 1, 2]


def test_global_balance_sum_is_zero() -> None:
    ledger = _funded_ledger()
    ledger.post(0, H, WALLET, GOV, q(25000), FlowCategory.TAX)
    ledger.post(0, H, LOAN, POT, q(30000), FlowCategory.BORROWING)
    ledger.post(
        0,
        H,
        POT,
        MARKET,
        q(20000),
        FlowCategory.PRIVATE_CONSUMPTION,
        need=NeedKind.FOOD,
        beneficiary=BABY,
    )
    assert sum(ledger.balances_snapshot().values(), Decimal(0)) == 0


def test_loan_is_a_liability() -> None:
    ledger = _funded_ledger()
    ledger.post(0, H, LOAN, POT, q(30000), FlowCategory.BORROWING)
    ledger.post(0, H, LOAN, BANK, q(450), FlowCategory.INTEREST_ACCRUED)
    assert ledger.balance(LOAN) == q(-30450)
    ledger.post(0, H, POT, LOAN, q(30450), FlowCategory.DEBT_REPAYMENT)
    assert ledger.balance(LOAN) == 0


def test_entries_by_step_and_household() -> None:
    ledger = _funded_ledger()
    ledger.post(
        1,
        "h0002",
        EMPLOYER,
        AccountId(AccountKind.PERSON_WALLET, "h0002-p0"),
        q(1000),
        FlowCategory.LABOR_INCOME,
    )
    assert len(ledger.entries(OPENING_STEP)) == 2
    assert len(ledger.entries(0, H)) == 1
    assert ledger.entries(1, H) == ()
    assert len(ledger.entries(1)) == 1


def test_unknown_account_balance_is_zero() -> None:
    assert Ledger().balance(POT) == 0


def test_subscribers_receive_each_entry() -> None:
    ledger = Ledger()
    seen: list[LedgerEntry] = []
    ledger.subscribe(seen.append)
    entry = ledger.post(0, H, EMPLOYER, WALLET, q(10), FlowCategory.LABOR_INCOME)
    assert seen == [entry]


def test_inter_household_transfer_both_directions() -> None:
    ledger = _funded_ledger()
    ledger.post(0, H, OTHERS, POT, q(5000), FlowCategory.INTER_HOUSEHOLD_TRANSFER)
    ledger.post(0, H, WALLET, OTHERS, q(5000), FlowCategory.INTER_HOUSEHOLD_TRANSFER)


# --- refus (critères d'acceptation)


@pytest.mark.parametrize("amount", [q(0), q(-1)])
def test_non_positive_amount_is_refused(amount: Decimal) -> None:
    with pytest.raises(LedgerError, match="montant"):
        Ledger().post(0, H, EMPLOYER, WALLET, amount, FlowCategory.LABOR_INCOME)


@pytest.mark.parametrize("amount", [Decimal("1.005"), Decimal("1"), 1.0, 100])
def test_unquantized_or_non_decimal_amount_is_refused(amount: object) -> None:
    with pytest.raises(LedgerError, match="quantifié"):
        Ledger().post(0, H, EMPLOYER, WALLET, amount, FlowCategory.LABOR_INCOME)  # type: ignore[arg-type]


def test_consumption_without_beneficiary_is_refused() -> None:
    with pytest.raises(LedgerError, match="bénéficiaire"):
        _funded_ledger().post(
            0, H, POT, MARKET, q(100), FlowCategory.PRIVATE_CONSUMPTION, need=NeedKind.FOOD
        )


def test_consumption_without_need_is_refused() -> None:
    with pytest.raises(LedgerError, match="besoin"):
        _funded_ledger().post(
            0, H, POT, MARKET, q(100), FlowCategory.PRIVATE_CONSUMPTION, beneficiary=BABY
        )


def test_public_inkind_without_beneficiary_is_refused() -> None:
    with pytest.raises(LedgerError, match="bénéficiaire"):
        Ledger().post(0, H, GOV, MARKET, q(100), FlowCategory.PUBLIC_INKIND)


def test_beneficiary_outside_household_is_refused() -> None:
    with pytest.raises(LedgerError, match="membre"):
        _funded_ledger().post(
            0,
            H,
            POT,
            MARKET,
            q(100),
            FlowCategory.PRIVATE_CONSUMPTION,
            need=NeedKind.FOOD,
            beneficiary="h0002-p1",
        )


@pytest.mark.parametrize(
    ("src", "dst", "category"),
    [
        (POT, MARKET, FlowCategory.SAVING_DEPOSIT),  # dépôt vers le marché
        (MARKET, WALLET, FlowCategory.LABOR_INCOME),  # revenu venant du marché
        (WALLET, POT, FlowCategory.TAX),
        (POT, LOAN, FlowCategory.BORROWING),  # sens inversé
    ],
)
def test_incompatible_account_pair_is_refused(
    src: AccountId, dst: AccountId, category: FlowCategory
) -> None:
    with pytest.raises(LedgerError, match="incompatible"):
        _funded_ledger().post(0, H, src, dst, q(10), category)


def test_overdraft_of_internal_asset_is_refused() -> None:
    ledger = _funded_ledger()
    with pytest.raises(LedgerError, match="découvert"):
        ledger.post(0, H, POT, SAVINGS, q(50000.01), FlowCategory.SAVING_DEPOSIT)
    assert ledger.balance(POT) == q(50000)  # écriture refusée sans effet


def test_repayment_beyond_debt_is_refused() -> None:
    ledger = _funded_ledger()
    ledger.post(0, H, LOAN, POT, q(1000), FlowCategory.BORROWING)
    with pytest.raises(LedgerError, match="dette"):
        ledger.post(0, H, POT, LOAN, q(1000.01), FlowCategory.DEBT_REPAYMENT)


def test_account_of_another_household_is_refused() -> None:
    other_pot = AccountId(AccountKind.HOUSEHOLD_POT, "h0002")
    with pytest.raises(LedgerError, match="foyer"):
        Ledger().post(
            0,
            H,
            EMPLOYER,
            AccountId(AccountKind.PERSON_WALLET, "h0002-p0"),
            q(10),
            FlowCategory.LABOR_INCOME,
        )
    with pytest.raises(LedgerError, match="foyer"):
        Ledger().post(OPENING_STEP, H, BANK, other_pot, q(10), FlowCategory.OPENING_BALANCE)


def test_external_account_with_owner_is_refused() -> None:
    with pytest.raises(LedgerError, match="externe"):
        Ledger().post(
            0, H, AccountId(AccountKind.EMPLOYER, "x"), WALLET, q(10), FlowCategory.LABOR_INCOME
        )


def test_opening_balance_only_at_opening_step() -> None:
    with pytest.raises(LedgerError, match="OPENING_BALANCE"):
        Ledger().post(0, H, BANK, POT, q(10), FlowCategory.OPENING_BALANCE)
    with pytest.raises(LedgerError, match="OPENING_BALANCE"):
        Ledger().post(OPENING_STEP, H, EMPLOYER, WALLET, q(10), FlowCategory.LABOR_INCOME)


def test_refused_entry_leaves_no_trace() -> None:
    ledger = _funded_ledger()
    seen: list[LedgerEntry] = []
    ledger.subscribe(seen.append)
    with pytest.raises(LedgerError):
        ledger.post(0, H, POT, MARKET, q(10), FlowCategory.PRIVATE_CONSUMPTION)
    assert seen == [] and len(ledger.all_entries()) == 3


# --- table des catégories


def test_every_category_has_allowed_pairs() -> None:
    assert set(ALLOWED) == set(FlowCategory)
    assert all(ALLOWED[c] for c in FlowCategory)


def test_internal_accounts() -> None:
    internal = {k for k in AccountKind if is_internal(k)}
    assert internal == {
        AccountKind.PERSON_WALLET,
        AccountKind.HOUSEHOLD_POT,
        AccountKind.HOUSEHOLD_SAVINGS,
        AccountKind.HOUSEHOLD_LOAN,
    }


# --- non-régression (revues T-005)


def test_public_inkind_without_need_is_refused() -> None:
    with pytest.raises(LedgerError, match="besoin"):
        Ledger().post(0, H, GOV, MARKET, q(100), FlowCategory.PUBLIC_INKIND, beneficiary=BABY)


def test_beneficiary_outside_household_refused_for_any_category() -> None:
    with pytest.raises(LedgerError, match="membre"):
        _funded_ledger().post(
            0, H, POT, WALLET, q(10), FlowCategory.ALLOCATION_CASH, beneficiary="h0002-p1"
        )


@pytest.mark.parametrize("step", [-2, True, 1.0])
def test_invalid_step_is_refused(step: object) -> None:
    with pytest.raises(LedgerError, match="pas invalide"):
        Ledger().post(step, H, EMPLOYER, WALLET, q(10), FlowCategory.LABOR_INCOME)  # type: ignore[arg-type]


def test_same_source_and_destination_is_refused() -> None:
    with pytest.raises(LedgerError, match="identiques"):
        _funded_ledger().post(0, H, POT, POT, q(10), FlowCategory.SAVING_DEPOSIT)


@pytest.mark.parametrize("person", ["h0001-p٣", "h00011-p1", "h0001-p"])
def test_malformed_member_ids_are_not_members(person: str) -> None:
    with pytest.raises(LedgerError):
        Ledger().post(
            0,
            H,
            EMPLOYER,
            AccountId(AccountKind.PERSON_WALLET, person),
            q(10),
            FlowCategory.LABOR_INCOME,
        )


def test_failing_subscriber_propagates_after_entry_is_recorded() -> None:
    ledger = _funded_ledger()

    def boom(entry: LedgerEntry) -> None:
        raise RuntimeError("cache")

    ledger.subscribe(boom)
    with pytest.raises(RuntimeError, match="cache"):
        ledger.post(0, H, WALLET, POT, q(10), FlowCategory.POOLING)
    assert len(ledger.all_entries()) == 4  # écriture acquise : le run doit échouer
