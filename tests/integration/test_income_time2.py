"""Revenus du Temps 2 dans le modèle : LABOR_INCOME → TAX → POOLING (T-007, 10 §3, §15)."""

from decimal import Decimal

import pytest
from tests.conftest import CONFIG_DIR, ScriptedEngine

from family_abm.config.loader import load_config
from family_abm.core.types import EmploymentStatus
from family_abm.economy.accounts import AccountId, AccountKind, FlowCategory
from family_abm.model.family_model import FamilyModel

# Trace 10 §15 : valeurs placeholder de 03, fixées explicitement (J3), aucun choc.
TRACE = {
    "economic_params.wages.father": 250000,
    "economic_params.wages.mother": 120000,
    "economic_params.income_shocks.informal.volatility": 0.0,
    "economic_params.income_shocks.formal.p_loss_monthly": 0.0,
    "economic_params.income_shocks.informal.p_loss_monthly": 0.0,
    "economic_params.tax.formal_rate": 0.10,
    "economic_params.tax.informal_rate": 0.0,
}

INCOME_CATEGORIES = {FlowCategory.LABOR_INCOME, FlowCategory.TAX, FlowCategory.POOLING}


def _model(overrides: dict[str, object], seed: int = 42) -> FamilyModel:
    config = load_config(CONFIG_DIR, {**overrides, "seed": seed})
    return FamilyModel(config, ScriptedEngine())


def test_step_zero_income_matches_trace() -> None:
    model = _model(TRACE)
    model.step()
    entries = [e for e in model.ledger.entries(0) if e.category in INCOME_CATEGORIES]
    father, mother = "h0000-p0", "h0000-p1"
    assert [(e.category, e.initiator, e.amount) for e in entries] == [
        (FlowCategory.LABOR_INCOME, father, Decimal("250000.00")),
        (FlowCategory.TAX, father, Decimal("25000.00")),
        (FlowCategory.LABOR_INCOME, mother, Decimal("120000.00")),
        (FlowCategory.POOLING, father, Decimal("225000.00")),
        (FlowCategory.POOLING, mother, Decimal("96000.00")),
    ]
    pot = model.ledger.balance(AccountId(AccountKind.HOUSEHOLD_POT, "h0000"))
    assert pot == Decimal("371000.00")  # 50 000 + 225 000 + 96 000
    assert model.ledger.balance(AccountId(AccountKind.PERSON_WALLET, mother)) == Decimal("24000.00")
    assert model.households[0].member(mother).econ.wallet_cached == Decimal("24000.00")


def test_each_tax_follows_its_labor_income() -> None:
    model = _model({})
    for _ in range(36):
        model.step()
    for step in range(36):
        entries = [e for e in model.ledger.entries(step) if e.category in INCOME_CATEGORIES]
        for previous, entry in zip(entries, entries[1:], strict=False):
            if entry.category is FlowCategory.TAX:
                assert previous.category is FlowCategory.LABOR_INCOME
                assert previous.initiator == entry.initiator
        pooling_seen = False
        for entry in entries:  # toute mise en commun après tous les revenus (10 §8.1)
            pooling_seen |= entry.category is FlowCategory.POOLING
            assert not (pooling_seen and entry.category is FlowCategory.LABOR_INCOME)


def test_formal_labor_income_is_followed_by_its_tax() -> None:
    model = _model({})
    for _ in range(24):
        model.step()
    entries = [e for e in model.ledger.all_entries() if e.category in INCOME_CATEGORIES]
    formal_incomes = [
        (i, e)
        for i, e in enumerate(entries)
        if e.category is FlowCategory.LABOR_INCOME and e.initiator == "h0000-p0"
    ]
    assert formal_incomes
    for i, income in formal_incomes:
        tax = entries[i + 1]
        assert (tax.category, tax.initiator) == (FlowCategory.TAX, income.initiator)
        assert tax.amount == (income.amount * Decimal("0.10")).quantize(Decimal("0.01"))


def _income(model: FamilyModel, person_id: str) -> list[Decimal]:
    return [
        e.amount
        for e in model.ledger.all_entries()
        if e.category is FlowCategory.LABOR_INCOME and e.initiator == person_id
    ]


def test_informal_income_varies_formal_income_does_not() -> None:
    model = _model({**TRACE, "economic_params.income_shocks.informal.volatility": 0.15})
    for _ in range(12):
        model.step()
    assert set(_income(model, "h0000-p0")) == {Decimal("250000.00")}
    assert len(set(_income(model, "h0000-p1"))) == 12


def test_informal_shocks_do_not_depend_on_other_members_trajectory() -> None:
    # Nombres aléatoires communs : la perte d'emploi du père ne change pas les chocs de la mère.
    stable = {**TRACE, "economic_params.income_shocks.informal.volatility": 0.15}
    shaken = {
        **stable,
        "economic_params.income_shocks.formal.p_loss_monthly": 1.0,
        "economic_params.income_shocks.formal.p_find_monthly": 0.0,
    }
    models = [_model(stable), _model(shaken)]
    for model in models:
        for _ in range(24):
            model.step()
    assert _income(models[1], "h0000-p0") == []
    assert _income(models[0], "h0000-p1") == _income(models[1], "h0000-p1")


def test_unemployed_finds_an_informal_job() -> None:
    model = _model(
        {
            **TRACE,
            "economic_params.income_shocks.formal.p_loss_monthly": 1.0,
            "economic_params.income_shocks.formal.p_find_monthly": 1.0,
            "economic_params.income_shocks.find_formal_share": 0.0,
        }
    )
    model.step()
    model.step()
    father = model.households[0].member("h0000-p0")
    assert father.econ.employment is EmploymentStatus.EMPLOYED_INFORMAL
    found = [e for e in model.events if e.type == "job_found"]
    assert [(e.step, e.person_id, e.detail["sector"]) for e in found] == [
        (1, "h0000-p0", "employed_informal")
    ]
    assert not [e for e in model.ledger.entries(1) if e.category is FlowCategory.TAX]


def test_wages_are_revalued_each_year() -> None:
    model = _model({**TRACE, "economic_params.wage_growth_annual": 0.02})
    for _ in range(13):
        model.step()
    father_income = [
        e.amount
        for e in model.ledger.all_entries()
        if e.category is FlowCategory.LABOR_INCOME and e.initiator == "h0000-p0"
    ]
    assert father_income[:12] == [Decimal("250000.00")] * 12
    assert father_income[12] == Decimal("255000.00")


def test_same_seed_same_income_and_events() -> None:
    def trajectory(seed: int) -> tuple[list[object], list[object]]:
        model = _model({}, seed)
        for _ in range(120):
            model.step()
        flows = [(e.step, e.category, e.initiator, e.amount) for e in model.ledger.all_entries()]
        return flows, model.events

    assert trajectory(42) == trajectory(42)
    assert trajectory(42)[0] != trajectory(43)[0]


def test_job_loss_and_job_found_are_logged_endogenously() -> None:
    model = _model(
        {
            "economic_params.income_shocks.formal.p_loss_monthly": 1.0,
            "economic_params.income_shocks.formal.p_find_monthly": 1.0,
            "economic_params.income_shocks.find_formal_share": 1.0,
        }
    )
    model.step()
    model.step()
    father = model.households[0].member("h0000-p0")
    losses = [e for e in model.events if e.type == "job_loss" and e.person_id == father.person_id]
    found = [e for e in model.events if e.type == "job_found" and e.person_id == father.person_id]
    assert [(e.step, e.origin, e.detail["sector"]) for e in losses] == [
        (0, "endogenous", "employed_formal")
    ]
    assert [(e.step, e.detail["sector"]) for e in found] == [(1, "employed_formal")]
    assert father.econ.employment is EmploymentStatus.EMPLOYED_FORMAL
    assert father.econ.months_employed == 1
    no_income_at_0 = [
        e
        for e in model.ledger.entries(0)
        if e.category is FlowCategory.LABOR_INCOME and e.initiator == father.person_id
    ]
    assert no_income_at_0 == []


def test_unemployment_counter_and_labor_supply() -> None:
    model = _model(
        {
            "economic_params.income_shocks.formal.p_loss_monthly": 1.0,
            "economic_params.income_shocks.formal.p_find_monthly": 0.0,
        }
    )
    for _ in range(4):
        model.step()
    father = model.households[0].member("h0000-p0")
    assert father.econ.employment is EmploymentStatus.UNEMPLOYED
    assert father.econ.months_unemployed == 4
    assert father.econ.months_employed == 0
    assert father.econ.labor_supply == 0.0
    assert father.econ.last_sector is EmploymentStatus.EMPLOYED_FORMAL


@pytest.mark.parametrize("capacity", [0.0, 0.5])
def test_labor_capacity_scales_income(capacity: float) -> None:
    model = _model(TRACE)
    father = model.households[0].member("h0000-p0")
    father.phys.labor_capacity = capacity
    model.step()
    paid = [
        e.amount
        for e in model.ledger.entries(0)
        if e.category is FlowCategory.LABOR_INCOME and e.initiator == father.person_id
    ]
    assert paid == ([Decimal("125000.00")] if capacity else [])


def test_member_without_work_capability_earns_nothing() -> None:
    model = _model(
        {
            **TRACE,
            "profiles.father.capabilities": ["consume", "rest"],
        }
    )
    model.step()
    assert not [
        e
        for e in model.ledger.entries(0)
        if e.category is FlowCategory.LABOR_INCOME and e.initiator == "h0000-p0"
    ]
