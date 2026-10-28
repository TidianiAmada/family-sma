"""``allocate()`` — arbitrage du foyer au Temps 2, fonction pure paramétrée (10 §8.2–8.3, S1).

Une seule fonction, paramétrée par le mode (``FIXED_WEIGHTS``, ``UNITARY``) : pas de
hiérarchie d'allocation. Les sources se mobilisent dans l'ordre pot → retrait d'épargne →
emprunt (dans la marge ``credit_limit − debt``) :

- ``COMMITMENT`` (logement, puis échéance) et ``ESSENTIAL`` : pot, épargne, emprunt (emprunt
  pour ESSENTIAL seulement si ce palier figure dans ``borrow_for_tiers``) ;
- ``EDUCATION`` et ``OTHER`` : pot et épargne ;
- ``SAVING`` : pot seul (le montant accordé devient un dépôt).

Dans un palier insuffisant : les indivisibles sont accordés en entier par poids
décroissant tant qu'ils tiennent ; les divisibles se partagent le reste au prorata
``poids × demande``, ceux qui tombent sous leur minimum sont refusés et le reste redistribué.
Les parts sont arrondies au centime inférieur : le total accordé ne dépasse jamais les
ressources. Le résultat ne dépend pas de l'ordre des demandes en entrée.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal

from family_abm.core.errors import AllocationError, NotInV1Error
from family_abm.core.types import (
    MONEY_QUANTUM,
    ActionKind,
    AllocationMode,
    DemandStatus,
    Money,
    NeedKind,
    PersonId,
    Tier,
)
from family_abm.decision.engine import Allocation, Demand

REASON_BUDGET = "budget_exhausted"
REASON_BELOW_MIN = "below_min"
REASON_RATIONED = "rationed"


@dataclass(frozen=True, slots=True)
class AllocationInput:
    demands: tuple[Demand, ...]
    pot: Money  # après versements, impôts, mise en commun, transferts publics
    savings: Money
    debt: Money
    credit_limit: Money
    housing_shares: Mapping[PersonId, Money]
    min_repayment: Money
    weights: Mapping[PersonId, float]
    mode: AllocationMode
    priority_order: tuple[NeedKind, ...] | None  # UNITARY : attended_needs du priority_owner
    borrow_for_tiers: frozenset[Tier]


@dataclass(frozen=True, slots=True)
class AllocationResult:
    allocations: tuple[Allocation, ...]
    housing_paid: Mapping[PersonId, Money]
    repayment_paid: Money
    withdrawal: Money
    borrowing: Money
    deposit: Money
    arrears: bool  # échéance non intégralement payée
    # extension de 10 §8.2 (J19) : un palier qui peut emprunter demandait plus que ses
    # ressources, marge de crédit comprise — l'emprunt a été plafonné (10 §8.4)
    credit_limit_hit: bool = False


@dataclass(slots=True)
class _Funds:
    pot: Money
    savings: Money
    margin: Money
    borrow_for_tiers: frozenset[Tier]
    withdrawal: Money = field(default_factory=Decimal)
    borrowing: Money = field(default_factory=Decimal)

    def _uses_savings(self, tier: Tier) -> bool:
        return tier is not Tier.SAVING

    def borrows(self, tier: Tier) -> bool:
        return tier is Tier.COMMITMENT or tier in self.borrow_for_tiers

    def available(self, tier: Tier) -> Money:
        total = self.pot
        if self._uses_savings(tier):
            total += self.savings
        if self.borrows(tier):
            total += self.margin
        return total

    def spend(self, amount: Money, tier: Tier) -> None:
        """Prélève ``amount`` dans l'ordre pot → épargne → emprunt."""
        from_pot = min(amount, self.pot)
        self.pot -= from_pot
        rest = amount - from_pot
        if rest > 0 and self._uses_savings(tier):
            withdrawn = min(rest, self.savings)
            self.savings -= withdrawn
            self.withdrawal += withdrawn
            rest -= withdrawn
        if rest > 0 and self.borrows(tier):
            borrowed = min(rest, self.margin)
            self.margin -= borrowed
            self.borrowing += borrowed
            rest -= borrowed
        if rest > 0:
            raise AllocationError(f"palier {tier.name} : dépense {amount} au-delà des ressources")


def allocate(inp: AllocationInput) -> AllocationResult:
    """Arbitrage du Temps 2 (10 §8.3)."""
    if inp.mode is AllocationMode.VARIABLE_WEIGHTS:
        raise NotInV1Error("allocation à poids variables : V2")
    demands = sorted(inp.demands, key=lambda d: d.demand_id)
    duplicates = sorted(
        {
            a.demand_id
            for a, b in zip(demands, demands[1:], strict=False)
            if a.demand_id == b.demand_id
        }
    )
    if duplicates:
        raise AllocationError(f"identifiants de demande en double : {duplicates}")
    weights, priority = _weights_and_priority(inp, demands)
    funds = _Funds(
        pot=inp.pot,
        savings=inp.savings,
        margin=max(Decimal(0), inp.credit_limit - inp.debt),
        borrow_for_tiers=inp.borrow_for_tiers,
    )
    commitments = sum(inp.housing_shares.values(), Decimal(0)) + inp.min_repayment
    limit_hit = commitments > funds.available(Tier.COMMITMENT)
    housing_paid = _pay_housing(inp.housing_shares, funds)
    repayment = min(inp.min_repayment, funds.available(Tier.COMMITMENT))
    if repayment > 0:
        funds.spend(repayment, Tier.COMMITMENT)
    granted: dict[str, Money] = {}
    reasons: dict[str, str] = {}
    for tier in (Tier.ESSENTIAL, Tier.EDUCATION, Tier.OTHER, Tier.SAVING):
        in_tier = [d for d in demands if d.tier is tier]
        if not in_tier:
            continue
        budget = funds.available(tier)
        requested = sum((d.amount_requested for d in in_tier), Decimal(0))
        limit_hit |= funds.borrows(tier) and requested > budget  # emprunt plafonné
        tier_granted, tier_reasons = _ration(in_tier, budget, weights, priority)
        granted.update(tier_granted)
        reasons.update(tier_reasons)
        spent = sum(tier_granted.values(), Decimal(0))
        if spent > 0:
            funds.spend(spent, tier)
    allocations = tuple(_allocation(d, granted[d.demand_id], reasons) for d in demands)
    deposit = sum((granted[d.demand_id] for d in demands if d.tier is Tier.SAVING), Decimal(0))
    return AllocationResult(
        allocations=allocations,
        housing_paid=housing_paid,
        repayment_paid=repayment,
        withdrawal=funds.withdrawal,
        borrowing=funds.borrowing,
        deposit=deposit,
        arrears=repayment < inp.min_repayment,
        credit_limit_hit=limit_hit,
    )


def _weights_and_priority(
    inp: AllocationInput, demands: Sequence[Demand]
) -> tuple[dict[PersonId, Decimal], dict[str, int]]:
    """FIXED_WEIGHTS : poids normalisés, priorités des personnes. UNITARY : poids égaux,
    priorité = rang du besoin dans l'ordre du décideur."""
    if inp.mode is AllocationMode.UNITARY:
        order = list(inp.priority_order or ())
        ranks = {
            d.demand_id: order.index(_need(d)) if _need(d) in order else len(order) for d in demands
        }
        return {d.person_id: Decimal(1) for d in demands}, ranks
    weights = {pid: Decimal(repr(w)) for pid, w in inp.weights.items()}
    missing = {d.person_id for d in demands} - set(weights)
    if missing:
        raise AllocationError(f"poids d'allocation absents pour {sorted(missing)}")
    return weights, {d.demand_id: d.priority for d in demands}


def _need(demand: Demand) -> NeedKind:
    return NeedKind.SECURITY if demand.need is None else demand.need


def _pay_housing(shares: Mapping[PersonId, Money], funds: _Funds) -> dict[PersonId, Money]:
    """Logement payé en entier si possible, sinon au prorata des parts (centime inférieur)."""
    total = sum(shares.values(), Decimal(0))
    available = funds.available(Tier.COMMITMENT)
    if total <= available:
        paid = dict(shares)
    else:
        paid = {pid: _floor(available * share / total) for pid, share in shares.items()}
    spent = sum(paid.values(), Decimal(0))
    if spent > 0:
        funds.spend(spent, Tier.COMMITMENT)
    return paid


def _ration(
    demands: Sequence[Demand],
    budget: Money,
    weights: Mapping[PersonId, Decimal],
    priority: Mapping[str, int],
) -> tuple[dict[str, Money], dict[str, str]]:
    """Montants accordés dans un palier (10 §8.3, étape 2)."""
    if sum((d.amount_requested for d in demands), Decimal(0)) <= budget:
        return {d.demand_id: d.amount_requested for d in demands}, {}
    granted: dict[str, Money] = {}
    reasons: dict[str, str] = {}
    rest = budget
    indivisible = sorted(
        (d for d in demands if not d.divisible),
        key=lambda d: (-weights[d.person_id], priority[d.demand_id], d.demand_id),
    )
    for demand in indivisible:
        if demand.amount_requested <= rest:
            granted[demand.demand_id] = demand.amount_requested
            rest -= demand.amount_requested
        else:
            granted[demand.demand_id] = Decimal(0)
            reasons[demand.demand_id] = REASON_BUDGET
    active = [d for d in demands if d.divisible]
    if rest <= 0:
        for demand in active:
            granted[demand.demand_id] = Decimal(0)
            reasons[demand.demand_id] = REASON_BUDGET
        return granted, reasons
    while True:
        shares = _proportional(active, rest, weights)
        below = [d for d in active if shares[d.demand_id] < d.amount_min]
        if not below:
            break
        # « retirer d et redistribuer » : la demande la plus loin de son minimum d'abord
        worst = min(below, key=lambda d: (shares[d.demand_id] / d.amount_min, d.demand_id))
        granted[worst.demand_id] = Decimal(0)
        reasons[worst.demand_id] = REASON_BELOW_MIN
        active = [d for d in active if d is not worst]
    granted.update(shares)
    return granted, reasons


def _proportional(
    demands: Sequence[Demand], rest: Money, weights: Mapping[PersonId, Decimal]
) -> dict[str, Money]:
    """Parts ``rest × w·req / Σ w·req`` au centime inférieur ; une part qui atteint la
    demande est plafonnée et l'excédent redistribué aux autres (jusqu'à stabilité)."""
    shares: dict[str, Money] = {}
    open_ = list(demands)
    while open_:
        if sum((d.amount_requested for d in open_), Decimal(0)) <= rest:
            shares.update({d.demand_id: d.amount_requested for d in open_})
            return shares
        total = sum((weights[d.person_id] * d.amount_requested for d in open_), Decimal(0))
        if total <= 0:
            shares.update({d.demand_id: Decimal(0) for d in open_})
            return shares
        exact = {
            d.demand_id: rest * weights[d.person_id] * d.amount_requested / total for d in open_
        }
        capped = [d for d in open_ if exact[d.demand_id] >= d.amount_requested]
        if not capped:
            shares.update({d.demand_id: _floor(exact[d.demand_id]) for d in open_})
            return shares
        for demand in capped:
            shares[demand.demand_id] = demand.amount_requested
            rest -= demand.amount_requested
        open_ = [d for d in open_ if d not in capped]
    return shares


def _allocation(demand: Demand, granted: Money, reasons: Mapping[str, str]) -> Allocation:
    if granted >= demand.amount_requested:
        return Allocation(demand.demand_id, granted, DemandStatus.GRANTED, "")
    if granted > 0:
        return Allocation(demand.demand_id, granted, DemandStatus.PARTIAL, REASON_RATIONED)
    reason = reasons.get(demand.demand_id, REASON_BUDGET)
    return Allocation(demand.demand_id, granted, DemandStatus.REFUSED, reason)


def _floor(amount: Decimal) -> Money:
    return amount.quantize(MONEY_QUANTUM, rounding=ROUND_DOWN)


# --- retour d'information pour la perception du pas suivant (10 §7.1, §7.3)


@dataclass(frozen=True, slots=True)
class Feedback:
    habitual: dict[NeedKind, Money]  # panier demandé au pas précédent (soin d'épisode exclu)
    grant_ratio: dict[NeedKind, float]  # ê_k : Σ accordé / Σ demandé par besoin
    granted_total: Money  # Σ accordé à la personne (enveloppe = ce total + portefeuille)


def feedback(demands: Sequence[Demand], allocations: Sequence[Allocation]) -> Feedback:
    """Ce que la personne retient de son allocation du pas précédent."""
    granted = {a.demand_id: a.granted for a in allocations}
    requested_by_need: dict[NeedKind, Money] = {}
    granted_by_need: dict[NeedKind, Money] = {}
    habitual: dict[NeedKind, Money] = {}
    for demand in demands:
        need = _need(demand)
        amount = granted.get(demand.demand_id, Decimal(0))
        requested_by_need[need] = requested_by_need.get(need, Decimal(0)) + demand.amount_requested
        granted_by_need[need] = granted_by_need.get(need, Decimal(0)) + amount
        if demand.action is not ActionKind.SEEK_CARE:
            habitual[need] = demand.amount_requested
    ratio = {
        need: float(granted_by_need[need] / requested)
        for need, requested in requested_by_need.items()
        if requested > 0
    }
    return Feedback(habitual, ratio, sum(granted.values(), Decimal(0)))
