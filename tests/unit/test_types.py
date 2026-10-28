"""Tests des types du noyau (02 §2–3)."""

from decimal import Decimal

import pytest

from family_abm.core.types import (
    MONEY_QUANTUM,
    Role,
    Tier,
    make_household_id,
    make_person_id,
    q,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("1.005"), Decimal("1.00")),  # arrondi bancaire
        (Decimal("1.015"), Decimal("1.02")),
        ("2.5", Decimal("2.50")),
        (3, Decimal("3.00")),
        (0.1 + 0.2, Decimal("0.30")),
        (-1.236, Decimal("-1.24")),
    ],
)
def test_q_quantizes_half_even(value: Decimal | str | int | float, expected: Decimal) -> None:
    result = q(value)
    assert result == expected
    assert result.as_tuple().exponent == MONEY_QUANTUM.as_tuple().exponent


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "-inf", "abc"])
def test_q_refuses_non_finite(value: float | str) -> None:
    with pytest.raises(ValueError):
        q(value)


def test_identifiers_format() -> None:
    hid = make_household_id(7)
    assert hid == "h0007"
    assert make_person_id(hid, 3) == "h0007-p3"


def test_identifiers_refuse_negative_index() -> None:
    with pytest.raises(ValueError):
        make_household_id(-1)
    with pytest.raises(ValueError):
        make_person_id("h0001", -1)


def test_tier_order_is_arbitration_order() -> None:
    assert sorted(Tier) == [
        Tier.COMMITMENT,
        Tier.ESSENTIAL,
        Tier.EDUCATION,
        Tier.OTHER,
        Tier.SAVING,
    ]


def test_roles_are_the_six_household_members() -> None:
    assert {r.value for r in Role} == {
        "father",
        "mother",
        "young_adult",
        "adolescent",
        "child",
        "baby",
    }


@pytest.mark.parametrize("value", [True, False, "1e30", 1e30])
def test_q_refuses_bool_and_out_of_precision(value: object) -> None:
    with pytest.raises(ValueError):
        q(value)  # type: ignore[arg-type]
