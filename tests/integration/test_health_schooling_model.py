"""Santé, scolarité et exigences dans le modèle (T-008, 10 §4–§6)."""

from decimal import Decimal

from tests.conftest import CONFIG_DIR, ScriptedEngine

from family_abm.config.loader import load_config
from family_abm.core.types import EmploymentStatus, NeedKind, SchoolStatus
from family_abm.decision.engine import Percept
from family_abm.model.family_model import FamilyModel

NO_EPISODES = {"economic_params.health.p_episode_monthly_by_age": [[0, 0.0]]}


def _run(
    overrides: dict[str, object], steps: int, engine: ScriptedEngine | None = None
) -> FamilyModel:
    model = FamilyModel(load_config(CONFIG_DIR, overrides), engine or ScriptedEngine())
    for _ in range(steps):
        model.step()
    return model


def test_baby_enrols_and_young_adult_completes_at_step_60() -> None:
    model = _run(NO_EPISODES, 61)
    household = model.households[0]
    baby, young_adult = household.member("h0000-p5"), household.member("h0000-p2")
    assert baby.school_status is SchoolStatus.ENROLLED
    assert young_adult.school_status is SchoolStatus.COMPLETED
    assert young_adult.econ.employment in {
        EmploymentStatus.UNEMPLOYED,
        EmploymentStatus.EMPLOYED_FORMAL,
        EmploymentStatus.EMPLOYED_INFORMAL,
    }
    school = [(e.step, e.person_id, e.type) for e in model.events if e.type.startswith("school_")]
    assert school == [(60, "h0000-p2", "school_completed"), (60, "h0000-p5", "school_enrolled")]


def test_percept_carries_requirements_and_first_sick_month() -> None:
    percepts: list[Percept] = []

    def record(percept: Percept) -> tuple[()]:
        percepts.append(percept)
        return ()

    always_sick = {"economic_params.health.p_episode_monthly_by_age": [[0, 1.0]]}
    _run(always_sick, 2, ScriptedEngine(record))
    father = [p for p in percepts if p.person_id == "h0000-p0"]
    assert [p.sick_first_month for p in father] == [True, False]
    assert set(father[0].requirements) == {NeedKind.FOOD, NeedKind.HEALTH}
    young_adult = next(p for p in percepts if p.person_id == "h0000-p2")
    assert young_adult.school_enrolled and NeedKind.EDUCATION in young_adult.requirements
    assert young_adult.requirements[NeedKind.EDUCATION] == Decimal("5045.00")


def test_health_events_are_logged_and_care_need_is_set() -> None:
    model = _run({"economic_params.health.p_episode_monthly_by_age": [[0, 1.0]]}, 1)
    episodes = [e for e in model.events if e.type == "health_episode"]
    assert {e.person_id for e in episodes} == {f"h0000-p{i}" for i in range(6)}
    assert all(e.step == 0 and float(e.detail["severity"]) > 0 for e in episodes)
    father = model.households[0].member("h0000-p0")
    assert father.phys.sick and father.phys.care_need == Decimal("40000.00")


def test_health_and_school_are_reproducible() -> None:
    def trace(seed: int) -> list[tuple[int, str | None, str]]:
        model = _run({"seed": seed}, 120)
        return [(e.step, e.person_id, e.type) for e in model.events]

    assert trace(5) == trace(5)
    first = [
        FamilyModel(load_config(CONFIG_DIR, {"seed": seed}), ScriptedEngine())
        .households[0]
        .members[0]
        .streams["health"]
        .random()
        for seed in (5, 6)
    ]
    assert first[0] != first[1]


def test_health_draws_do_not_depend_on_health_state() -> None:
    # Nombres aléatoires communs : même état du flux « health » que la personne soit malade ou non.
    sick = _run({"economic_params.health.p_episode_monthly_by_age": [[0, 1.0]]}, 5)
    healthy = _run(NO_EPISODES, 5)
    for a, b in zip(sick.households[0].members, healthy.households[0].members, strict=True):
        assert a.streams["health"].bit_generator.state == b.streams["health"].bit_generator.state


def test_needs_activated_with_age_get_initial_levels() -> None:
    model = _run(NO_EPISODES, 48)
    household = model.households[0]
    adolescent, baby = household.member("h0000-p3"), household.member("h0000-p5")
    assert NeedKind.SECURITY in adolescent.needs.active  # 15 ans + 36 mois = 18 ans
    assert adolescent.needs.level[NeedKind.SECURITY] == household.security_level()
    assert NeedKind.EDUCATION in baby.needs.active  # 1 an + 48 mois = 5 ans
    assert baby.needs.level[NeedKind.EDUCATION] == 1.0


def test_episode_reduces_labor_income_through_capacity() -> None:
    from family_abm.economy.accounts import FlowCategory

    overrides = {
        "economic_params.wages.father": 250000,
        "economic_params.health.p_episode_monthly_by_age": [[0, 1.0]],
        "economic_params.health.episode_severity": {
            "mean": 0.5,
            "sd": 0.0,
            "min": 0.05,
            "max": 0.9,
        },
        "economic_params.health.health_min_for_work": 0.0,
        "economic_params.income_shocks.formal.p_loss_monthly": 0.0,
    }
    model = _run(overrides, 1)
    father = model.households[0].member("h0000-p0")
    assert father.phys.labor_capacity == 0.5
    paid = [
        e.amount
        for e in model.ledger.entries(0)
        if e.category is FlowCategory.LABOR_INCOME and e.initiator == father.person_id
    ]
    assert paid == [Decimal("125000.00")]
