"""``SatisficingEngine`` : règles de choix, impulsivité, demandes et trace (T-009, 10 §7)."""

from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal
from typing import Any

import numpy as np
import pytest
from tests.conftest import make_percept

from family_abm.config.schemas import CognitiveProfile, SimulationConfig
from family_abm.core.types import ActionKind, NeedKind, Tier
from family_abm.decision.engine import DemandSet, EffectiveCognitiveProfile, Percept
from family_abm.decision.satisficing import SatisficingEngine

D = Decimal


@pytest.fixture(scope="module")
def engine(baseline_config: SimulationConfig) -> SatisficingEngine:
    return SatisficingEngine(baseline_config.needs)


@pytest.fixture(scope="module")
def father(baseline_config: SimulationConfig) -> CognitiveProfile:
    return baseline_config.profiles["father"]


def _decide(
    engine: SatisficingEngine,
    base: CognitiveProfile,
    percept: Percept,
    *,
    aspiration: float | None = None,
    seed: int = 0,
    **profile_changes: Any,  # champs de EffectiveCognitiveProfile
) -> DemandSet:
    profile = replace(EffectiveCognitiveProfile.from_profile(base), **profile_changes)
    theta = base.aspiration_init if aspiration is None else aspiration
    levels: Mapping[NeedKind, float] = dict.fromkeys(NeedKind, theta)
    return engine.decide(percept, profile, base, levels, np.random.default_rng(seed))


def test_father_demands_match_trace(engine: SatisficingEngine, father: CognitiveProfile) -> None:
    demands = {d.demand_id: d for d in _decide(engine, father, make_percept()).demands}
    assert {k: (d.amount_requested, d.tier) for k, d in demands.items()} == {
        "0-h0000-p0-food": (D("35000.00"), Tier.ESSENTIAL),
        "0-h0000-p0-health": (D("3000.00"), Tier.OTHER),
        "0-h0000-p0-security": (D("36375.00"), Tier.SAVING),  # ω · 873 000 / 12
    }
    saving = demands["0-h0000-p0-security"]
    assert saving.need is None and saving.action is ActionKind.SAVE and saving.amount_min == 0
    food = demands["0-h0000-p0-food"]
    assert food.amount_min == D("17500.00") and food.divisible and food.priority == 0


def test_reactive_rule_when_one_alternative_and_no_horizon(
    engine: SatisficingEngine, father: CognitiveProfile
) -> None:
    result = _decide(engine, father, make_percept(), max_alternatives=1, planning_horizon=0)
    assert result.trace.rule == "reactive"
    assert len(result.trace.considered) == 1
    assert result.trace.chosen_id == "alt-0"  # premier produit : tout plein


def test_very_low_threshold_accepts_first_alternative(
    engine: SatisficingEngine, father: CognitiveProfile
) -> None:
    result = _decide(engine, father, make_percept(), aspiration=0.0)
    assert result.trace.rule == "first_acceptable"
    assert [e.alternative_id for e in result.trace.considered] == ["alt-0"]
    assert result.trace.considered[0].acceptable


def test_threshold_above_one_falls_back(
    engine: SatisficingEngine, father: CognitiveProfile
) -> None:
    result = _decide(engine, father, make_percept(), aspiration=1.01)
    trace = result.trace
    assert trace.rule == "fallback_top_need"
    assert len(trace.considered) == father.max_alternatives
    assert not any(e.acceptable for e in trace.considered)
    assert all(e.failed_need is NeedKind.FOOD for e in trace.considered)
    best = max(e.projected_levels[NeedKind.FOOD] for e in trace.considered)
    chosen = next(e for e in trace.considered if e.alternative_id == trace.chosen_id)
    assert chosen.projected_levels[NeedKind.FOOD] == best


def test_fallback_on_first_unsatisfiable_need(
    engine: SatisficingEngine, father: CognitiveProfile
) -> None:
    # SECURITY ne peut atteindre 0,99 : repli sur SECURITY parmi les paniers qui satisfont
    # les besoins précédents ; l'épargne la plus forte gagne.
    result = _decide(engine, father, make_percept(), aspiration=0.99, planning_horizon=0)
    chosen = next(e for e in result.trace.considered if e.alternative_id == result.trace.chosen_id)
    assert result.trace.rule == "fallback_top_need"
    considered = result.trace.considered
    assert {e.failed_need for e in considered} <= {NeedKind.HEALTH, NeedKind.SECURITY}
    before = (NeedKind.FOOD, NeedKind.HOUSING, NeedKind.HEALTH)
    pool = [e for e in considered if all(e.projected_levels[k] >= 0.99 for k in before)]
    assert pool and chosen in pool
    assert chosen.projected_levels[NeedKind.SECURITY] == max(
        e.projected_levels[NeedKind.SECURITY] for e in pool
    )


def test_impulsivity_one_checks_only_first_need(
    engine: SatisficingEngine, father: CognitiveProfile
) -> None:
    impulsive = father.model_copy(update={"impulsivity": 1.0})
    result = _decide(engine, impulsive, make_percept(), aspiration=0.99, planning_horizon=0)
    assert result.trace.rule == "first_acceptable"  # FOOD satisfait, SECURITY non vérifié
    assert result.trace.considered[0].projected_levels[NeedKind.SECURITY] < 0.99


def test_impulsivity_uses_one_draw_of_decision_ties(
    engine: SatisficingEngine, father: CognitiveProfile
) -> None:
    rng, reference = np.random.default_rng(9), np.random.default_rng(9)
    profile = EffectiveCognitiveProfile.from_profile(father)
    engine.decide(make_percept(), profile, father, dict.fromkeys(NeedKind, 0.7), rng)
    reference.random()
    assert rng.random() == reference.random()


def test_at_most_max_alternatives_are_evaluated(
    engine: SatisficingEngine, father: CognitiveProfile
) -> None:
    for k in (1, 2, 3, 8):
        result = _decide(engine, father, make_percept(), aspiration=1.01, max_alternatives=k)
        assert len(result.trace.considered) == k


def test_trace_is_complete(engine: SatisficingEngine, father: CognitiveProfile) -> None:
    result = _decide(engine, father, make_percept())
    trace = result.trace
    assert trace.person_id == "h0000-p0" and trace.step == 0
    assert set(trace.aspiration) == {
        NeedKind.FOOD,
        NeedKind.HOUSING,
        NeedKind.HEALTH,
        NeedKind.SECURITY,
        NeedKind.REST,
    }
    assert trace.chosen_id in {e.alternative_id for e in trace.considered}
    assert all(set(e.projected_levels) == set(trace.aspiration) for e in trace.considered)
    assert all(e.description for e in trace.considered)
    assert result.labor_supply == 1.0


def test_unemployed_supplies_no_labor(engine: SatisficingEngine, father: CognitiveProfile) -> None:
    assert _decide(engine, father, make_percept(employed=False)).labor_supply == 0.0


def test_first_sick_month_adds_indivisible_episode_demand(
    engine: SatisficingEngine, father: CognitiveProfile
) -> None:
    percept = make_percept(sick=True, sick_first_month=True, care_need=D("40000.00"))
    demands = {d.demand_id: d for d in _decide(engine, father, percept).demands}
    episode = demands["0-h0000-p0-health_episode"]
    assert (episode.tier, episode.divisible, episode.amount_min) == (
        Tier.ESSENTIAL,
        False,
        D("40000.00"),
    )
    assert episode.need is NeedKind.HEALTH and episode.action is ActionKind.SEEK_CARE
    assert demands["0-h0000-p0-health"].tier is Tier.OTHER


def test_health_score_rewards_episode_care(
    engine: SatisficingEngine, father: CognitiveProfile
) -> None:
    percept = make_percept(sick=True, sick_first_month=True, care_need=D("40000.00"))
    result = _decide(engine, father, percept, aspiration=1.01, planning_horizon=0)
    by_episode = {
        "health_episode 40000.00" in e.description: e.projected_levels[NeedKind.HEALTH]
        for e in result.trace.considered
    }
    assert by_episode[True] > by_episode[False]


def test_empty_attention_gives_empty_valid_demand_set(
    engine: SatisficingEngine, father: CognitiveProfile
) -> None:
    silent = father.model_copy(update={"attended_needs": ()})
    result = _decide(engine, silent, make_percept())
    assert result.demands == () and result.trace.rule == "first_acceptable"


def test_decision_is_deterministic(engine: SatisficingEngine, father: CognitiveProfile) -> None:
    assert _decide(engine, father, make_percept(), seed=3) == _decide(
        engine, father, make_percept(), seed=3
    )


def test_amounts_beyond_envelope_use_past_grant_ratio(
    engine: SatisficingEngine, father: CognitiveProfile
) -> None:
    within = make_percept(envelope=D(10**9), expected_grant_ratio={NeedKind.FOOD: 0.5})
    beyond = make_percept(envelope=D(1), expected_grant_ratio={NeedKind.FOOD: 0.5})
    level = {}
    for name, percept in (("within", within), ("beyond", beyond)):
        result = _decide(engine, father, percept, aspiration=0.0, planning_horizon=0)
        level[name] = result.trace.considered[0].projected_levels[NeedKind.FOOD]
    rho = 0.5  # needs.food.persistence
    assert level["within"] == pytest.approx(1.0)
    assert level["beyond"] == pytest.approx(rho * 1.0 + (1 - rho) * 0.5)


def test_security_with_null_target_is_satisfied(
    engine: SatisficingEngine, father: CognitiveProfile
) -> None:
    percept = make_percept(savings_target=D(0), savings_gap=D(0))
    result = _decide(engine, father, percept, aspiration=0.0)
    assert result.trace.considered[0].projected_levels[NeedKind.SECURITY] == pytest.approx(1.0)
    assert all(d.tier is not Tier.SAVING for d in result.demands)  # écart nul : rien à épargner


def test_non_owner_does_not_save_and_keeps_past_security(
    engine: SatisficingEngine, father: CognitiveProfile
) -> None:
    percept = make_percept(ownership_share=0.0, last_satisfaction={NeedKind.SECURITY: 0.3})
    result = _decide(engine, father, percept, aspiration=0.0, planning_horizon=0)
    assert all(d.tier is not Tier.SAVING for d in result.demands)
    rho = 0.9  # needs.security.persistence
    projected = result.trace.considered[0].projected_levels[NeedKind.SECURITY]
    assert projected == pytest.approx(rho * 1.0 + (1 - rho) * 0.3)


def test_cared_sick_person_projects_full_health(
    engine: SatisficingEngine, father: CognitiveProfile
) -> None:
    percept = make_percept(sick=True, cared=True)
    result = _decide(engine, father, percept, aspiration=0.0, planning_horizon=0)
    assert result.trace.considered[0].projected_levels[NeedKind.HEALTH] == pytest.approx(1.0)


def test_health_without_consume_keeps_past_satisfaction(
    engine: SatisficingEngine, father: CognitiveProfile
) -> None:
    no_consume = father.model_copy(
        update={"capabilities": tuple(c for c in father.capabilities if c.value != "consume")}
    )
    percept = make_percept(last_satisfaction={NeedKind.HEALTH: 0.4})
    result = _decide(engine, no_consume, percept, aspiration=0.0, planning_horizon=0)
    rho = 0.8  # needs.health.persistence
    projected = result.trace.considered[0].projected_levels[NeedKind.HEALTH]
    assert projected == pytest.approx(rho * 1.0 + (1 - rho) * 0.4)


@pytest.mark.parametrize("seed", range(20))
def test_intermediate_impulsivity_shortcut_iff_draw_below(
    engine: SatisficingEngine, father: CognitiveProfile, seed: int
) -> None:
    impulsive = father.model_copy(update={"impulsivity": 0.5})
    shortcut = np.random.default_rng(seed).random() < 0.5
    result = _decide(
        engine, impulsive, make_percept(), aspiration=0.99, planning_horizon=0, seed=seed
    )
    # raccourci : FOOD seul vérifié, le panier plein est accepté ; sinon repli sur SECURITY
    assert (result.trace.rule == "first_acceptable") == shortcut


def test_habit_is_brought_to_current_levels(
    engine: SatisficingEngine, father: CognitiveProfile, baseline_config: SimulationConfig
) -> None:
    from family_abm.decision.alternatives import generate

    habit = {NeedKind.FOOD: D(1000), NeedKind.HEALTH: D(99999), NeedKind.SECURITY: D(10**7)}
    percept = make_percept(habitual=habit, care_need=D("40000.00"))
    profile = EffectiveCognitiveProfile.from_profile(father)
    basket = generate(percept, profile, father, baseline_config.needs)[0]
    assert basket.alternative_id == "habit"
    assert basket.amount(NeedKind.FOOD) == D("17500.00")  # relevé au minimum 0,5·r
    assert basket.amount(NeedKind.HEALTH) == D("3000.00")  # plafonné au plein
    assert basket.amount(NeedKind.SECURITY) == D("36375.00")  # plafonné au plein
    assert basket.amount("health_episode") == D("40000.00")  # dimension nouvelle : plein
    without_security = make_percept(habitual={NeedKind.FOOD: D(35000)})
    basket = generate(without_security, profile, father, baseline_config.needs)[0]
    assert basket.amount(NeedKind.SECURITY) == D("36375.00")  # absente : plein
