"""Temps 2 complet dans le modèle : intérêts, plafond, allocation, financement (T-010, 10 §8)."""

from decimal import Decimal

from tests.conftest import CONFIG_DIR, ScriptedEngine

from family_abm.config.loader import load_config
from family_abm.core.types import DemandStatus
from family_abm.decision.satisficing import SatisficingEngine
from family_abm.economy.accounts import AccountId, AccountKind, FlowCategory
from family_abm.model.family_model import FamilyModel

TRACE = {
    "economic_params.wages.father": 250000,
    "economic_params.wages.mother": 120000,
    "economic_params.income_shocks.informal.volatility": 0.0,
    "economic_params.income_shocks.formal.p_loss_monthly": 0.0,
    "economic_params.income_shocks.informal.p_loss_monthly": 0.0,
    "economic_params.health.p_episode_monthly_by_age": [[0, 0.0]],
}
FINANCING = {
    FlowCategory.SAVING_WITHDRAWAL,
    FlowCategory.BORROWING,
    FlowCategory.DEBT_REPAYMENT,
    FlowCategory.SAVING_DEPOSIT,
}


def _model(overrides: dict[str, object], engine: str = "satisficing") -> FamilyModel:
    config = load_config(CONFIG_DIR, overrides)
    chosen = SatisficingEngine(config.needs) if engine == "satisficing" else ScriptedEngine()
    return FamilyModel(config, chosen)


def test_step_zero_interest_and_credit_limit_match_trace() -> None:
    model = _model(TRACE)
    model.step()
    household = model.households[0]
    asset = [e.amount for e in model.ledger.entries(0) if e.category is FlowCategory.ASSET_INCOME]
    assert asset == [Decimal("369.94")]
    assert household.state.credit_limit == Decimal("1110000.00")  # 3 × 370 000
    assert list(household.income_history) == [Decimal("370369.94")]  # Yl + Ya


def test_time2_order_and_financing_after_pooling() -> None:
    model = _model(TRACE)
    model.step()
    categories = [e.category for e in model.ledger.entries(0)]
    last_pooling = max(i for i, c in enumerate(categories) if c is FlowCategory.POOLING)
    asset = categories.index(FlowCategory.ASSET_INCOME)
    assert asset < last_pooling  # intérêts (3) avant la mise en commun (3c)
    assert all(i > last_pooling for i, c in enumerate(categories) if c in FINANCING)


def test_every_demand_receives_an_allocation() -> None:
    model = _model(TRACE)
    model.step()
    household = model.households[0]
    for person_id, demand_set in household.demand_sets.items():
        ids = [a.demand_id for a in household.allocations[person_id]]
        assert ids == sorted(d.demand_id for d in demand_set.demands)


def test_debt_follows_interest_borrowing_and_repayment() -> None:
    # Pot et épargne vides, logement au-delà du revenu mis en commun : le foyer emprunte
    # (engagement, puis essentiel) dans la limite du plafond ; INV-07 vérifiée sur le Ledger.
    short = {
        **TRACE,
        "household_rules.baseline_household.initial_assets": {"pot": 0, "savings": 0, "loan": 0},
        "economic_params.housing.monthly_cost_household": 400000,
    }
    model = _model(short)
    loan = AccountId(AccountKind.HOUSEHOLD_LOAN, "h0000")
    debt = Decimal(0)
    for step in range(12):
        model.step()
        flows = {c: Decimal(0) for c in FlowCategory}
        for entry in model.ledger.entries(step):
            flows[entry.category] += entry.amount
        debt += (
            flows[FlowCategory.INTEREST_ACCRUED]
            + flows[FlowCategory.BORROWING]
            - flows[FlowCategory.DEBT_REPAYMENT]
        )
        assert -model.ledger.balance(loan) == debt
        if step == 0:
            assert flows[FlowCategory.BORROWING] > 0
            assert flows[FlowCategory.BORROWING] <= model.households[0].state.credit_limit
    assert debt > 0


def test_arrears_events_when_repayment_cannot_be_met() -> None:
    broke = {
        **TRACE,
        "household_rules.baseline_household.initial_assets": {
            "pot": 0,
            "savings": 0,
            "loan": 10000,
        },
        "household_rules.credit.limit_months_income": 0.0,
        "economic_params.wages.father": 1,
        "economic_params.wages.mother": 1,
        "economic_params.housing.monthly_cost_household": 1000,
    }
    model = _model(broke, engine="scripted")
    model.step()
    model.step()
    household = model.households[0]
    assert household.state.arrears_months == 2
    types = [(e.step, e.type) for e in model.events if e.person_id is None]
    assert (0, "arrears_start") in types
    assert (1, "arrears_start") not in types


def test_saving_demands_become_deposits() -> None:
    model = _model(TRACE)
    model.step()
    household = model.households[0]
    deposits = sum(
        e.amount for e in model.ledger.entries(0) if e.category is FlowCategory.SAVING_DEPOSIT
    )
    granted_savings = sum(
        a.granted
        for allocations in household.allocations.values()
        for a in allocations
        if a.demand_id.endswith("-security") and a.status is not DemandStatus.REFUSED
    )
    assert deposits == granted_savings


def test_arrears_end_when_repayment_is_met_again() -> None:
    model = _model(
        {
            **TRACE,
            "household_rules.baseline_household.initial_assets": {
                "pot": 0,
                "savings": 0,
                "loan": 10000,
            },
            "household_rules.credit.limit_months_income": 0.0,
            "economic_params.housing.monthly_cost_household": 1000,
        },
        engine="scripted",
    )
    household = model.households[0]
    household.state.arrears_months = 2  # arriérés hérités ; le revenu couvre l'échéance
    model.step()
    assert household.state.arrears_months == 0
    assert [(e.step, e.type) for e in model.events if e.person_id is None] == [(0, "arrears_end")]


def test_unitary_mode_requires_its_decision_maker() -> None:
    import pytest

    from family_abm.core.errors import ConfigError

    model = _model({**TRACE, "household_rules.allocation.mode": "unitary"})
    household = model.households[0]
    del household.member_keys["father"]
    with pytest.raises(ConfigError, match="father"):
        model.step()
