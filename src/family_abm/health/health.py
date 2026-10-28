"""Transitions de santé et capacité de travail (10 §5, ODD-V1 §7.4).

Fonction pure appliquée au début du Temps 1 à chaque personne : elle reçoit l'état
physique et rend le nouvel état ; le foyer l'applique (``health`` n'importe pas ``agents``,
01 §3). Chaque personne tire à chaque pas, quel que soit son état, une uniforme puis une
normale dans son flux ``health`` : le nombre de tirages ne dépend pas de la trajectoire
(nombres aléatoires communs entre scénarios, comme pour l'emploi).
"""

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Literal

import numpy as np

from family_abm.config.schemas import AgeTable, HealthParams, lookup_by_age
from family_abm.core.types import Money, q


@dataclass(frozen=True, slots=True)
class HealthState:
    """Champs de ``PhysicalState`` lus et écrits par la transition de santé."""

    health: float
    sick: bool
    cared: bool
    episode_months: int
    health_pre_episode: float
    care_need: Money
    labor_capacity: float


@dataclass(frozen=True, slots=True)
class HealthDraw:
    onset: float  # uniforme [0, 1[ : survenue d'un épisode
    severity: float  # normale N(mean, sd), non bornée


@dataclass(frozen=True, slots=True)
class HealthUpdate:
    state: HealthState
    event: Literal["health_episode", "recovered"] | None = None
    severity: float | None = None  # gravité bornée de l'épisode survenu


def draw_health(rng: np.random.Generator, cfg: HealthParams) -> HealthDraw:
    """Une uniforme puis une normale du flux ``health``, tirées à chaque pas."""
    onset = float(rng.random())
    severity = float(rng.normal(cfg.episode_severity.mean, cfg.episode_severity.sd))
    return HealthDraw(onset=onset, severity=severity)


def labor_capacity(health: float, cfg: HealthParams) -> float:
    """``clip((health − h_min) / (1 − h_min), 0, 1)`` (02 §4.2)."""
    h_min = cfg.health_min_for_work
    return min(1.0, max(0.0, (health - h_min) / (1 - h_min)))


def update_health(
    state: HealthState,
    *,
    age_years: float,
    cfg: HealthParams,
    episode_cost: AgeTable,
    price_index: Decimal,
    draw: HealthDraw,
) -> HealthUpdate:
    """Transition mensuelle (10 §5).

    Hors épisode : un épisode survient avec ``p_episode_monthly_by_age`` ; sa gravité,
    tirée dans N(mean, sd) bornée à [min, max], est retranchée à la santé, et le coût du soin
    ``episode_cost(âge) × P_t`` devient ``care_need`` (demandé une seule fois, au premier
    mois). Sinon, récupération naturelle. En épisode : récupération avec ou sans soin ; fin
    quand la santé revient à ``recovery_tolerance`` du niveau antérieur ou après
    ``max_episode_months``. La capacité de travail suit la santé à chaque pas, y compris
    au pas de survenue ou de guérison (02 §4.2).
    """
    if not state.sick:
        if draw.onset < lookup_by_age(cfg.p_episode_monthly_by_age, age_years):
            bounds = cfg.episode_severity
            severity = min(bounds.max, max(bounds.min, draw.severity))
            health = max(0.0, state.health - severity)
            cost = q(Decimal(repr(lookup_by_age(episode_cost, age_years))) * price_index)
            new = HealthState(
                health=health,
                sick=True,
                cared=False,
                episode_months=0,
                health_pre_episode=state.health,
                care_need=cost,
                labor_capacity=labor_capacity(health, cfg),
            )
            return HealthUpdate(new, "health_episode", severity)
        health = min(1.0, state.health + cfg.natural_recovery)
        return HealthUpdate(
            replace(state, health=health, labor_capacity=labor_capacity(health, cfg))
        )
    months = state.episode_months + 1
    gain = cfg.recovery_with_care if state.cared else cfg.recovery_without_care
    health = min(1.0, state.health + gain)
    recovered = (
        health >= state.health_pre_episode - cfg.recovery_tolerance
        or months >= cfg.max_episode_months
    )
    new = HealthState(
        health=health,
        sick=not recovered,
        cared=state.cared,
        episode_months=months,
        health_pre_episode=state.health_pre_episode,
        care_need=Decimal(0) if recovered else state.care_need,
        labor_capacity=labor_capacity(health, cfg),
    )
    return HealthUpdate(new, "recovered" if recovered else None)
