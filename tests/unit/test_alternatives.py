"""Génération des alternatives (T-009, 10 §7.2–7.3)."""

from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest
from tests.conftest import make_percept

from family_abm.config.schemas import CognitiveProfile, Needs, SimulationConfig
from family_abm.core.types import NeedKind
from family_abm.decision.alternatives import EPISODE, dimensions, generate, level_options
from family_abm.decision.engine import EffectiveCognitiveProfile

D = Decimal


@pytest.fixture(scope="module")
def needs(baseline_config: SimulationConfig) -> Needs:
    return baseline_config.needs


@pytest.fixture(scope="module")
def father(baseline_config: SimulationConfig) -> CognitiveProfile:
    return baseline_config.profiles["father"]


def _profile(base: CognitiveProfile, **changes: Any) -> EffectiveCognitiveProfile:
    return replace(EffectiveCognitiveProfile.from_profile(base), **changes)


def test_demandable_dimensions_follow_attention_and_capabilities(
    needs: Needs, father: CognitiveProfile, baseline_config: SimulationConfig
) -> None:
    # père : [food, housing, health, security, rest] → logement (engagement) et repos exclus
    assert dimensions(make_percept(), father, needs) == [
        NeedKind.FOOD,
        NeedKind.HEALTH,
        NeedKind.SECURITY,
    ]
    assert NeedKind.SECURITY not in dimensions(make_percept(ownership_share=0.0), father, needs)
    sick = make_percept(care_need=D("40000.00"))
    assert dimensions(sick, father, needs)[:3] == [NeedKind.FOOD, NeedKind.HEALTH, EPISODE]
    adolescent = baseline_config.profiles["adolescent"]  # sans « save »
    percept = make_percept(
        requirements={NeedKind.FOOD: D(30000), NeedKind.EDUCATION: D(15000)},
        active_needs=frozenset(NeedKind),
    )
    assert NeedKind.EDUCATION not in dimensions(percept, adolescent, needs)  # non inscrit
    enrolled = replace(percept, school_enrolled=True)
    assert NeedKind.EDUCATION in dimensions(enrolled, adolescent, needs)
    assert NeedKind.SECURITY not in dimensions(enrolled, adolescent, needs)


def test_level_options(needs: Needs) -> None:
    percept = make_percept(care_need=D("40000.00"))
    assert level_options(NeedKind.FOOD, percept, needs) == [D(35000), D(24500), D(17500)]
    assert level_options(NeedKind.HEALTH, percept, needs) == [D(3000), D(2100), D(0)]
    assert level_options(EPISODE, percept, needs) == [D(40000), D(0)]
    assert level_options(NeedKind.SECURITY, percept, needs) == [
        D("36375.00"),  # 0,5 × 873 000 / 12
        D("18187.50"),  # / 24
        D(0),
    ]


def test_full_basket_first_and_truncation(needs: Needs, father: CognitiveProfile) -> None:
    baskets = generate(make_percept(), _profile(father, max_alternatives=4), father, needs)
    assert len(baskets) == 4
    assert baskets[0].amounts == (
        (NeedKind.FOOD, D(35000)),
        (NeedKind.HEALTH, D(3000)),
        (NeedKind.SECURITY, D("36375.00")),
    )
    assert baskets[1].amount(NeedKind.SECURITY) == D("18187.50")  # dernier besoin d'abord


def test_habit_comes_first(needs: Needs, father: CognitiveProfile) -> None:
    habit = {NeedKind.FOOD: D(24500), NeedKind.HEALTH: D(0), NeedKind.SECURITY: D(0)}
    baskets = generate(make_percept(habitual=habit), _profile(father), father, needs)
    assert baskets[0].alternative_id == "habit"
    assert baskets[0].total == D(24500)
    assert len({b.amounts for b in baskets}) == len(baskets)  # sans doublon


def test_envelope_partition_only_when_anticipating(needs: Needs, father: CognitiveProfile) -> None:
    percept = make_percept(envelope=D(40000))
    anticipating = generate(percept, _profile(father, planning_horizon=1), father, needs)
    reactive = generate(percept, _profile(father, planning_horizon=0), father, needs)
    assert anticipating[0].total <= D(40000)
    assert reactive[0].total > D(40000)  # tout plein d'abord, enveloppe ignorée
    totals = [b.total <= D(40000) for b in anticipating]
    assert totals == sorted(totals, reverse=True)  # partition stable
