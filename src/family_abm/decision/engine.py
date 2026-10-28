"""Interface du point de variation polymorphe unique : ``DecisionEngine`` (S1, 02 §1, 10 §7.1).

Ce module ne contient que des types : la perception (``Percept``), les demandes et
allocations échangées entre le Temps 1 et le Temps 2 (02 §5), la trace de décision (02 §7)
et le ``Protocol``. ``SatisficingEngine`` (T-009) en est la seule implémentation livrée ;
le moteur scripté des tests (``tests/conftest.py``) en est la seconde.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from family_abm.config.schemas import CognitiveProfile
from family_abm.core.types import (
    ActionKind,
    DemandStatus,
    Money,
    NeedKind,
    PersonId,
    Step,
    Tier,
)


@dataclass(frozen=True, slots=True)
class EffectiveCognitiveProfile:
    """Profil effectivement utilisé par la décision (02 §6). En V1/V2, copie du profil de
    base sans modulation ; en V3, produit par ``ModulationEngine`` à partir de l'affect."""

    max_alternatives: int
    planning_horizon: int
    aspiration_scale: float
    beta: float
    risk_lambda: float
    intention_commitment: float

    @classmethod
    def from_profile(cls, profile: CognitiveProfile) -> "EffectiveCognitiveProfile":
        """Profil effectif non modulé (``aspiration_scale = 1``, 10 §7.1)."""
        return cls(
            max_alternatives=profile.max_alternatives,
            planning_horizon=profile.planning_horizon,
            aspiration_scale=1.0,
            beta=profile.discounting.beta,
            risk_lambda=profile.risk.lambda_,
            intention_commitment=profile.intention_commitment,
        )


@dataclass(frozen=True, slots=True)
class Percept:
    """Ce que la personne perçoit au Temps 1 (10 §7.1)."""

    step: Step
    person_id: PersonId
    age_years: float
    needs_level: Mapping[NeedKind, float]
    active_needs: frozenset[NeedKind]
    requirements: Mapping[NeedKind, Money]  # r_k(âge)·P_t (épisode de soin inclus si 1er mois)
    amount_min: Mapping[NeedKind, Money]
    expected_grant_ratio: Mapping[
        NeedKind, float
    ]  # ê_k ; V1 : ratio du pas précédent, 1.0 au départ
    envelope: Money | None  # E_i ; None au pas 0
    habitual: Mapping[NeedKind, Money] | None  # panier choisi au pas précédent
    savings_gap: Money  # (cible − épargne) du foyer, ≥ 0
    ownership_share: float  # ω_i
    sick_first_month: bool
    school_enrolled: bool
    # Compléments de 10 §7.1 requis par 10 §7.3–7.5 (décisions J13–J14)
    care_need: Money  # coût du soin d'épisode, > 0 au premier mois seulement
    sick: bool
    cared: bool  # soin d'épisode obtenu
    employed: bool  # offre de travail du DemandSet
    savings: Money  # épargne du foyer (projection SECURITY)
    savings_target: Money  # target_buffer_months × dépense mensuelle de référence
    last_satisfaction: Mapping[NeedKind, float]  # sat du pas précédent (HOUSING, REST…)


@dataclass(frozen=True, slots=True)
class Demand:
    demand_id: str  # f"{step}-{person_id}-{k}"
    person_id: PersonId
    need: NeedKind | None  # None pour SAVING
    tier: Tier
    amount_requested: Money
    amount_min: Money  # en deçà, la demande est inutile
    priority: int  # rang intra-personne (0 = le plus urgent)
    divisible: bool  # False ⇒ tout ou rien
    plan_id: str | None = None  # V2
    action: ActionKind = ActionKind.CONSUME


@dataclass(frozen=True, slots=True)
class AlternativeEval:
    alternative_id: str
    description: str
    projected_levels: Mapping[NeedKind, float]
    acceptable: bool
    failed_need: NeedKind | None  # premier besoin sous le seuil (règle lexicographique)


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    """Trace de décision, consommée par la collecte et l'interface « Vue agent » (02 §7)."""

    person_id: PersonId
    step: Step
    profile_effective: EffectiveCognitiveProfile
    aspiration: Mapping[NeedKind, float]
    considered: tuple[AlternativeEval, ...]  # au plus max_alternatives
    chosen_id: str
    rule: str  # "first_acceptable" | "fallback_top_need" | "reactive" | "plan_step" | "cpt"
    intention_goal: str | None = None
    plan_id: str | None = None
    cpt: Mapping[str, Any] | None = None  # V3


@dataclass(frozen=True, slots=True)
class DemandSet:
    person_id: PersonId
    demands: tuple[Demand, ...]
    labor_supply: float  # offre de travail décidée pour le pas suivant
    trace: DecisionTrace


@dataclass(frozen=True, slots=True)
class Allocation:
    demand_id: str
    granted: Money
    status: DemandStatus
    reason: str  # "budget_exhausted", "tier_cutoff", "below_min", "sphere_not_owner", …


class DecisionEngine(Protocol):
    """Seul point polymorphe du modèle (S1). Ne lit jamais l'affect : reçoit un profil
    effectif déjà modulé (règle 7, contrat C4)."""

    def decide(
        self,
        percept: Percept,
        profile: EffectiveCognitiveProfile,
        base: CognitiveProfile,
        aspiration: Mapping[NeedKind, float],
        rng: np.random.Generator,
    ) -> DemandSet: ...
