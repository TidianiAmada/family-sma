"""Indices de prix et de salaire, taux mensuels (T-007, 10 §2)."""

from decimal import Decimal

import pytest
from tests.conftest import CONFIG_DIR

from family_abm.config.loader import load_config
from family_abm.config.schemas import EconomicParams, SimulationConfig
from family_abm.economy.prices import PriceShock, monthly_rate, price_index, wage_index


@pytest.fixture(scope="module")
def economic() -> EconomicParams:
    overrides = {
        "economic_params.prices.inflation_annual": 0.02,
        "economic_params.wage_growth_annual": 0.02,
    }
    config: SimulationConfig = load_config(CONFIG_DIR, overrides)
    return config.economic_params


def test_indices_start_at_one(economic: EconomicParams) -> None:
    assert price_index(0, economic) == 1
    assert wage_index(0, economic) == 1


def test_wage_index_is_revalued_once_a_year(economic: EconomicParams) -> None:
    assert {wage_index(step, economic) for step in range(12)} == {Decimal(1)}
    assert wage_index(12, economic) == Decimal("1.02")
    assert wage_index(23, economic) == Decimal("1.02")
    assert wage_index(24, economic) == Decimal("1.0404")


def test_price_index_grows_monthly(economic: EconomicParams) -> None:
    assert price_index(12, economic) == Decimal("1.02")
    assert 1 < price_index(1, economic) < price_index(6, economic) < Decimal("1.02")
    assert price_index(6, economic) ** 2 == pytest.approx(Decimal("1.02"), abs=Decimal("1e-20"))


def test_price_shock_applies_from_its_step_onwards(economic: EconomicParams) -> None:
    shocks = (PriceShock(step=5, rate=0.10),)
    assert price_index(4, economic, shocks) == price_index(4, economic)
    assert price_index(5, economic, shocks) == price_index(5, economic) * Decimal("1.1")
    assert price_index(30, economic, shocks) == price_index(30, economic) * Decimal("1.1")


def test_monthly_rate_matches_trace() -> None:
    # 10 §15 : r_s,m = 1,03^(1/12) − 1 = 0,0024663
    assert round(monthly_rate(0.03), 7) == Decimal("0.0024663")
    assert (1 + monthly_rate(0.03)) ** 12 == pytest.approx(Decimal("1.03"), abs=Decimal("1e-20"))
    assert monthly_rate(0.0) == 0
