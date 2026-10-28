"""Transitions de santé et capacité de travail (T-008, 10 §5, J5)."""

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from family_abm.config.schemas import HealthParams, SimulationConfig, lookup_by_age
from family_abm.health.health import (
    HealthDraw,
    HealthState,
    HealthUpdate,
    draw_health,
    labor_capacity,
    update_health,
)

ROOT = Path(__file__).resolve().parents[2]
HEALTHY = HealthState(
    health=1.0,
    sick=False,
    cared=False,
    episode_months=0,
    health_pre_episode=1.0,
    care_need=Decimal(0),
    labor_capacity=1.0,
)
EPISODE_COST = ((0.0, 25000.0), (18.0, 40000.0))


@pytest.fixture(scope="module")
def cfg(baseline_config: SimulationConfig) -> HealthParams:
    return baseline_config.economic_params.health


def _update(
    state: HealthState,
    cfg: HealthParams,
    onset: float,
    severity: float = 0.25,
    age: float = 30.0,
    price_index: Decimal = Decimal(1),
) -> HealthUpdate:
    return update_health(
        state,
        age_years=age,
        cfg=cfg,
        episode_cost=EPISODE_COST,
        price_index=price_index,
        draw=HealthDraw(onset=onset, severity=severity),
    )


def test_episode_onset_sets_care_need_once(cfg: HealthParams) -> None:
    p = lookup_by_age(cfg.p_episode_monthly_by_age, 30.0)
    update = _update(HEALTHY, cfg, onset=p / 2, severity=0.25, price_index=Decimal("1.02"))
    state = update.state
    assert update.event == "health_episode" and update.severity == 0.25
    assert state.sick and not state.cared and state.episode_months == 0
    assert state.health == pytest.approx(0.75) and state.health_pre_episode == 1.0
    assert state.care_need == Decimal("40800.00")
    assert state.labor_capacity == pytest.approx(labor_capacity(0.75, cfg))


def test_no_episode_above_probability_natural_recovery(cfg: HealthParams) -> None:
    p = lookup_by_age(cfg.p_episode_monthly_by_age, 30.0)
    update = _update(replace(HEALTHY, health=0.5), cfg, onset=p)
    assert update.event is None and not update.state.sick
    assert update.state.health == pytest.approx(0.5 + cfg.natural_recovery)
    assert _update(HEALTHY, cfg, onset=p).state.health == 1.0  # plafonnée à 1


def test_severity_is_bounded(cfg: HealthParams) -> None:
    bounds = cfg.episode_severity
    assert _update(HEALTHY, cfg, onset=0.0, severity=5.0).severity == bounds.max
    assert _update(HEALTHY, cfg, onset=0.0, severity=-1.0).severity == bounds.min
    deep = _update(replace(HEALTHY, health=0.1), cfg, onset=0.0, severity=5.0)
    assert deep.state.health == 0.0


def test_recovery_depends_on_care(cfg: HealthParams) -> None:
    sick = replace(HEALTHY, health=0.5, sick=True, health_pre_episode=1.0, care_need=Decimal(1))
    cared = _update(replace(sick, cared=True), cfg, onset=0.0).state
    untreated = _update(sick, cfg, onset=0.0).state
    assert cared.health == pytest.approx(0.5 + cfg.recovery_with_care)
    assert untreated.health == pytest.approx(0.5 + cfg.recovery_without_care)
    assert cared.sick and untreated.sick and cared.episode_months == 1


def test_episode_ends_within_tolerance(cfg: HealthParams) -> None:
    near = replace(
        HEALTHY,
        health=1.0 - cfg.recovery_tolerance - cfg.recovery_with_care,
        sick=True,
        cared=True,
        care_need=Decimal(5),
    )
    update = _update(near, cfg, onset=0.0)
    assert update.event == "recovered"
    assert not update.state.sick and update.state.care_need == 0


def test_episode_ends_after_max_months(cfg: HealthParams) -> None:
    long = replace(HEALTHY, health=0.2, sick=True, episode_months=cfg.max_episode_months - 1)
    update = _update(long, cfg, onset=0.0)
    assert update.event == "recovered" and update.state.episode_months == cfg.max_episode_months


def test_labor_capacity_formula(cfg: HealthParams) -> None:
    h_min = cfg.health_min_for_work
    assert labor_capacity(h_min, cfg) == 0.0
    assert labor_capacity(0.0, cfg) == 0.0
    assert labor_capacity(1.0, cfg) == 1.0
    assert labor_capacity((1 + h_min) / 2, cfg) == pytest.approx(0.5)


def test_draw_health_consumes_uniform_then_normal(cfg: HealthParams) -> None:
    rng, reference = np.random.default_rng(11), np.random.default_rng(11)
    draw = draw_health(rng, cfg)
    assert draw.onset == reference.random()
    assert draw.severity == reference.normal(cfg.episode_severity.mean, cfg.episode_severity.sd)


def test_simulated_episode_frequency_is_below_ehcvm_morbidity(cfg: HealthParams) -> None:
    # J5 : la fréquence mensuelle des épisodes simulés, tous âges, ne dépasse pas la part des
    # personnes malades ou blessées sur 30 jours de l'EHCVM 2018/2019 (borne de vraisemblance).
    bound = json.loads(
        (ROOT / "data/processed/targets/ehcvm_morbidity_bound.json").read_text(encoding="utf-8")
    )["share_ill_or_injured_last_30_days"]
    rng = np.random.default_rng(42)
    episodes = months = 0
    for age in (45.0, 40.0, 20.0, 15.0, 9.0, 1.0):  # foyer de référence
        state = HEALTHY
        for _ in range(240):
            update = _update(state, cfg, **_draw_kwargs(draw_health(rng, cfg)), age=age)
            episodes += update.event == "health_episode"
            months += 1
            state = update.state
    assert episodes / months <= bound


def _draw_kwargs(draw: HealthDraw) -> dict[str, float]:
    return {"onset": draw.onset, "severity": draw.severity}
