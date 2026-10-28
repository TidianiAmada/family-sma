"""Indices de prix et de salaire, taux mensuels (10 §2, ODD-V1 §7.2).

Toute valeur monétaire de besoin, de logement, de soins, de frais de scolarité et de
consommation publique est multipliée par ``P_t`` ; tout salaire par ``W_t``. Les indices
sont calculés en ``Decimal`` (précision du contexte par défaut, 28 chiffres) ; seuls les
montants qui en résultent sont quantifiés au centime, par l'appelant.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from family_abm.config.schemas import EconomicParams
from family_abm.core.types import MONTHS_PER_YEAR, Step


@dataclass(frozen=True, slots=True)
class PriceShock:
    """Choc de prix survenu au pas ``step`` : le niveau des prix est multiplié par ``1 + rate``."""

    step: Step
    rate: float


type PriceShockLog = Sequence[PriceShock]


def _decimal(value: float) -> Decimal:
    return Decimal(repr(value))


def price_index(step: Step, cfg: EconomicParams, shocks: PriceShockLog = ()) -> Decimal:
    """``P_t = (1 + π)^(t/12) × Π(1 + choc)`` pour les chocs de prix déjà survenus (pas ≤ t)."""
    base = (1 + _decimal(cfg.prices.inflation_annual)) ** (Decimal(step) / MONTHS_PER_YEAR)
    for shock in shocks:
        if shock.step <= step:
            base *= 1 + _decimal(shock.rate)
    return base


def wage_index(step: Step, cfg: EconomicParams) -> Decimal:
    """``W_t = (1 + g)^floor(t/12)`` — revalorisation annuelle des salaires."""
    return (1 + _decimal(cfg.wage_growth_annual)) ** (step // MONTHS_PER_YEAR)


def monthly_rate(annual: float) -> Decimal:
    """Taux mensuel équivalent : ``(1 + r)^(1/12) − 1``."""
    return (1 + _decimal(annual)) ** (Decimal(1) / MONTHS_PER_YEAR) - 1
