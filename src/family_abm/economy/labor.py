"""Travail, emploi et chocs de revenu (10 §3, ODD-V1 §7.2–§7.3).

Fonctions pures : le foyer (``agents/household.py``) les applique à l'état de chaque membre
au début du Temps 2. Les tirages aléatoires sont séparés des transitions : chaque personne
tire, **à chaque pas et quel que soit son état**, deux uniformes dans son flux
``employment`` et une normale centrée réduite dans son flux ``income_shocks``. Le nombre de
tirages ne dépend donc pas de la trajectoire : deux scénarios de même seed partagent les
mêmes nombres aléatoires (comparaisons à nombres aléatoires communs).
"""

import math
from dataclasses import dataclass
from decimal import Decimal

import numpy as np

from family_abm.config.schemas import EconomicParams, IncomeShocks, TaxParams
from family_abm.core.types import EmploymentStatus, Money, SchoolStatus, q

EMPLOYED = frozenset({EmploymentStatus.EMPLOYED_FORMAL, EmploymentStatus.EMPLOYED_INFORMAL})
SCHOOL_LEFT = frozenset({SchoolStatus.COMPLETED, SchoolStatus.DROPPED_OUT})


@dataclass(frozen=True, slots=True)
class EmploymentDraw:
    """Uniformes d'un pas : ``transition`` décide le changement d'état, ``formal`` le secteur
    d'un emploi trouvé."""

    transition: float
    formal: float


def draw_employment(rng: np.random.Generator) -> EmploymentDraw:
    """Deux uniformes [0, 1[ tirés dans le flux ``employment`` de la personne."""
    transition, formal = rng.random(2)
    return EmploymentDraw(transition=float(transition), formal=float(formal))


def income_multiplier(rng: np.random.Generator, volatility: float) -> float:
    """``m ~ LogNormal(−σ²/2, σ)``, d'espérance 1 (10 §20.1), tiré dans ``income_shocks``.

    La normale est tirée même si ``σ = 0`` (alors ``m = 1``), pour garder le flux aligné.
    """
    z = float(rng.standard_normal())
    return math.exp(-(volatility**2) / 2 + volatility * z)


def next_employment(
    status: EmploymentStatus,
    *,
    last_sector: EmploymentStatus | None,
    school_status: SchoolStatus,
    age_years: float,
    can_work: bool,
    params: EconomicParams,
    draw: EmploymentDraw,
) -> EmploymentStatus:
    """Statut d'emploi du mois (10 §3), appliqué au début du Temps 2.

    - employé ⇒ chômeur avec ``p_loss_monthly`` de son secteur ;
    - chômeur ⇒ employé avec ``p_find_monthly`` du secteur du dernier emploi (informel s'il
      n'a jamais travaillé) ; l'emploi trouvé est formel avec ``find_formal_share`` ; une
      personne sans la capacité ``work`` (``can_work`` faux) n'est pas éligible et reste au
      chômage (10 §3, J9) ;
    - étudiant ⇒ chômeur quand sa scolarité est terminée ou abandonnée et que son âge atteint
      ``employment.min_work_age`` ;
    - inactif ⇒ étudiant à l'inscription scolaire.
    """
    shocks: IncomeShocks = params.income_shocks
    match status:
        case EmploymentStatus.EMPLOYED_FORMAL:
            lost = draw.transition < shocks.formal.p_loss_monthly
            return EmploymentStatus.UNEMPLOYED if lost else status
        case EmploymentStatus.EMPLOYED_INFORMAL:
            lost = draw.transition < shocks.informal.p_loss_monthly
            return EmploymentStatus.UNEMPLOYED if lost else status
        case EmploymentStatus.UNEMPLOYED:
            formal = last_sector is EmploymentStatus.EMPLOYED_FORMAL
            sector = shocks.formal if formal else shocks.informal
            if not can_work or draw.transition >= sector.p_find_monthly:
                return status
            if draw.formal < shocks.find_formal_share:
                return EmploymentStatus.EMPLOYED_FORMAL
            return EmploymentStatus.EMPLOYED_INFORMAL
        case EmploymentStatus.STUDENT:
            leaves = school_status in SCHOOL_LEFT and age_years >= params.employment.min_work_age
            return EmploymentStatus.UNEMPLOYED if leaves else status
        case EmploymentStatus.INACTIVE:
            enrolled = school_status is SchoolStatus.ENROLLED
            return EmploymentStatus.STUDENT if enrolled else status


@dataclass(frozen=True, slots=True)
class EmploymentSpell:
    """Grandeurs dérivées du statut après la transition du mois."""

    labor_supply: float  # 1 en emploi, 0 sinon (V1 : offre constante, 10 §3)
    months_employed: int
    months_unemployed: int
    last_sector: EmploymentStatus | None


def update_spell(
    status: EmploymentStatus,
    *,
    months_employed: int,
    months_unemployed: int,
    last_sector: EmploymentStatus | None,
) -> EmploymentSpell:
    """Offre de travail, mois consécutifs en emploi et au chômage, secteur du dernier emploi."""
    if status in EMPLOYED:
        return EmploymentSpell(1.0, months_employed + 1, 0, status)
    unemployed = months_unemployed + 1 if status is EmploymentStatus.UNEMPLOYED else 0
    return EmploymentSpell(0.0, 0, unemployed, last_sector)


def effective_multiplier(status: EmploymentStatus, multiplier: float) -> float:
    """``m`` ne s'applique qu'au revenu informel ; le revenu formel est certain (m = 1)."""
    return multiplier if status is EmploymentStatus.EMPLOYED_INFORMAL else 1.0


def gross_labor_income(
    *,
    wage_monthly: Money,
    wage_index: Decimal,
    labor_supply: float,
    labor_capacity: float,
    multiplier: float,
) -> Money:
    """``Yl = wage_monthly × W_t × labor_supply × labor_capacity × m``, au centime."""
    factors = Decimal(repr(labor_supply)) * Decimal(repr(labor_capacity))
    return q(wage_monthly * wage_index * factors * Decimal(repr(multiplier)))


def labor_tax(gross: Money, status: EmploymentStatus, tax: TaxParams) -> Money:
    """Impôt prélevé à la source : taux formel ou informel selon le secteur de l'emploi."""
    rate = tax.formal_rate if status is EmploymentStatus.EMPLOYED_FORMAL else tax.informal_rate
    return q(gross * Decimal(repr(rate)))


def pooled_amount(net_income: Money, pooling_rate: float) -> Money:
    """Part du revenu net versée au pot : ``pooling_rate × (Yl − impôt)``."""
    return q(net_income * Decimal(repr(pooling_rate)))
