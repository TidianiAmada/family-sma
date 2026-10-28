"""Travail, emploi, impôt, mise en commun — fonctions pures (T-007, 10 §3)."""

from decimal import Decimal

import numpy as np
import pytest

from family_abm.config.schemas import EconomicParams, SimulationConfig, TaxParams
from family_abm.core.types import EmploymentStatus, SchoolStatus
from family_abm.economy.labor import (
    EmploymentDraw,
    draw_employment,
    effective_multiplier,
    gross_labor_income,
    income_multiplier,
    labor_tax,
    next_employment,
    pooled_amount,
    update_spell,
)

FORMAL = EmploymentStatus.EMPLOYED_FORMAL
INFORMAL = EmploymentStatus.EMPLOYED_INFORMAL
UNEMPLOYED = EmploymentStatus.UNEMPLOYED
STUDENT = EmploymentStatus.STUDENT
INACTIVE = EmploymentStatus.INACTIVE


@pytest.fixture(scope="module")
def economic(baseline_config: SimulationConfig) -> EconomicParams:
    return baseline_config.economic_params


def _next(
    status: EmploymentStatus,
    params: EconomicParams,
    transition: float,
    formal: float = 0.99,
    *,
    last_sector: EmploymentStatus | None = None,
    school: SchoolStatus = SchoolStatus.COMPLETED,
    age: float = 30.0,
    can_work: bool = True,
) -> EmploymentStatus:
    return next_employment(
        status,
        last_sector=last_sector,
        school_status=school,
        age_years=age,
        can_work=can_work,
        params=params,
        draw=EmploymentDraw(transition=transition, formal=formal),
    )


# --- chocs informels


def test_informal_multiplier_has_unit_mean() -> None:
    # 10 §16 : E[m] = 1 sur 10⁵ tirages, tolérance 1 %
    rng = np.random.default_rng(2024)
    draws = [income_multiplier(rng, 0.15) for _ in range(100_000)]
    assert np.mean(draws) == pytest.approx(1.0, rel=0.01)
    assert min(draws) > 0


def test_zero_volatility_gives_one_and_still_draws() -> None:
    rng, reference = np.random.default_rng(7), np.random.default_rng(7)
    assert income_multiplier(rng, 0.0) == 1.0
    reference.standard_normal()
    assert rng.random() == reference.random()


def test_employment_draw_consumes_two_uniforms() -> None:
    rng, reference = np.random.default_rng(3), np.random.default_rng(3)
    draw = draw_employment(rng)
    expected = reference.random(2)
    assert (draw.transition, draw.formal) == (expected[0], expected[1])


# --- transitions


def test_formal_job_is_lost_below_its_probability(economic: EconomicParams) -> None:
    p = economic.income_shocks.formal.p_loss_monthly
    assert _next(FORMAL, economic, p / 2) is UNEMPLOYED
    assert _next(FORMAL, economic, p) is FORMAL


def test_informal_job_is_lost_below_its_probability(economic: EconomicParams) -> None:
    p = economic.income_shocks.informal.p_loss_monthly
    assert _next(INFORMAL, economic, p / 2) is UNEMPLOYED
    assert _next(INFORMAL, economic, p) is INFORMAL


def test_job_search_uses_sector_of_last_job(economic: EconomicParams) -> None:
    p_formal = economic.income_shocks.formal.p_find_monthly
    p_informal = economic.income_shocks.informal.p_find_monthly
    between = (p_formal + p_informal) / 2
    assert p_formal < p_informal
    assert _next(UNEMPLOYED, economic, between, last_sector=FORMAL) is UNEMPLOYED
    assert _next(UNEMPLOYED, economic, between, last_sector=INFORMAL) in {FORMAL, INFORMAL}


def test_never_employed_searches_as_informal(economic: EconomicParams) -> None:
    p_informal = economic.income_shocks.informal.p_find_monthly
    assert _next(UNEMPLOYED, economic, p_informal * 0.99, last_sector=None) is not UNEMPLOYED
    assert _next(UNEMPLOYED, economic, p_informal, last_sector=None) is UNEMPLOYED


def test_job_found_is_formal_with_find_formal_share(economic: EconomicParams) -> None:
    share = economic.income_shocks.find_formal_share
    assert _next(UNEMPLOYED, economic, 0.0, share / 2) is FORMAL
    assert _next(UNEMPLOYED, economic, 0.0, share) is INFORMAL


def test_student_enters_labour_market_after_school(economic: EconomicParams) -> None:
    min_age = economic.employment.min_work_age
    for school in (SchoolStatus.COMPLETED, SchoolStatus.DROPPED_OUT):
        assert _next(STUDENT, economic, 0.0, school=school, age=min_age) is UNEMPLOYED
        assert _next(STUDENT, economic, 0.0, school=school, age=min_age - 0.5) is STUDENT
    assert _next(STUDENT, economic, 0.0, school=SchoolStatus.ENROLLED, age=30) is STUDENT


def test_inactive_becomes_student_at_enrolment(economic: EconomicParams) -> None:
    assert _next(INACTIVE, economic, 0.0, school=SchoolStatus.ENROLLED, age=6) is STUDENT
    assert _next(INACTIVE, economic, 0.0, school=SchoolStatus.NOT_SCHOOL_AGE, age=2) is INACTIVE


# --- revenu, impôt, mise en commun


def test_gross_income_formula() -> None:
    gross = gross_labor_income(
        wage_monthly=Decimal("250000.00"),
        wage_index=Decimal("1.02"),
        labor_supply=1.0,
        labor_capacity=0.5,
        multiplier=1.1,
    )
    assert gross == Decimal("140250.00")


def test_tax_depends_on_sector_and_is_quantized() -> None:
    tax = TaxParams(formal_rate=0.10, informal_rate=0.05)
    assert labor_tax(Decimal("1000.05"), FORMAL, tax) == Decimal("100.00")  # 100,005 → au pair
    assert labor_tax(Decimal("1000.15"), FORMAL, tax) == Decimal("100.02")  # 100,015 → au pair
    assert labor_tax(Decimal("1000.10"), INFORMAL, tax) == Decimal("50.00")  # 50,005 → au pair


def test_person_without_work_capability_never_finds_a_job(economic: EconomicParams) -> None:
    assert _next(UNEMPLOYED, economic, 0.0, 0.0, can_work=False) is UNEMPLOYED
    assert _next(UNEMPLOYED, economic, 0.0, 0.0, can_work=True) is FORMAL


def test_spell_counters_and_labor_supply() -> None:
    spell = update_spell(INFORMAL, months_employed=3, months_unemployed=0, last_sector=FORMAL)
    assert (spell.labor_supply, spell.months_employed, spell.months_unemployed) == (1.0, 4, 0)
    assert spell.last_sector is INFORMAL
    spell = update_spell(UNEMPLOYED, months_employed=4, months_unemployed=2, last_sector=FORMAL)
    assert (spell.labor_supply, spell.months_employed, spell.months_unemployed) == (0.0, 0, 3)
    assert spell.last_sector is FORMAL
    spell = update_spell(STUDENT, months_employed=0, months_unemployed=5, last_sector=None)
    assert (spell.labor_supply, spell.months_unemployed, spell.last_sector) == (0.0, 0, None)


def test_multiplier_applies_to_informal_income_only() -> None:
    assert effective_multiplier(INFORMAL, 1.3) == 1.3
    assert effective_multiplier(FORMAL, 1.3) == 1.0


def test_pooled_amount_is_quantized() -> None:
    assert pooled_amount(Decimal("120000.00"), 0.8) == Decimal("96000.00")
    assert pooled_amount(Decimal("100.01"), 0.5) == Decimal("50.00")  # demi-centime au pair
