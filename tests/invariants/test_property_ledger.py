"""Propriétés du Ledger (10 §16, 90 §2.5) : pour toute séquence d'écritures valides,
INV-01 (somme globale des soldes nulle), INV-02 (variation d'un compte interne = entrées −
sorties du pas) et INV-03 (actifs internes ≥ 0, prêt ≤ 0) tiennent.

Les comptes sont amplement approvisionnés au pas −1 et au pas 0 : le seul refus légitime
restant est un remboursement au-delà de la dette. Tout autre refus fait échouer le test,
qui ne peut donc pas passer en n'acceptant presque rien.
"""

from collections import defaultdict
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

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
from family_abm.economy.ledger import Ledger

H = "h0001"
PEOPLE = ("h0001-p0", "h0001-p1")
OWNER = {
    AccountKind.PERSON_WALLET: PEOPLE,
    AccountKind.HOUSEHOLD_POT: (H,),
    AccountKind.HOUSEHOLD_SAVINGS: (H,),
    AccountKind.HOUSEHOLD_LOAN: (H,),
}
CATEGORIES = [c for c in FlowCategory if c is not FlowCategory.OPENING_BALANCE]
FUNDING = q(1_000_000_000)  # ≫ 60 écritures × 500 000 FCFA au plus
ENTRIES_PER_STEP = 5
EXTERNAL = {kind: AccountId(kind, None) for kind in (AccountKind.BANK, AccountKind.EMPLOYER)}


@st.composite
def postings(draw: st.DrawFn) -> tuple[AccountId, AccountId, FlowCategory, Decimal, str]:
    category = draw(st.sampled_from(CATEGORIES))
    src_kind, dst_kind = draw(st.sampled_from(sorted(ALLOWED[category])))
    src = AccountId(src_kind, draw(st.sampled_from(OWNER.get(src_kind, (None,)))))
    dst = AccountId(dst_kind, draw(st.sampled_from(OWNER.get(dst_kind, (None,)))))
    cents = draw(st.integers(min_value=1, max_value=50_000_000))
    return src, dst, category, Decimal(cents).scaleb(-2), draw(st.sampled_from(PEOPLE))


def _funded_ledger() -> Ledger:
    ledger = Ledger()
    bank = EXTERNAL[AccountKind.BANK]
    for kind in (AccountKind.HOUSEHOLD_POT, AccountKind.HOUSEHOLD_SAVINGS):
        ledger.post(
            OPENING_STEP, H, bank, AccountId(kind, H), FUNDING, FlowCategory.OPENING_BALANCE
        )
    for person in PEOPLE:
        ledger.post(
            0,
            H,
            EXTERNAL[AccountKind.EMPLOYER],
            AccountId(AccountKind.PERSON_WALLET, person),
            FUNDING,
            FlowCategory.LABOR_INCOME,
        )
    return ledger


@settings(max_examples=200, deadline=None)
@given(st.lists(postings(), max_size=60))
def test_valid_sequences_satisfy_inv_01_02_03(
    sequence: list[tuple[AccountId, AccountId, FlowCategory, Decimal, str]],
) -> None:
    ledger = _funded_ledger()
    start_of_step = ledger.balances_snapshot()
    for index, (src, dst, category, amount, person) in enumerate(sequence):
        step = 1 + index // ENTRIES_PER_STEP
        try:
            ledger.post(
                step, H, src, dst, q(amount), category, need=NeedKind.FOOD, beneficiary=person
            )
        except LedgerError as exc:
            # Seul refus légitime avec des comptes approvisionnés.
            assert category is FlowCategory.DEBT_REPAYMENT, exc
            assert "dette" in str(exc), exc

        balances = ledger.balances_snapshot()
        # INV-01 : conservation globale.
        assert sum(balances.values(), Decimal(0)) == 0
        # INV-03 : signes des comptes internes.
        for account, balance in balances.items():
            if account.kind is AccountKind.HOUSEHOLD_LOAN:
                assert balance <= 0
            elif is_internal(account.kind):
                assert balance >= 0

        last_of_step = index == len(sequence) - 1 or (index + 1) % ENTRIES_PER_STEP == 0
        if last_of_step:
            # INV-02 : Δ solde = Σ entrées − Σ sorties du pas, pour chaque compte interne.
            flows: defaultdict[AccountId, Decimal] = defaultdict(Decimal)
            for entry in ledger.entries(step, H):
                flows[entry.dst] += entry.amount
                flows[entry.src] -= entry.amount
            for account in set(balances) | set(start_of_step):
                if is_internal(account.kind):
                    delta = balances.get(account, Decimal(0)) - start_of_step.get(
                        account, Decimal(0)
                    )
                    assert delta == flows[account]
            start_of_step = balances
