"""``SatisficingEngine`` — décision par satisficing non compensatoire (10 §7.4–7.5).

Le même moteur couvre le continuum réactif → délibératif : seuls ``max_alternatives``,
``planning_horizon`` (H), ``impulsivity``, ``attended_needs`` et les capacités du profil
font varier le comportement (règle 1). La première alternative dont chaque besoin vérifié
atteint son seuil est retenue ; sinon, repli lexicographique sur le premier besoin qu'aucune
alternative ne satisfait. Le moteur ne lit jamais l'affect (règle 7) et ne tire que dans le
flux ``decision_ties`` qu'on lui passe : un tirage par décision, pour l'impulsivité.
"""

from collections.abc import Mapping
from decimal import Decimal

import numpy as np

from family_abm.config.schemas import CognitiveProfile, Needs
from family_abm.core.types import ActionKind, NeedKind, Tier
from family_abm.decision.alternatives import (
    EPISODE,
    Basket,
    Dimension,
    amount_min,
    attended_needs,
    generate,
    is_demandable,
    is_divisible,
    spec_of,
)
from family_abm.decision.engine import (
    AlternativeEval,
    DecisionTrace,
    Demand,
    DemandSet,
    EffectiveCognitiveProfile,
    Percept,
)

RULE_REACTIVE = "reactive"
RULE_FIRST_ACCEPTABLE = "first_acceptable"
RULE_FALLBACK = "fallback_top_need"


class SatisficingEngine:
    """Seule implémentation livrée de ``DecisionEngine`` (S1)."""

    def __init__(self, needs: Needs) -> None:
        self.needs = needs

    def decide(
        self,
        percept: Percept,
        profile: EffectiveCognitiveProfile,
        base: CognitiveProfile,
        aspiration: Mapping[NeedKind, float],
        rng: np.random.Generator,
    ) -> DemandSet:
        attended = attended_needs(percept, base)
        theta = {k: aspiration[k] * profile.aspiration_scale for k in attended}
        shortcut = bool(rng.random() < base.impulsivity)  # un tirage par décision
        checked = attended[:1] if shortcut else attended
        reactive = profile.max_alternatives == 1 and profile.planning_horizon == 0
        demandable = frozenset(k for k in attended if is_demandable(k, percept, base, self.needs))
        evals: list[AlternativeEval] = []
        baskets = generate(percept, profile, base, self.needs)
        for basket in baskets:
            scores = {
                k: self.score(basket, k, percept, profile.planning_horizon, demandable)
                for k in attended
            }
            failed = next((k for k in checked if scores[k] < theta[k]), None)
            evals.append(
                AlternativeEval(
                    alternative_id=basket.alternative_id,
                    description=basket.describe(),
                    projected_levels=scores,
                    acceptable=failed is None,
                    failed_need=failed,
                )
            )
            if failed is None:
                rule = RULE_REACTIVE if reactive else RULE_FIRST_ACCEPTABLE
                return self._demand_set(percept, base, profile, theta, basket, evals, rule)
        chosen = baskets[_fallback_index(evals, attended, theta)]
        rule = RULE_REACTIVE if reactive else RULE_FALLBACK
        return self._demand_set(percept, base, profile, theta, chosen, evals, rule)

    # --- projection (10 §7.4)

    def score(
        self,
        basket: Basket,
        need: NeedKind,
        percept: Percept,
        horizon: int,
        demandable: frozenset[NeedKind],
    ) -> float:
        """Niveau moyen projeté du besoin sur ``t = 0..H`` (actualisation D(t) = 1 en V1).

        ŝ est constant sur l'horizon, sauf pour SECURITY, dont l'épargne projetée croît.
        """
        rho = spec_of(self.needs, need).persistence
        level = percept.needs_level[need]
        expected = _expected_ratio(basket, need, percept)
        security = need is NeedKind.SECURITY and need in demandable
        constant = (
            0.0 if security else self._satisfaction(basket, need, percept, demandable, expected)
        )
        total = 0.0
        for t in range(horizon + 1):
            sat = self._security(basket, percept, expected, t) if security else constant
            level = rho * level + (1 - rho) * sat
            total += level
        return total / (horizon + 1)

    @staticmethod
    def _security(basket: Basket, percept: Percept, expected: float, t: int) -> float:
        """``min(1, (épargne + (t+1)·a_SEC/ω·ê) / cible)`` : l'autre propriétaire est supposé
        épargner symétriquement (10 §7.4)."""
        target = float(percept.savings_target)
        if target <= 0:
            return 1.0
        per_month = float(basket.amount(NeedKind.SECURITY)) / percept.ownership_share
        projected = float(percept.savings) + (t + 1) * per_month * expected
        return min(1.0, max(0.0, projected / target))  # score projeté : float suffit

    def _satisfaction(
        self,
        basket: Basket,
        need: NeedKind,
        percept: Percept,
        demandable: frozenset[NeedKind],
        expected: float,
    ) -> float:
        health_demanded = need in demandable or any(k == EPISODE for k, _ in basket.amounts)
        if need is NeedKind.HEALTH and health_demanded:
            return self._health_satisfaction(basket, percept, demandable, expected)
        if need not in demandable:
            # non demandable mais attendu (logement, repos…) : satisfaction du pas précédent
            return percept.last_satisfaction.get(need, percept.needs_level[need])
        return _ratio(basket.amount(need), percept.requirements[need], expected)

    def _health_satisfaction(
        self,
        basket: Basket,
        percept: Percept,
        demandable: frozenset[NeedKind],
        expected: float,
    ) -> float:
        """Satisfaction de santé de 10 §4 appliquée au panier (décision J14) : hors épisode,
        ratio de routine ; en épisode, 1 si soigné (déjà, ou soin d'épisode demandé au
        premier mois et attendu en entier), sinon ``sat_untreated_factor`` × ratio."""
        routine = basket.amount(NeedKind.HEALTH) if NeedKind.HEALTH in demandable else Decimal(0)
        ratio = _ratio(routine, percept.requirements.get(NeedKind.HEALTH, Decimal(0)), expected)
        if not percept.sick:
            return ratio
        episode = basket.amount(EPISODE) * Decimal(repr(expected))
        cared = percept.cared or (percept.care_need > 0 and episode >= percept.care_need)
        return 1.0 if cared else self.needs.health.sat_untreated_factor * ratio

    # --- demandes

    def _demand_set(
        self,
        percept: Percept,
        base: CognitiveProfile,
        profile: EffectiveCognitiveProfile,
        theta: Mapping[NeedKind, float],
        basket: Basket,
        evals: list[AlternativeEval],
        rule: str,
    ) -> DemandSet:
        priority = {need: rank for rank, need in enumerate(attended_needs(percept, base))}
        demands = tuple(
            self._demand(percept, dimension, amount, priority)
            for dimension, amount in basket.amounts
            if amount > 0
        )
        trace = DecisionTrace(
            person_id=percept.person_id,
            step=percept.step,
            profile_effective=profile,
            aspiration=dict(theta),
            considered=tuple(evals),
            chosen_id=basket.alternative_id,
            rule=rule,
        )
        labor_supply = 1.0 if percept.employed else 0.0  # offre constante en V1 (10 §3)
        return DemandSet(percept.person_id, demands, labor_supply, trace)

    def _demand(
        self,
        percept: Percept,
        dimension: Dimension,
        amount: Decimal,
        priority: Mapping[NeedKind, int],
    ) -> Demand:
        need = NeedKind.HEALTH if dimension == EPISODE else NeedKind(dimension)
        tier, action = _tier_and_action(dimension, spec_of(self.needs, need).tier)
        return Demand(
            demand_id=f"{percept.step}-{percept.person_id}-{dimension}",
            person_id=percept.person_id,
            need=None if need is NeedKind.SECURITY else need,  # 02 §5 : None pour SAVING
            tier=tier,
            amount_requested=amount,
            amount_min=amount_min(dimension, percept, self.needs),
            priority=priority[need],
            divisible=is_divisible(dimension, self.needs),
            action=action,
        )


def _tier_and_action(dimension: Dimension, configured: Tier) -> tuple[Tier, ActionKind]:
    """Palier et action (10 §7.5) : le palier de ``needs.yaml`` (pour la santé, celui du
    soin d'épisode, ESSENTIAL) ; routine de santé ⇒ OTHER ; SECURITY ⇒ SAVING."""
    if dimension == EPISODE:
        return configured, ActionKind.SEEK_CARE
    if dimension is NeedKind.HEALTH:
        return Tier.OTHER, ActionKind.CONSUME
    if dimension is NeedKind.SECURITY:
        return Tier.SAVING, ActionKind.SAVE
    if dimension is NeedKind.EDUCATION:
        return configured, ActionKind.STUDY
    return configured, ActionKind.CONSUME


def _expected_ratio(basket: Basket, need: NeedKind, percept: Percept) -> float:
    """ê_k(a) : 1 si le panier tient dans l'enveloppe (ou sans enveloppe), sinon le ratio
    accordé passé."""
    if percept.envelope is None or basket.total <= percept.envelope:
        return 1.0
    return percept.expected_grant_ratio.get(need, 1.0)


def _ratio(amount: Decimal, required: Decimal, expected: float) -> float:
    if required <= 0:
        return 1.0
    return min(1.0, float(amount / required) * expected)


def _fallback_index(
    evals: list[AlternativeEval], attended: list[NeedKind], theta: Mapping[NeedKind, float]
) -> int:
    """Repli lexicographique (10 §7.5) : k* est le premier besoin qu'aucune alternative
    satisfaisant tous les besoins précédents n'atteint ; parmi elles, la meilleure sur k*,
    la première en cas d'égalité."""
    pool = list(range(len(evals)))
    for need in attended:
        passing = [i for i in pool if evals[i].projected_levels[need] >= theta[need]]
        if not passing:
            return max(pool, key=lambda i: (evals[i].projected_levels[need], -i))
        pool = passing
    return pool[0]
