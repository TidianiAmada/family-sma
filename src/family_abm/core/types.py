"""Énumérations, alias et objets-valeurs du noyau (02 §2–3).

Toutes les énumérations, y compris celles des versions V2 et V3, sont déclarées dès la V1
pour figer les schémas de sortie (10 §1). ``Role`` est une étiquette descriptive : elle
n'est jamais testée dans la logique du modèle (D1).
"""

import math
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from enum import IntEnum, StrEnum

# --------------------------------------------------------------------------- alias

type Money = Decimal
"""Montant monétaire du ``Ledger`` (quantifié à ``MONEY_QUANTUM`` par ``q``)."""
type Step = int
"""Mois écoulés depuis t₀ (≥ 0)."""
type PersonId = str
"""``"{household_id}-p{index}"``, ex. ``"h0007-p3"``."""
type HouseholdId = str
"""``"h{index:04d}"``, ex. ``"h0007"``."""
type RunId = str
"""Identifiant de run (ULID)."""
type ConfigHash = str
"""SHA-256 de la configuration résolue (JSON canonique)."""

MONTHS_PER_YEAR = 12
"""Conversion années ↔ mois (pas mensuel, 03 §1)."""

MONEY_QUANTUM = Decimal("0.01")
"""Quantum monétaire du ``Ledger`` (convention de mesure, pas un paramètre du modèle)."""
WEIGHT_SUM_TOLERANCE = 1e-12
"""Tolérance de ``Σω = 1`` et ``Σ weights = 1`` (INV-10, 10 §12) : convention de mesure."""


def q(value: Decimal | int | float | str) -> Decimal:
    """Quantifie un montant au centime, arrondi bancaire (``ROUND_HALF_EVEN``).

    C'est la seule porte d'entrée d'un montant calculé (``float``) vers le ``Ledger`` : le
    ``float`` est converti via sa représentation décimale la plus courte, pour ne pas propager
    le bruit binaire. Lève ``ValueError`` pour un booléen, une valeur non finie, illisible ou
    hors de la précision décimale.
    """
    if isinstance(value, bool):
        raise ValueError(f"un booléen n'est pas un montant : {value!r}")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"montant non fini : {value!r}")
        value = repr(value)
    try:
        amount = Decimal(value)
        if not amount.is_finite():
            raise ValueError(f"montant non fini : {value!r}")
        return amount.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_EVEN)
    except InvalidOperation as exc:
        raise ValueError(f"montant illisible ou hors précision : {value!r}") from exc


def make_household_id(index: int) -> HouseholdId:
    """Identifiant de foyer ``"h{index:04d}"`` (02 §3)."""
    if index < 0:
        raise ValueError(f"indice de foyer négatif : {index}")
    return f"h{index:04d}"


def make_person_id(household_id: HouseholdId, index: int) -> PersonId:
    """Identifiant de personne ``"{household_id}-p{index}"`` (02 §3)."""
    if index < 0:
        raise ValueError(f"indice de personne négatif : {index}")
    return f"{household_id}-p{index}"


# --------------------------------------------------------------------------- énumérations


class Role(StrEnum):
    """Étiquette descriptive uniquement — jamais testée dans la logique (D1)."""

    FATHER = "father"
    MOTHER = "mother"
    YOUNG_ADULT = "young_adult"
    ADOLESCENT = "adolescent"
    CHILD = "child"
    BABY = "baby"


class Capability(StrEnum):
    """Ce que le profil autorise ; seule source de variation de comportement avec les paramètres."""

    WORK = "work"
    CONSUME = "consume"
    SAVE = "save"
    SEEK_CARE = "seek_care"
    STUDY = "study"
    REST = "rest"
    BORROW_REQUEST = "borrow_request"  # V2 — peut demander un emprunt au foyer
    SEEK_JOB = "seek_job"  # V2
    PLAN = "plan"  # V2 — accès à la PlanLibrary
    REMEMBER = "remember"  # V2 — accès en écriture à la mémoire épisodique
    APPRAISE = "appraise"  # V3
    RISK_EVAL = "risk_eval"  # V3 — CPT sur décisions binaires
    LEAVE_HOUSEHOLD = "leave_household"  # V2, si household_rules.young_adult_can_leave


class NeedKind(StrEnum):
    FOOD = "food"
    HEALTH = "health"
    EDUCATION = "education"
    HOUSING = "housing"
    REST = "rest"
    SECURITY = "security"


class Tier(IntEnum):
    """Ordre d'arbitrage du foyer."""

    COMMITMENT = 0  # service de la dette, loyer — prélevé avant toute demande
    ESSENTIAL = 1  # alimentation, soins urgents
    EDUCATION = 2
    OTHER = 3  # repos/loisirs, soins non urgents
    SAVING = 4


class ActionKind(StrEnum):
    WORK = "work"
    CONSUME = "consume"
    SAVE = "save"
    SEEK_CARE = "seek_care"
    STUDY = "study"
    REST = "rest"
    # V2
    SEEK_JOB = "seek_job"
    INCREASE_LABOR = "increase_labor"
    REDUCE_CONSUMPTION = "reduce_consumption"
    REQUEST_BORROW = "request_borrow"
    REPAY_EXTRA = "repay_extra"
    WITHDRAW_SAVINGS = "withdraw_savings"
    CONTRIBUTE_MORE = "contribute_more"
    LEAVE_HOUSEHOLD = "leave_household"
    DROP_SCHOOL = "drop_school"
    ENTER_WORK = "enter_work"
    # V3 — décisions binaires évaluées par CPT
    TAKE_LOAN = "take_loan"
    JOIN_MUTUELLE = "join_mutuelle"
    KEEP_IN_SCHOOL = "keep_in_school"
    JOIN_TONTINE = "join_tontine"


class EmploymentStatus(StrEnum):
    EMPLOYED_FORMAL = "employed_formal"
    EMPLOYED_INFORMAL = "employed_informal"
    UNEMPLOYED = "unemployed"
    STUDENT = "student"
    INACTIVE = "inactive"


class SchoolStatus(StrEnum):
    NOT_SCHOOL_AGE = "not_school_age"
    ENROLLED = "enrolled"
    DROPPED_OUT = "dropped_out"
    COMPLETED = "completed"


class DemandStatus(StrEnum):
    GRANTED = "granted"
    PARTIAL = "partial"
    REFUSED = "refused"


class HouseholdRegime(StrEnum):
    NORMAL = "normal"
    SEPARATE_SPHERES = "separate_spheres"  # V3


class AllocationMode(StrEnum):
    """Paramètre d'UNE fonction ``allocate()``, pas des classes (S1)."""

    UNITARY = "unitary"
    FIXED_WEIGHTS = "fixed_weights"
    VARIABLE_WEIGHTS = "variable_weights"


class IntentionStatus(StrEnum):
    ACTIVE = "active"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DROPPED = "dropped"
    SUSPENDED = "suspended"


class Emotion(StrEnum):
    """V3 — quatre émotions ; stress et humeur sont portés à part."""

    JOY = "joy"
    SADNESS = "sadness"
    FEAR = "fear"
    ANGER = "anger"


class DiscountingMode(StrEnum):
    NONE = "none"
    EXPONENTIAL = "exponential"
    NAIVE_BETA_DELTA = "naive"
    SOPHISTICATED_BETA_DELTA = "sophisticated"
