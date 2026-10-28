"""Génération des alternatives (paniers) selon les capacités (10 §7.2–7.3).

Un panier fixe un montant demandé pour chaque dimension demandable : les besoins attendus
(``attended_needs``) et, au premier mois d'un épisode de maladie, le soin d'épisode, qui est
une dimension distincte de la routine (décision J13). Tous les coefficients viennent de
``needs.yaml`` (``reduced_share``, ``amount_min_share``, ``saving_horizons_months``).

La rationalité limitée tient à l'ordre et à la troncature : l'habitude d'abord, puis le
produit des niveaux « plein d'abord », partitionné par l'enveloppe attendue si l'agent
anticipe (H ≥ 1), tronqué à ``max_alternatives``.
"""

import itertools
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from family_abm.config.schemas import CognitiveProfile, FoodNeed, HealthNeed, Needs, NeedSpec
from family_abm.core.errors import ConfigError
from family_abm.core.types import Capability, Money, NeedKind, Tier, q
from family_abm.decision.engine import EffectiveCognitiveProfile, Percept

EPISODE: Literal["health_episode"] = "health_episode"
type Dimension = NeedKind | Literal["health_episode"]

# Capacité requise pour demander chaque besoin monétaire individuel (10 §7.2).
REQUIRED_CAPABILITY: Mapping[NeedKind, Capability] = {
    NeedKind.FOOD: Capability.CONSUME,
    NeedKind.HEALTH: Capability.CONSUME,
    NeedKind.EDUCATION: Capability.STUDY,
    NeedKind.SECURITY: Capability.SAVE,
}


@dataclass(frozen=True, slots=True)
class Basket:
    """Une alternative : montant demandé par dimension, dans l'ordre des besoins attendus."""

    alternative_id: str
    amounts: tuple[tuple[Dimension, Money], ...]

    def amount(self, dimension: Dimension) -> Money:
        for key, value in self.amounts:
            if key == dimension:
                return value
        return Decimal(0)

    @property
    def total(self) -> Money:
        return sum((value for _, value in self.amounts), Decimal(0))

    def describe(self) -> str:
        return " ; ".join(f"{key} {value}" for key, value in self.amounts) or "aucune demande"


def spec_of(needs: Needs, need: NeedKind) -> NeedSpec:
    spec: NeedSpec = getattr(needs, need.value)
    return spec


def attended_needs(percept: Percept, base: CognitiveProfile) -> list[NeedKind]:
    """Besoins attendus et actifs, dans l'ordre de ``attended_needs`` (priorité)."""
    return [need for need in base.attended_needs if need in percept.active_needs]


def is_demandable(need: NeedKind, percept: Percept, base: CognitiveProfile, needs: Needs) -> bool:
    """Monétaire, hors engagement du foyer, capacité présente (10 §7.2) ; l'éducation exige
    l'inscription, l'épargne une part ω > 0 ; une exigence nulle n'est pas demandée."""
    spec = spec_of(needs, need)
    capability = REQUIRED_CAPABILITY.get(need)
    if spec.tier is Tier.COMMITMENT or capability is None:
        return False
    if capability not in base.capabilities or need not in percept.active_needs:
        return False
    if need is NeedKind.SECURITY:
        return percept.ownership_share > 0
    if need is NeedKind.EDUCATION and not percept.school_enrolled:
        return False
    return percept.requirements.get(need, Decimal(0)) > 0


def dimensions(percept: Percept, base: CognitiveProfile, needs: Needs) -> list[Dimension]:
    """Dimensions du panier ; le soin d'épisode suit la routine de santé."""
    dims: list[Dimension] = []
    for need in attended_needs(percept, base):
        if is_demandable(need, percept, base, needs):
            dims.append(need)
        if (
            need is NeedKind.HEALTH
            and percept.care_need > 0
            and Capability.SEEK_CARE in base.capabilities
        ):
            dims.append(EPISODE)
    return dims


def requirement(dimension: Dimension, percept: Percept) -> Money:
    if dimension == EPISODE:
        return percept.care_need
    return percept.requirements.get(dimension, Decimal(0))


def is_divisible(dimension: Dimension, needs: Needs) -> bool:
    """``needs.health`` (palier, divisibilité) décrit le soin d'épisode ; la routine de
    santé est divisible (10 §7.3 : « HEALTH routine : 0 » dans la branche divisible ; J15)."""
    if dimension == EPISODE:
        return needs.health.divisible
    if dimension is NeedKind.HEALTH:
        return True
    return spec_of(needs, dimension).divisible


def amount_min(dimension: Dimension, percept: Percept, needs: Needs) -> Money:
    """Montant minimal utile (10 §7.3) : part minimale × r si divisible ; r sinon ;
    0 pour l'épargne."""
    if dimension is NeedKind.SECURITY:
        return Decimal(0)
    r = requirement(dimension, percept)
    if not is_divisible(dimension, needs):
        return r
    return q(r * Decimal(repr(_divisible_spec(dimension, needs).amount_min_share)))


def level_options(dimension: Dimension, percept: Percept, needs: Needs) -> list[Money]:
    """Niveaux possibles d'une dimension, du plus haut au plus bas, sans doublon."""
    if dimension is NeedKind.SECURITY:
        gap_share = Decimal(repr(percept.ownership_share)) * percept.savings_gap
        options = [q(gap_share / horizon) for horizon in needs.security.saving_horizons_months]
        return _unique([*options, Decimal(0)])
    r = requirement(dimension, percept)
    if not is_divisible(dimension, needs):
        return _unique([r, Decimal(0)])
    reduced = q(r * Decimal(repr(_divisible_spec(dimension, needs).reduced_share)))
    return _unique([r, reduced, amount_min(dimension, percept, needs)])


def _divisible_spec(dimension: Dimension, needs: Needs) -> FoodNeed | HealthNeed:
    """Spécification d'un besoin divisible ; ses parts réduite et minimale sont exigées."""
    spec = spec_of(needs, NeedKind(dimension))
    if not isinstance(spec, FoodNeed | HealthNeed):
        raise ConfigError(f"besoin divisible {dimension} sans reduced_share ni amount_min_share")
    return spec


def generate(
    percept: Percept,
    profile: EffectiveCognitiveProfile,
    base: CognitiveProfile,
    needs: Needs,
) -> list[Basket]:
    """Alternatives dans l'ordre de saillance, tronquées à ``max_alternatives``."""
    dims = dimensions(percept, base, needs)
    ordered: list[Basket] = []
    seen: set[tuple[tuple[Dimension, Money], ...]] = set()
    if percept.habitual is not None:
        habit = tuple(
            (dim, _habitual_amount(dim, percept, needs, percept.habitual)) for dim in dims
        )
        ordered.append(Basket("habit", habit))
        seen.add(habit)
    options = [level_options(dim, percept, needs) for dim in dims]
    for index, levels in enumerate(itertools.product(*options)):
        amounts = tuple(zip(dims, levels, strict=True))
        if amounts not in seen:
            seen.add(amounts)
            ordered.append(Basket(f"alt-{index}", amounts))
    envelope = percept.envelope
    if profile.planning_horizon >= 1 and envelope is not None:
        ordered = [b for b in ordered if b.total <= envelope] + [
            b for b in ordered if b.total > envelope
        ]
    return ordered[: profile.max_alternatives]


def _habitual_amount(
    dimension: Dimension, percept: Percept, needs: Needs, habitual: Mapping[NeedKind, Money]
) -> Money:
    """Montant habituel ramené aux niveaux du pas courant (exigences indexées sur P_t,
    écart d'épargne) : une dimension nouvelle (soin d'épisode, besoin qui vient de
    s'activer) est au niveau plein ; un montant nul reste nul ; un indivisible repris est
    au r courant ; l'épargne est plafonnée au niveau plein ; un divisible est borné à
    [minimum, plein]."""
    full = level_options(dimension, percept, needs)[0]
    if dimension == EPISODE or dimension not in habitual:
        return full
    amount = habitual[dimension]
    if amount <= 0:
        return Decimal(0)
    if dimension is NeedKind.SECURITY:
        return min(amount, full)
    if not is_divisible(dimension, needs):
        return full
    return max(amount_min(dimension, percept, needs), min(amount, full))


def _unique(values: list[Money]) -> list[Money]:
    return list(dict.fromkeys(values))
