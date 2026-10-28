"""``allocate()`` : cas de 10 §8.3 et trace 10 §15 (T-010)."""

from decimal import Decimal

import pytest

from family_abm.agents.allocation import AllocationInput, AllocationResult, allocate, feedback
from family_abm.core.errors import AllocationError, NotInV1Error
from family_abm.core.types import ActionKind, AllocationMode, DemandStatus, NeedKind, Tier
from family_abm.decision.engine import Demand

D = Decimal
P = [f"h0000-p{i}" for i in range(6)]  # père, mère, jeune adulte, adolescent, enfant, bébé
WEIGHTS = dict(zip(P, [1.0, 1.0, 0.8, 0.7, 0.6, 0.6], strict=True))
HOUSING = dict(
    zip(
        P,
        map(D, ["29032.26", "14516.13", "14516.13", "14516.13", "8709.68", "8709.67"]),
        strict=True,
    )
)
FOOD, HEALTH, EDU = NeedKind.FOOD, NeedKind.HEALTH, NeedKind.EDUCATION


def demand(
    person: str,
    key: str,
    amount: str | int,
    tier: Tier,
    *,
    need: NeedKind | None = None,
    divisible: bool = True,
    amount_min: str | int = 0,
    priority: int = 0,
) -> Demand:
    return Demand(
        demand_id=f"0-{person}-{key}",
        person_id=person,
        need=need,
        tier=tier,
        amount_requested=D(amount),
        amount_min=D(amount_min),
        priority=priority,
        divisible=divisible,
        action=ActionKind.CONSUME,
    )


def run(
    demands: list[Demand],
    pot: str | int,
    *,
    savings: str | int = 0,
    debt: str | int = 0,
    limit: str | int = 0,
    housing: dict[str, Decimal] | None = None,
    repayment: str | int = 0,
    mode: AllocationMode = AllocationMode.FIXED_WEIGHTS,
    weights: dict[str, float] | None = None,
    order: tuple[NeedKind, ...] | None = None,
) -> AllocationResult:
    return allocate(
        AllocationInput(
            demands=tuple(demands),
            pot=D(pot),
            savings=D(savings),
            debt=D(debt),
            credit_limit=D(limit),
            housing_shares=housing or {},
            min_repayment=D(repayment),
            weights=weights or WEIGHTS,
            mode=mode,
            priority_order=order,
            borrow_for_tiers=frozenset({Tier.ESSENTIAL}),
        )
    )


def granted(result: AllocationResult) -> dict[str, Decimal]:
    return {a.demand_id: a.granted for a in result.allocations}


def status(result: AllocationResult) -> dict[str, tuple[DemandStatus, str]]:
    return {a.demand_id: (a.status, a.reason) for a in result.allocations}


def trace_demands() -> list[Demand]:
    rows = [  # 10 §15 : FOOD, HEALTH routine, EDUCATION, SECURITY
        (P[0], 35000, 3000, None, 36375),
        (P[1], 35000, 3000, None, 36375),
        (P[2], 35000, 3000, 40000, None),
        (P[3], 30000, 2000, 15000, None),
        (P[4], 22000, 2000, 8000, None),
        (P[5], 15000, 3000, None, None),
    ]
    demands = []
    for person, food, health, edu, saving in rows:
        demands.append(
            demand(person, "food", food, Tier.ESSENTIAL, need=FOOD, amount_min=food // 2)
        )
        demands.append(demand(person, "health", health, Tier.OTHER, need=HEALTH))
        if edu:
            demands.append(
                demand(
                    person,
                    "education",
                    edu,
                    Tier.EDUCATION,
                    need=EDU,
                    divisible=False,
                    amount_min=edu,
                )
            )
        if saving:
            demands.append(demand(person, "security", saving, Tier.SAVING))
    return demands


def test_trace_allocation_at_step_zero() -> None:
    result = run(
        trace_demands(), "371000.00", savings="150369.94", limit="1110000.00", housing=HOUSING
    )
    assert result.housing_paid == HOUSING
    allocated = granted(result)
    assert allocated["0-h0000-p0-security"] == allocated["0-h0000-p1-security"] == D("15000.00")
    assert status(result)["0-h0000-p0-security"] == (DemandStatus.PARTIAL, "rationed")
    others = {k: v for k, v in status(result).items() if not k.endswith("security")}
    assert set(others.values()) == {(DemandStatus.GRANTED, "")}
    assert (result.deposit, result.withdrawal, result.borrowing) == (D(30000), D(0), D(0))
    spent = sum(allocated.values(), D(0)) - result.deposit + sum(HOUSING.values(), D(0))
    assert D("371000.00") - spent - result.deposit == 0  # pot final 0


def test_housing_is_prorated_and_repayment_unpaid_when_short() -> None:
    housing = {P[0]: D(600), P[1]: D(400)}
    result = run([], 500, housing=housing, repayment=100)
    assert result.housing_paid == {P[0]: D(300), P[1]: D(200)}
    assert result.repayment_paid == 0 and result.arrears


def test_partial_repayment_is_arrears() -> None:
    result = run([], 150, housing={P[0]: D(100)}, repayment=80)
    assert result.repayment_paid == D(50) and result.arrears
    assert not run([], 200, housing={P[0]: D(100)}, repayment=80).arrears


def test_commitments_come_before_any_demand() -> None:
    food = demand(P[0], "food", 100, Tier.ESSENTIAL, need=FOOD)
    result = run([food], 100, housing={P[0]: D(100)})
    assert granted(result)[food.demand_id] == 0


def test_essential_borrows_within_margin_only() -> None:
    food = demand(P[0], "food", 1000, Tier.ESSENTIAL, need=FOOD, amount_min=100)
    result = run([food], 200, savings=300, debt=100, limit=400)  # marge = 300
    assert granted(result)[food.demand_id] == D(800)
    assert (result.withdrawal, result.borrowing) == (D(300), D(300))
    assert result.credit_limit_hit


def test_education_and_other_use_savings_but_never_borrow() -> None:
    edu = demand(P[2], "education", 500, Tier.EDUCATION, need=EDU, divisible=False, amount_min=500)
    other = demand(P[0], "health", 300, Tier.OTHER, need=HEALTH)
    result = run([edu, other], 100, savings=450, limit=10**6)
    assert granted(result)[edu.demand_id] == D(500)  # 100 pot + 400 épargne
    assert granted(result)[other.demand_id] == D(50)
    assert result.borrowing == 0 and result.withdrawal == D(450)


def test_saving_uses_the_pot_only() -> None:
    saving = demand(P[0], "security", 1000, Tier.SAVING)
    result = run([saving], 300, savings=10**6, limit=10**6)
    assert result.deposit == D(300) and result.withdrawal == 0 and result.borrowing == 0


def test_indivisibles_by_weight_then_priority() -> None:
    a = demand(P[5], "education", 300, Tier.EDUCATION, divisible=False, amount_min=300)  # w 0,6
    b = demand(P[2], "education", 300, Tier.EDUCATION, divisible=False, amount_min=300)  # w 0,8
    c = demand(P[3], "education", 100, Tier.EDUCATION, divisible=False, amount_min=100)  # w 0,7
    result = run([a, b, c], 450)
    assert granted(result) == {a.demand_id: 0, b.demand_id: D(300), c.demand_id: D(100)}
    assert status(result)[a.demand_id] == (DemandStatus.REFUSED, "budget_exhausted")


def test_below_min_is_refused_and_redistributed() -> None:
    big = demand(P[0], "food", 900, Tier.ESSENTIAL, need=FOOD, amount_min=100)
    small = demand(P[5], "food", 100, Tier.ESSENTIAL, need=FOOD, amount_min=90)
    result = run([big, small], 500)
    # part du bébé = 500 × 0,6·100 / (1·900 + 0,6·100) = 31,25 < 90 ⇒ refusée ; le père a tout
    assert granted(result) == {big.demand_id: D(500), small.demand_id: D(0)}
    assert status(result)[small.demand_id] == (DemandStatus.REFUSED, "below_min")


def test_proportional_shares_are_floored() -> None:
    demands = [demand(P[i], "food", 100, Tier.ESSENTIAL, need=FOOD) for i in (0, 1, 2)]
    result = run(demands, 100, weights=dict.fromkeys(P, 1.0))
    assert set(granted(result).values()) == {D("33.33")}


def test_later_tiers_get_nothing_once_exhausted() -> None:
    food = demand(P[0], "food", 100, Tier.ESSENTIAL, need=FOOD)
    other = demand(P[0], "health", 10, Tier.OTHER, need=HEALTH)
    result = run([food, other], 100)
    assert status(result)[other.demand_id] == (DemandStatus.REFUSED, "budget_exhausted")


def test_unitary_mode_uses_equal_weights_and_owner_priorities() -> None:
    edu_child = demand(
        P[4], "education", 300, Tier.EDUCATION, need=EDU, divisible=False, amount_min=300
    )
    edu_ya = demand(
        P[2], "education", 300, Tier.EDUCATION, need=EDU, divisible=False, amount_min=300
    )
    result = run([edu_child, edu_ya], 300, mode=AllocationMode.UNITARY, order=(FOOD, EDU))
    # poids égaux, même priorité ⇒ départage par demand_id : p2 avant p4
    assert granted(result) == {edu_child.demand_id: 0, edu_ya.demand_id: D(300)}
    foods = [demand(P[i], "food", 100, Tier.ESSENTIAL, need=FOOD) for i in (0, 5)]
    result = run(foods, 100, mode=AllocationMode.UNITARY, order=(FOOD,))
    assert set(granted(result).values()) == {D(50)}


def test_variable_weights_not_in_v1() -> None:
    with pytest.raises(NotInV1Error):
        run([], 0, mode=AllocationMode.VARIABLE_WEIGHTS)


def test_feedback_for_next_perception() -> None:
    food = demand(P[0], "food", 100, Tier.ESSENTIAL, need=FOOD)
    saving = demand(P[0], "security", 50, Tier.SAVING)
    result = run([food, saving], 120)
    past = feedback([food, saving], result.allocations)
    assert past.habitual == {FOOD: D(100), NeedKind.SECURITY: D(50)}
    assert past.grant_ratio == {FOOD: 1.0, NeedKind.SECURITY: 0.4}
    assert past.granted_total == D(120)


def test_capped_shares_are_redistributed() -> None:
    # Revue T-010 : poids 0,9 / 0,1, demandes 100 et 1 000, budget 500. La part exacte de a
    # (≈ 236) dépasse sa demande : a reçoit 100 et b le reste, 400 — rien n'est perdu.
    a = demand(P[0], "food", 100, Tier.ESSENTIAL, need=FOOD)
    b = demand(P[1], "food", 1000, Tier.ESSENTIAL, need=FOOD)
    result = run([a, b], 500, weights={P[0]: 0.9, P[1]: 0.1})
    assert granted(result) == {a.demand_id: D(100), b.demand_id: D(400)}


def test_empty_tier_budget_refuses_for_budget_not_below_min() -> None:
    food = demand(P[0], "food", 100, Tier.ESSENTIAL, need=FOOD, amount_min=50)
    result = run([food], 0)
    assert status(result)[food.demand_id] == (DemandStatus.REFUSED, "budget_exhausted")
    other = demand(P[0], "health", 10, Tier.OTHER, need=HEALTH, amount_min=5)
    result = run([demand(P[0], "food", 100, Tier.ESSENTIAL, need=FOOD), other], 100)
    assert status(result)[other.demand_id] == (DemandStatus.REFUSED, "budget_exhausted")


def test_below_min_removed_one_at_a_time() -> None:
    # Les deux petites demandes sont sous leur minimum au premier tour ; retirer la plus
    # éloignée suffit à sauver l'autre.
    big = demand(P[0], "food", 1000, Tier.ESSENTIAL, need=FOOD, amount_min=0)
    mid = demand(P[1], "food", 200, Tier.ESSENTIAL, need=FOOD, amount_min=150)
    far = demand(P[2], "food", 200, Tier.ESSENTIAL, need=FOOD, amount_min=199)
    # budget 1 000 : parts 142,86 (mid 0,95 de son minimum, far 0,72) ; sans far, mid = 166,66
    result = run([big, mid, far], 1000, weights=dict.fromkeys(P, 1.0))
    assert status(result)[far.demand_id] == (DemandStatus.REFUSED, "below_min")
    assert granted(result)[mid.demand_id] >= D(150)


def test_duplicate_demand_ids_are_refused() -> None:
    food = demand(P[0], "food", 100, Tier.ESSENTIAL, need=FOOD)
    with pytest.raises(AllocationError, match="double"):
        run([food, food], 100)


def test_allocate_does_not_mutate_its_input() -> None:
    demands = tuple(trace_demands())
    shares = dict(HOUSING)
    weights = dict(WEIGHTS)
    inp = AllocationInput(
        demands=demands,
        pot=D(371000),
        savings=D(0),
        debt=D(0),
        credit_limit=D(0),
        housing_shares=shares,
        min_repayment=D(0),
        weights=weights,
        mode=AllocationMode.FIXED_WEIGHTS,
        priority_order=None,
        borrow_for_tiers=frozenset({Tier.ESSENTIAL}),
    )
    first = allocate(inp)
    assert inp.demands == demands and shares == HOUSING and weights == WEIGHTS
    assert allocate(inp) == first


def test_credit_limit_hit_when_borrowing_is_capped() -> None:
    food = demand(P[0], "food", 1000, Tier.ESSENTIAL, need=FOOD)
    assert run([food], 0, limit=500).credit_limit_hit
    assert not run([food], 0, limit=5000).credit_limit_hit
    other = demand(P[0], "health", 1000, Tier.OTHER, need=HEALTH)
    assert not run([other], 0, limit=0).credit_limit_hit  # palier sans emprunt
    assert run([], 0, housing={P[0]: D(100)}, limit=50).credit_limit_hit
