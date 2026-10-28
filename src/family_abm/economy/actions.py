"""Actions des agents : écritures du Ledger et grandeurs dérivées (10 §3–§4, §6, §9).

- T-007 : versement du revenu du travail (``LABOR_INCOME`` → ``TAX``) et mise en commun
  (``POOLING``). Un montant nul ne produit aucune écriture (le Ledger refuse tout montant
  ≤ 0).
- T-008 : exigences monétaires des besoins, satisfactions et niveaux lissés, échelle
  d'équivalence et parts du logement, machine à états de la scolarité. Fonctions pures,
  appliquées par le foyer ; les écritures de consommation du Temps 3 et la mise à jour des
  niveaux à partir des dépenses sont livrées par T-011.
"""

from collections.abc import Mapping
from decimal import Decimal

from family_abm.config.schemas import (
    ConsumptionRequirements,
    EquivalenceWeights,
    RestNeed,
    SchoolingParams,
    lookup_by_age,
)
from family_abm.core.errors import AllocationError
from family_abm.core.types import (
    HouseholdId,
    Money,
    NeedKind,
    PersonId,
    SchoolStatus,
    Step,
    q,
)
from family_abm.economy.accounts import AccountId, AccountKind, FlowCategory
from family_abm.economy.ledger import Ledger


def _wallet(person_id: PersonId) -> AccountId:
    return AccountId(AccountKind.PERSON_WALLET, person_id)


def post_labor_income(
    ledger: Ledger,
    step: Step,
    household_id: HouseholdId,
    person_id: PersonId,
    gross: Money,
    tax: Money,
) -> None:
    """``LABOR_INCOME`` employeur → portefeuille, puis ``TAX`` portefeuille → État."""
    if gross > 0:
        employer = AccountId(AccountKind.EMPLOYER, None)
        ledger.post(
            step,
            household_id,
            employer,
            _wallet(person_id),
            gross,
            FlowCategory.LABOR_INCOME,
            initiator=person_id,
        )
    if tax > 0:
        gov = AccountId(AccountKind.GOV, None)
        ledger.post(
            step,
            household_id,
            _wallet(person_id),
            gov,
            tax,
            FlowCategory.TAX,
            initiator=person_id,
        )


def post_pooling(
    ledger: Ledger, step: Step, household_id: HouseholdId, person_id: PersonId, amount: Money
) -> None:
    """``POOLING`` portefeuille → pot commun du foyer."""
    if amount > 0:
        pot = AccountId(AccountKind.HOUSEHOLD_POT, household_id)
        ledger.post(
            step,
            household_id,
            _wallet(person_id),
            pot,
            amount,
            FlowCategory.POOLING,
            initiator=person_id,
        )


# --- besoins (10 §4)


def monthly_requirements(
    age_years: float,
    *,
    school_enrolled: bool,
    price_index: Decimal,
    requirements: ConsumptionRequirements,
) -> dict[NeedKind, Money]:
    """Exigences r_k(âge) × P_t des besoins de consommation individuels (10 §4).

    FOOD, HEALTH (soins de routine ; le coût d'un épisode est ``care_need``) et EDUCATION
    pour une personne inscrite. Le logement est un engagement du foyer
    (``housing_shares``) ; REST n'est pas monétaire ; SECURITY dépend de l'épargne du foyer.
    """
    tables = {
        NeedKind.FOOD: requirements.food.by_age,
        NeedKind.HEALTH: requirements.health.routine_by_age,
    }
    if school_enrolled:
        tables[NeedKind.EDUCATION] = requirements.education.by_age
    return {
        need: q(Decimal(repr(lookup_by_age(table, age_years))) * price_index)
        for need, table in tables.items()
    }


def smooth_level(previous: float, satisfaction: float, persistence: float) -> float:
    """``level_t = ρ·level_t−1 + (1 − ρ)·sat_t``."""
    return persistence * previous + (1 - persistence) * satisfaction


def ratio_satisfaction(spent: Money, required: Money) -> float:
    """``min(1, dépensé / exigé)`` ; une exigence nulle est satisfaite."""
    if required <= 0:
        return 1.0
    return min(1.0, float(spent / required))


def health_satisfaction(
    *, sick: bool, cared: bool, routine_ratio: float, untreated_factor: float
) -> float:
    """Hors épisode : ratio de routine ; en épisode : 1 si soigné, sinon facteur × ratio."""
    if not sick:
        return routine_ratio
    return 1.0 if cared else untreated_factor * routine_ratio


def education_satisfaction(paid_in_full: bool) -> float:
    """Frais indivisibles : 1 s'ils sont intégralement payés, 0 sinon."""
    return 1.0 if paid_in_full else 0.0


def rest_satisfaction(labor_supply: float, fatigue: float, rest: RestNeed) -> float:
    """``clip(1 − slope·max(0, labor_supply − threshold) − fatigue, 0, 1)``."""
    overwork = max(0.0, labor_supply - rest.labor_threshold)
    return min(1.0, max(0.0, 1 - rest.labor_slope * overwork - fatigue))


def security_satisfaction(savings: Money, spend_avg: Money, target_buffer_months: float) -> float:
    """``min(1, épargne / (target_buffer_months × dépense moyenne))`` — valeur du foyer."""
    target = spend_avg * Decimal(repr(target_buffer_months))
    if target <= 0:
        return 1.0
    return min(1.0, max(0.0, float(savings / target)))


def equivalence_weights(
    ages: Mapping[PersonId, float], head_id: PersonId, weights: EquivalenceWeights
) -> dict[PersonId, float]:
    """Échelle OCDE modifiée : le chef ``first_adult`` ; autres membres d'au moins
    ``adult_age`` ans ``other_adult`` ; plus jeunes ``child``."""
    return {
        person_id: weights.first_adult
        if person_id == head_id
        else weights.other_adult
        if age >= weights.adult_age
        else weights.child
        for person_id, age in ages.items()
    }


def housing_shares(cost: Money, weights: Mapping[PersonId, float]) -> dict[PersonId, Money]:
    """Parts ``e_i / Σe`` du coût du logement, au centime ; le dernier bénéficiaire reçoit
    le résidu d'arrondi, de sorte que ``Σ parts = coût`` (10 §9).

    L'ordre est celui de ``weights`` : le foyer le fournit dans l'ordre de ses membres,
    c'est-à-dire de l'indice des identifiants ``{foyer}-p{i}`` (le tri lexicographique
    placerait ``p10`` avant ``p2``).
    """
    order = list(weights)
    exact = {person_id: Decimal(repr(weights[person_id])) for person_id in order}
    total = sum(exact.values(), Decimal(0))
    if not order or total <= 0:
        raise AllocationError(f"logement : poids d'équivalence vides ou nuls {dict(weights)}")
    shares = {person_id: q(cost * exact[person_id] / total) for person_id in order[:-1]}
    shares[order[-1]] = cost - sum(shares.values(), Decimal(0))
    return shares


# --- scolarité (10 §6, 02 §10.4)


def school_status_by_age(
    status: SchoolStatus, age_years: float, schooling: SchoolingParams
) -> SchoolStatus:
    """Transitions liées à l'âge, appliquées au début du Temps 1 : inscription au premier
    mois où l'âge atteint ``entry_age`` (frais demandés dès ce mois) ; fin d'études à
    ``exit_age.tertiary`` (poursuite automatique après le secondaire en V1)."""
    if status is SchoolStatus.NOT_SCHOOL_AGE and age_years >= schooling.entry_age:
        return SchoolStatus.ENROLLED
    if status is SchoolStatus.ENROLLED and age_years >= schooling.exit_age.tertiary:
        return SchoolStatus.COMPLETED
    return status


def school_status_after_fees(
    status: SchoolStatus, refused_months: int, *, paid: bool, schooling: SchoolingParams
) -> tuple[SchoolStatus, int]:
    """Après l'allocation du mois : refus consécutifs comptés, remis à 0 si les frais sont
    payés ; abandon à ``drop_after_refused_months`` refus consécutifs."""
    if status is not SchoolStatus.ENROLLED:
        return status, refused_months
    months = 0 if paid else refused_months + 1
    if months >= schooling.drop_after_refused_months:
        return SchoolStatus.DROPPED_OUT, months
    return status, months
