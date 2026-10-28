"""États passifs des agents (02 §4, §6).

Tous les états sont des ``@dataclass(slots=True)`` mutables mais **passifs** : aucune
méthode métier. La logique vit dans ``economy/``, ``health/``, ``cognition/``,
``decision/``. Les champs marqués V2/V3 portent leur valeur neutre en V1. Les champs
``*_cached`` sont des caches du ``Ledger`` (seule source de vérité, règle 4), tenus à jour
par abonnement et vérifiés par invariant (INV-02).
"""

from dataclasses import dataclass, field
from decimal import Decimal

from family_abm.core.types import (
    Emotion,
    EmploymentStatus,
    HouseholdRegime,
    IntentionStatus,
    Money,
    NeedKind,
    PersonId,
    Step,
)

# --- objets cognitifs (V2, 02 §6)


@dataclass(slots=True)
class Belief:
    key: str  # ex. "income_stable", "job_at_risk", "debt_manageable"
    value: float | bool
    confidence: float  # [0, 1]
    updated_step: Step


@dataclass(frozen=True, slots=True)
class Desire:
    goal: str  # ex. "satisfy:food", "repay_debt", "build_buffer"
    priority: float  # plus haut = plus important
    source: str  # "need_deficit" | "long_term" | "plan_subgoal"


@dataclass(slots=True)
class Intention:
    goal: str
    plan_id: str
    step_index: int  # étape courante du corps du plan
    status: IntentionStatus
    adopted_step: Step
    failures: int


# --- états de la personne (02 §4.1–4.5)


@dataclass(slots=True)
class EconomicState:
    employment: EmploymentStatus
    wage_monthly: Money  # salaire mensuel à plein temps
    labor_supply: float  # fraction de temps plein, [0, 1.25]
    pooling_rate: float  # part du revenu versée au pot, [0, 1]
    wallet_cached: Money = Decimal(0)  # cache du Ledger
    spent_by_need: dict[NeedKind, Money] = field(default_factory=dict)  # remis à zéro au Temps 1
    months_unemployed: int = 0
    months_employed: int = 0
    # secteur du dernier emploi (formel ou informel) ; None = jamais employé (10 §3)
    last_sector: EmploymentStatus | None = None
    in_mutuelle: bool = False  # V3
    in_tontine: bool = False  # V3


@dataclass(slots=True)
class PhysicalState:
    health: float  # [0, 1], 1 = pleine santé
    sick: bool = False
    care_need: Money = Decimal(0)
    labor_capacity: float = 1.0  # [0, 1]
    # détails d'implémentation de l'épisode de santé (10 §5), non exportés
    health_pre_episode: float = 1.0
    cared: bool = False  # soin d'épisode obtenu au premier mois
    episode_months: int = 0
    fatigue: float = 0.0  # V2


@dataclass(slots=True)
class NeedsState:
    level: dict[NeedKind, float]  # niveau lissé, [0, 1]
    satisfaction: dict[NeedKind, float]  # satisfaction instantanée du pas, [0, 1]
    active: frozenset[NeedKind]  # besoins pertinents pour la personne


@dataclass(slots=True)
class CognitiveState:
    aspiration: dict[NeedKind, float]  # seuils θ_k ; fixes en V1
    beliefs: dict[str, Belief] = field(default_factory=dict)  # V2
    desires: list[Desire] = field(default_factory=list)  # V2
    intention: Intention | None = None  # V2
    failure_streak: dict[NeedKind, int] = field(default_factory=dict)  # V2


@dataclass(slots=True)
class AffectiveState:
    emotions: dict[Emotion, float] = field(default_factory=dict)  # V3, [0, 1]
    stress: float = 0.0  # V3, [0, 1]
    mood: float = 0.0  # V3, [−1, 1]


# --- état du foyer (02 §4.6)


@dataclass(slots=True)
class HouseholdState:
    weights: dict[PersonId, float]  # poids d'allocation (Σ = 1)
    ownership: dict[PersonId, float]  # parts ω du pot commun (Σ = 1)
    head_id: PersonId  # pour l'imputation ONU uniquement
    credit_limit: Money = Decimal(0)
    arrears_months: int = 0
    regime: HouseholdRegime = HouseholdRegime.NORMAL  # V3
    stress_months: int = 0  # V3
    cached_pot: Money = Decimal(0)  # caches du Ledger
    cached_savings: Money = Decimal(0)
    cached_loan: Money = Decimal(0)
