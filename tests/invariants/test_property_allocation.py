"""Propriétés de ``allocate()`` (10 §8.3, §16 ; 90 §2.5 ; INV-09) — hypothesis, 500 exemples."""

from dataclasses import replace
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from family_abm.agents.allocation import AllocationInput, allocate
from family_abm.core.types import AllocationMode, NeedKind, Tier
from family_abm.decision.engine import Demand

PEOPLE = [f"h0000-p{i}" for i in range(4)]
CENTS = st.integers(min_value=0, max_value=5_000_000).map(lambda c: Decimal(c) / 100)
TIERS = [Tier.ESSENTIAL, Tier.EDUCATION, Tier.OTHER, Tier.SAVING]


@st.composite
def demand_lists(draw: st.DrawFn, divisible_only: bool = False) -> list[Demand]:
    demands = []
    for index in range(draw(st.integers(min_value=0, max_value=10))):
        amount = draw(CENTS.filter(lambda x: x > 0))
        divisible = True if divisible_only else draw(st.booleans())
        floor = draw(st.sampled_from([Decimal(0), amount / 2, amount])) if divisible else amount
        demands.append(
            Demand(
                demand_id=f"0-{PEOPLE[index % len(PEOPLE)]}-{index}",
                person_id=PEOPLE[index % len(PEOPLE)],
                need=NeedKind.FOOD,
                tier=draw(st.sampled_from(TIERS)),
                amount_requested=amount,
                amount_min=floor.quantize(Decimal("0.01")),
                priority=draw(st.integers(min_value=0, max_value=4)),
                divisible=divisible,
            )
        )
    return demands


@st.composite
def inputs(draw: st.DrawFn, divisible_only: bool = False) -> AllocationInput:
    demands = draw(demand_lists(divisible_only))
    debt = draw(CENTS)
    shares = {p: draw(CENTS) for p in draw(st.lists(st.sampled_from(PEOPLE), unique=True))}
    return AllocationInput(
        demands=tuple(demands),
        pot=draw(CENTS),
        savings=draw(CENTS),
        debt=debt,
        credit_limit=draw(CENTS),
        housing_shares=shares,
        min_repayment=draw(CENTS.filter(lambda x: x <= debt)),
        weights={p: draw(st.floats(min_value=0.0, max_value=1.0)) for p in PEOPLE},
        mode=draw(st.sampled_from([AllocationMode.FIXED_WEIGHTS, AllocationMode.UNITARY])),
        priority_order=(NeedKind.FOOD,),
        borrow_for_tiers=frozenset({Tier.ESSENTIAL}),
    )


@settings(max_examples=500, deadline=None)
@given(inputs())
def test_inv09_funding_and_grants(inp: AllocationInput) -> None:
    result = allocate(inp)
    by_id = {d.demand_id: d for d in inp.demands}
    granted = sum((a.granted for a in result.allocations), Decimal(0))
    housing = sum(result.housing_paid.values(), Decimal(0))
    consumption = granted - result.deposit
    uses = consumption + housing + result.repayment_paid + result.deposit
    assert uses <= inp.pot + result.withdrawal + result.borrowing
    assert result.withdrawal <= inp.savings
    assert result.borrowing <= max(Decimal(0), inp.credit_limit - inp.debt)
    for allocation in result.allocations:
        demand = by_id[allocation.demand_id]
        assert 0 <= allocation.granted <= demand.amount_requested
        if not demand.divisible:
            assert allocation.granted in (0, demand.amount_requested)
        if allocation.granted > 0:
            assert allocation.granted >= demand.amount_min
    for person, paid in result.housing_paid.items():
        assert 0 <= paid <= inp.housing_shares[person]


@settings(max_examples=500, deadline=None)
@given(inputs(), st.randoms(use_true_random=False))
def test_order_of_demands_does_not_matter(inp: AllocationInput, rnd) -> None:  # type: ignore[no-untyped-def]
    shuffled = list(inp.demands)
    rnd.shuffle(shuffled)
    permuted = AllocationInput(**{**_fields(inp), "demands": tuple(shuffled)})
    assert allocate(inp) == allocate(permuted)


@settings(max_examples=300, deadline=None)
@given(inputs(divisible_only=True), CENTS)
def test_more_budget_never_lowers_a_divisible_grant(inp: AllocationInput, extra: Decimal) -> None:
    # 90 §2.5 demande la monotonie ; l'algorithme de 10 §8.3 (qui prime) ne la garantit que
    # dans un palier, pour des demandes divisibles sans plancher ni engagement. Sinon un
    # indivisible, une demande qui repasse au-dessus de son minimum, un logement qui devient
    # payable en entier, ou les centimes d'arrondi qu'un palier cesse de laisser au suivant,
    # peuvent réduire une part (contradiction signalée, décision J17).
    floorless = tuple(replace(d, amount_min=Decimal(0), tier=Tier.ESSENTIAL) for d in inp.demands)
    inp = AllocationInput(
        **{
            **_fields(inp),
            "demands": floorless,
            "housing_shares": {},
            "min_repayment": Decimal(0),
        }
    )
    richer = AllocationInput(**{**_fields(inp), "pot": inp.pot + extra})
    before = {a.demand_id: a.granted for a in allocate(inp).allocations}
    after = {a.demand_id: a.granted for a in allocate(richer).allocations}
    assert all(after[k] >= before[k] for k in before)


@settings(max_examples=200, deadline=None)
@given(CENTS.filter(lambda x: x > 0), CENTS, st.integers(min_value=2, max_value=4))
def test_equal_weights_and_demands_give_equal_grants(amount: Decimal, pot: Decimal, n: int) -> None:
    demands = tuple(
        Demand(f"0-{p}-food", p, NeedKind.FOOD, Tier.ESSENTIAL, amount, Decimal(0), 0, True)
        for p in PEOPLE[:n]
    )
    inp = AllocationInput(
        demands=demands,
        pot=pot,
        savings=Decimal(0),
        debt=Decimal(0),
        credit_limit=Decimal(0),
        housing_shares={},
        min_repayment=Decimal(0),
        weights=dict.fromkeys(PEOPLE, 0.5),
        mode=AllocationMode.FIXED_WEIGHTS,
        priority_order=None,
        borrow_for_tiers=frozenset({Tier.ESSENTIAL}),
    )
    assert len({a.granted for a in allocate(inp).allocations}) == 1


def _fields(inp: AllocationInput) -> dict[str, object]:
    return {name: getattr(inp, name) for name in AllocationInput.__dataclass_fields__}
