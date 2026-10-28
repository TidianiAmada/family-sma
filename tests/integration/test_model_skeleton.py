"""Squelette du modèle à trois temps (T-006, 01 §4, 10 §2, §13)."""

from decimal import Decimal

from tests.conftest import CONFIG_DIR, ScriptedEngine

from family_abm.config.loader import load_config
from family_abm.config.schemas import SimulationConfig
from family_abm.core.types import HouseholdId, NeedKind, Role, SchoolStatus, Step
from family_abm.economy.accounts import OPENING_STEP, AccountId, AccountKind, FlowCategory
from family_abm.model.family_model import FamilyModel
from family_abm.model.scheduler import Phase

HORIZON = 240
STEP_ORDER = [Phase.EVENTS, Phase.TIME1, Phase.TIME2, Phase.TIME3, Phase.MEASURE, Phase.AGE]


def _run(config: SimulationConfig, engine: ScriptedEngine | None = None) -> FamilyModel:
    model = FamilyModel(config, engine or ScriptedEngine())
    model.run()
    return model


def test_240_step_run_with_scripted_engine(baseline_config: SimulationConfig) -> None:
    engine = ScriptedEngine()
    model = _run(baseline_config, engine)
    assert model.step_index == HORIZON
    assert len(engine.calls) == HORIZON * 6
    assert {step for step, _ in engine.calls} == set(range(HORIZON))


def test_three_times_order_is_traced(baseline_config: SimulationConfig) -> None:
    trace: list[tuple[Step, Phase, HouseholdId | None]] = []
    model = FamilyModel(baseline_config, ScriptedEngine(), on_phase=lambda *e: trace.append(e))
    model.run()
    phases_by_step: dict[Step, list[Phase]] = {}
    for step, phase, _ in trace:
        phases_by_step.setdefault(step, []).append(phase)
    assert list(phases_by_step) == list(range(HORIZON))
    assert all(phases == STEP_ORDER for phases in phases_by_step.values())
    households = {hid for _, phase, hid in trace if phase is Phase.TIME2}
    assert households == {model.households[0].household_id}


def test_decisions_happen_in_time1_before_household_arbitration(
    baseline_config: SimulationConfig,
) -> None:
    log: list[str] = []
    engine = ScriptedEngine()
    original = engine.decide

    def decide(*args, **kwargs):  # type: ignore[no-untyped-def]
        log.append("decide")
        return original(*args, **kwargs)

    engine.decide = decide  # type: ignore[method-assign]
    model = FamilyModel(baseline_config, engine, on_phase=lambda s, p, h: log.append(p.value))
    model.step()
    assert log == ["events", "time1", *["decide"] * 6, "time2", "time3", "measure", "age"]


def test_person_order_in_time1_is_seeded(baseline_config: SimulationConfig) -> None:
    first, second = ScriptedEngine(), ScriptedEngine()
    _run(baseline_config, first)
    _run(baseline_config, second)
    assert first.calls == second.calls
    orders = {tuple(p for s, p in first.calls if s == step) for step in range(HORIZON)}
    assert len(orders) > 1  # l'ordre est bien tiré, pas fixe


# --- initialisation


def test_initial_household(baseline_config: SimulationConfig) -> None:
    model = FamilyModel(baseline_config, ScriptedEngine())
    (household,) = model.households
    assert [p.role for p in household.members] == list(Role)
    assert [p.age_months for p in household.members] == [540, 480, 240, 180, 108, 12]
    statuses = [p.school_status for p in household.members]
    assert statuses == [
        SchoolStatus.COMPLETED,
        SchoolStatus.COMPLETED,
        SchoolStatus.ENROLLED,
        SchoolStatus.ENROLLED,
        SchoolStatus.ENROLLED,
        SchoolStatus.NOT_SCHOOL_AGE,
    ]
    assert abs(sum(household.state.weights.values()) - 1) < 1e-12
    assert sum(household.state.ownership.values()) == 1
    assert household.state.head_id == household.members[0].person_id


def test_opening_balances_posted_at_step_minus_one(baseline_config: SimulationConfig) -> None:
    model = FamilyModel(baseline_config, ScriptedEngine())
    (household,) = model.households
    openings = model.ledger.entries(OPENING_STEP)
    assert {e.category for e in openings} == {FlowCategory.OPENING_BALANCE}
    assert household.state.cached_pot == Decimal("50000.00")
    assert household.state.cached_savings == Decimal("150000.00")
    pot = AccountId(AccountKind.HOUSEHOLD_POT, household.household_id)
    assert model.ledger.balance(pot) == household.state.cached_pot


def test_needs_active_follow_active_ages(baseline_config: SimulationConfig) -> None:
    model = FamilyModel(baseline_config, ScriptedEngine())
    baby = model.households[0].members[-1]
    assert NeedKind.EDUCATION not in baby.needs.active
    assert NeedKind.SECURITY not in baby.needs.active
    assert set(baby.needs.level) == set(baby.needs.active)


# --- vieillissement et transitions de profil (10 §2)


def test_aging_after_run(baseline_config: SimulationConfig) -> None:
    model = _run(baseline_config)
    ages = [p.age_months for p in model.households[0].members]
    assert ages == [a + HORIZON for a in [540, 480, 240, 180, 108, 12]]


def test_profile_transitions_follow_config(baseline_config: SimulationConfig) -> None:
    model = _run(baseline_config)
    transitions = [
        (e.step, e.person_id, e.detail["from"], e.detail["to"])
        for e in model.events
        if e.type == "profile_transition"
    ]
    hid = model.households[0].household_id
    baby, child, teen = f"{hid}-p5", f"{hid}-p4", f"{hid}-p3"
    # L'âge franchit le seuil à la fin du pas t : age_months = initial + t + 1.
    assert transitions == [
        (35, teen, "adolescent", "young_adult"),  # 180 → 216 mois
        (47, child, "child", "adolescent"),  # 108 → 156 (ordre des membres)
        (47, baby, "baby", "child"),  # 12 → 60
        (107, child, "adolescent", "young_adult"),  # 108 → 216
        (143, baby, "child", "adolescent"),  # 12 → 156
        (203, baby, "adolescent", "young_adult"),  # 12 → 216
    ]
    members = model.households[0].members
    assert [p.profile_key for p in members[3:]] == ["young_adult"] * 3
    assert [p.role for p in members[3:]] == [Role.ADOLESCENT, Role.CHILD, Role.BABY]


def test_transition_resets_aspiration_and_active_needs(baseline_config: SimulationConfig) -> None:
    model = FamilyModel(baseline_config, ScriptedEngine())
    baby = model.households[0].members[-1]
    for _ in range(48):
        model.step()
    assert baby.profile_key == "child"
    child_init = baseline_config.profiles["child"].aspiration_init
    assert set(baby.cog.aspiration.values()) == {child_init}
    assert NeedKind.EDUCATION in baby.needs.active  # 5 ans révolus


def test_transition_ages_come_from_config() -> None:
    config = load_config(CONFIG_DIR, {"household_rules.profile_transitions.0.at_age": 2})
    model = _run(config)
    baby = model.households[0].members[-1].person_id
    first = next(e for e in model.events if e.person_id == baby)
    assert first.step == 11  # 12 → 24 mois


# --- non-régression (revues T-006)


def test_member_streams_do_not_depend_on_time1_order(baseline_config: SimulationConfig) -> None:
    model = FamilyModel(baseline_config, ScriptedEngine())
    members = model.households[0].members
    draws = [m.streams["decision_ties"].random() for m in members]
    assert len(set(draws)) == len(members)
    again = FamilyModel(baseline_config, ScriptedEngine()).households[0].members
    assert [m.streams["decision_ties"].random() for m in reversed(again)] == draws[::-1]
