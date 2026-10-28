"""Besoins : exigences, satisfactions, niveaux lissés, logement (T-008, 10 §4, §15)."""

from decimal import Decimal

import pytest
from tests.conftest import CONFIG_DIR

from family_abm.config.loader import load_config
from family_abm.config.schemas import (
    EquivalenceWeights,
    RestNeed,
    SimulationConfig,
    lookup_by_age,
)
from family_abm.core.errors import AllocationError
from family_abm.core.types import NeedKind
from family_abm.economy.actions import (
    education_satisfaction,
    equivalence_weights,
    health_satisfaction,
    housing_shares,
    monthly_requirements,
    ratio_satisfaction,
    rest_satisfaction,
    security_satisfaction,
    smooth_level,
)

# Valeurs placeholder de 03 reprises par la trace 10 §15 (fixées explicitement, J3).
TRACE = {
    "economic_params.consumption_requirements.education.by_age": [
        [5, 8000],
        [12, 15000],
        [16, 25000],
        [19, 40000],
    ],
    "economic_params.housing.monthly_cost_household": 90000,
}


@pytest.fixture(scope="module")
def trace_config() -> SimulationConfig:
    return load_config(CONFIG_DIR, TRACE)


def test_lookup_by_age_is_piecewise_constant() -> None:
    table = ((5.0, 10.0), (12.0, 20.0))
    assert lookup_by_age(table, 4.99) == 0.0
    assert lookup_by_age(table, 5.0) == 10.0
    assert lookup_by_age(table, 11.9) == 10.0
    assert lookup_by_age(table, 12.0) == 20.0
    assert lookup_by_age(table, 80.0) == 20.0


def test_requirements_match_trace(trace_config: SimulationConfig) -> None:
    requirements = trace_config.economic_params.consumption_requirements

    def r(age: float, enrolled: bool) -> dict[NeedKind, Decimal]:
        return monthly_requirements(
            age, school_enrolled=enrolled, price_index=Decimal(1), requirements=requirements
        )

    assert r(45, False) == {NeedKind.FOOD: Decimal("35000.00"), NeedKind.HEALTH: Decimal("3000.00")}
    assert r(20, True)[NeedKind.EDUCATION] == Decimal("40000.00")
    assert r(15, True) == {
        NeedKind.FOOD: Decimal("30000.00"),
        NeedKind.HEALTH: Decimal("2000.00"),
        NeedKind.EDUCATION: Decimal("15000.00"),
    }
    assert r(1, False) == {NeedKind.FOOD: Decimal("15000.00"), NeedKind.HEALTH: Decimal("3000.00")}


def test_requirements_are_indexed_on_prices(trace_config: SimulationConfig) -> None:
    requirements = trace_config.economic_params.consumption_requirements
    indexed = monthly_requirements(
        45, school_enrolled=False, price_index=Decimal("1.02"), requirements=requirements
    )
    assert indexed[NeedKind.FOOD] == Decimal("35700.00")


def test_smoothed_level() -> None:
    assert smooth_level(1.0, 0.0, 0.5) == 0.5
    assert smooth_level(0.5, 1.0, 0.9) == pytest.approx(0.55)
    assert smooth_level(0.3, 0.3, 0.8) == pytest.approx(0.3)


def test_ratio_satisfaction_is_capped() -> None:
    assert ratio_satisfaction(Decimal("17500"), Decimal("35000")) == 0.5
    assert ratio_satisfaction(Decimal("50000"), Decimal("35000")) == 1.0
    assert ratio_satisfaction(Decimal(0), Decimal(0)) == 1.0


def test_health_satisfaction() -> None:
    assert (
        health_satisfaction(sick=False, cared=False, routine_ratio=0.5, untreated_factor=0.2) == 0.5
    )
    assert (
        health_satisfaction(sick=True, cared=True, routine_ratio=0.0, untreated_factor=0.2) == 1.0
    )
    assert health_satisfaction(
        sick=True, cared=False, routine_ratio=0.5, untreated_factor=0.2
    ) == pytest.approx(0.1)


def test_education_satisfaction_is_all_or_nothing() -> None:
    assert education_satisfaction(True) == 1.0
    assert education_satisfaction(False) == 0.0


def test_rest_satisfaction(baseline_config: SimulationConfig) -> None:
    rest: RestNeed = baseline_config.needs.rest
    assert rest_satisfaction(0.8, 0.0, rest) == 1.0
    assert rest_satisfaction(1.0, 0.0, rest) == pytest.approx(1 - 0.6 * 0.2)
    assert rest_satisfaction(1.0, 0.95, rest) == 0.0


def test_security_satisfaction_matches_trace() -> None:
    # 10 §15 : cible = 3 × 341 000 ; épargne 150 000
    sat = security_satisfaction(Decimal("150000"), Decimal("341000"), 3)
    assert sat == pytest.approx(150000 / 1023000)
    assert security_satisfaction(Decimal("5000000"), Decimal("341000"), 3) == 1.0
    assert security_satisfaction(Decimal("1"), Decimal(0), 3) == 1.0


def test_housing_shares_match_trace() -> None:
    ages = {f"h0000-p{i}": age for i, age in enumerate([45, 40, 20, 15, 9, 1])}
    weights = equivalence_weights(
        ages,
        "h0000-p0",
        EquivalenceWeights(first_adult=1.0, other_adult=0.5, child=0.3, adult_age=14),
    )
    assert list(weights.values()) == [1.0, 0.5, 0.5, 0.5, 0.3, 0.3]
    shares = housing_shares(Decimal("90000.00"), weights)
    assert list(shares.values()) == [
        Decimal("29032.26"),
        Decimal("14516.13"),
        Decimal("14516.13"),
        Decimal("14516.13"),
        Decimal("8709.68"),
        Decimal("8709.67"),  # résidu au dernier bénéficiaire
    ]
    assert sum(shares.values()) == Decimal("90000.00")


def test_housing_shares_follow_member_order_not_lexical_order() -> None:
    weights = {f"h0000-p{i}": 1.0 for i in range(11)}  # p10 est le dernier membre
    shares = housing_shares(Decimal("100.00"), weights)
    assert list(shares) == list(weights)
    assert shares["h0000-p10"] == Decimal("100.00") - 10 * Decimal("9.09")


@pytest.mark.parametrize("weights", [{}, {"h0000-p0": 0.0}])
def test_housing_shares_refuse_empty_or_null_weights(weights: dict[str, float]) -> None:
    with pytest.raises(AllocationError):
        housing_shares(Decimal("100.00"), weights)


def test_initial_spending_and_security_level_match_trace(trace_config: SimulationConfig) -> None:
    from tests.conftest import ScriptedEngine

    from family_abm.model.family_model import FamilyModel

    model = FamilyModel(trace_config, ScriptedEngine())
    household = model.households[0]
    assert household.initial_spending() == Decimal("341000.00")
    expected = 150000 / (3 * 341000)
    for person in household.members:
        level = person.needs.level.get(NeedKind.SECURITY)
        if NeedKind.SECURITY in person.needs.active:
            assert level == pytest.approx(expected)
        else:
            assert level is None
