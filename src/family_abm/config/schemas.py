"""Modèles Pydantic v2 de la configuration (03).

Tous les modèles sont ``frozen=True`` et ``extra="forbid"`` : une clé inconnue est une
faute de frappe, refusée au chargement. Les bornes déclarées ici sont **structurelles**
(une probabilité est dans [0, 1], un montant est ≥ 0) ; les valeurs du modèle vivent dans
``config/*.yaml``. Chaque bloc peut porter ``provenance`` et ``source`` (03 §1).

``SimulationConfig`` est l'arbre résolu unique : les clés de ``simulation.yaml`` à la
racine, puis un espace de noms par fichier (``profiles``, ``household_rules``, ``needs``,
``economic_params``). Un chemin pointé de surcharge s'y applique donc tel quel (03 §1, B1).
"""

import math
from enum import StrEnum
from typing import Annotated, Any, Literal, Self, get_args

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
    model_validator,
)

from family_abm.core.types import (
    WEIGHT_SUM_TOLERANCE,
    AllocationMode,
    Capability,
    DiscountingMode,
    EmploymentStatus,
    NeedKind,
    Tier,
)

# --- types de base


class Provenance(StrEnum):
    PLACEHOLDER = "PLACEHOLDER"
    DIRECT = "DIRECT"
    CALIBRATED = "CALIBRATED"
    FIX_LIT = "FIX_LIT"
    EXPLORED = "EXPLORED"


class Treatment(StrEnum):
    """Traitement d'un paramètre dans le registre (03 §12)."""

    CALIBRATE = "CALIBRATE"
    FIX = "FIX"
    FIX_LIT = "FIX_LIT"
    EXPLORE = "EXPLORE"
    DIRECT = "DIRECT"


def _parse_tier(value: Any) -> Any:
    if isinstance(value, str) and not isinstance(value, Tier):
        try:
            return Tier[value.upper()]
        except KeyError:
            names = ", ".join(t.name.lower() for t in Tier)
            raise ValueError(f"palier inconnu {value!r} (attendu : {names})") from None
    return value


TierName = Annotated[
    Tier,
    BeforeValidator(_parse_tier),
    PlainSerializer(lambda t: t.name.lower(), return_type=str),
]
"""Palier écrit en minuscules dans le YAML (``essential``) et dans l'empreinte."""

ModelVersion = Literal["v1", "v2", "v3"]
MODEL_VERSIONS: tuple[str, ...] = get_args(ModelVersion)
"""Versions du modèle, dans l'ordre (S8)."""

Probability = Annotated[float, Field(ge=0.0, le=1.0)]
Share = Annotated[float, Field(ge=0.0, le=1.0)]
Amount = Annotated[float, Field(ge=0.0)]
Age = Annotated[float, Field(ge=0.0)]
AgeTable = tuple[tuple[Age, float], ...]
"""Table ``[[âge, valeur], …]`` à âges strictement croissants, constante par morceaux (03 §6)."""


def lookup_by_age(table: AgeTable, age_years: float) -> float:
    """Constante par morceaux (10 §2) : valeur du dernier âge ≤ ``age_years`` ; 0 avant le
    premier seuil."""
    value = 0.0
    for age, entry in table:
        if age > age_years:
            break
        value = entry
    return value


def _check_age_table(table: AgeTable, *, probabilities: bool = False) -> AgeTable:
    if not table:
        raise ValueError("table par âge vide")
    ages = [age for age, _ in table]
    if any(later <= earlier for earlier, later in zip(ages, ages[1:], strict=False)):
        raise ValueError(f"âges non strictement croissants : {ages}")
    values = [value for _, value in table]
    if any(value < 0 for value in values):
        raise ValueError(f"valeur négative dans la table : {values}")
    if probabilities and any(value > 1 for value in values):
        raise ValueError(f"probabilité > 1 dans la table : {values}")
    return table


def _unique[T](items: tuple[T, ...]) -> tuple[T, ...]:
    if len(set(items)) != len(items):
        raise ValueError(f"doublons : {list(items)}")
    return items


class ConfigModel(BaseModel):
    """Base : immuable, clés inconnues refusées, provenance optionnelle (03 §1)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", populate_by_name=True, allow_inf_nan=False
    )

    provenance: Provenance | None = None
    source: str | None = None


class Toggle(ConfigModel):
    enabled: bool


# --- simulation.yaml (03 §2)


class ModelSettings(ConfigModel):
    version: ModelVersion


class DemographySettings(ConfigModel):
    mode: Literal["fixed_cohort"]  # Q5 — seule valeur implémentée


class DataSettings(ConfigModel):
    # Ici ``source`` est la source de données (Q6), pas la métadonnée de provenance.
    source: Literal["synthetic", "nta_profiles", "ehcvm"]


class LoopsSettings(ConfigModel):
    b2: Toggle
    b3: Toggle


class CognitionSettings(ConfigModel):
    bdi: Toggle
    memory: Toggle
    discounting: Toggle


class ChecksSettings(ConfigModel):
    invariants: bool
    invariant_run_sample_rate: float = Field(gt=0.0, le=1.0)
    invariant_period_unsampled: int = Field(ge=1)

    @field_validator("invariants")
    @classmethod
    def _never_disabled(cls, value: bool) -> bool:
        if not value:
            raise ValueError(
                "les invariants ne peuvent pas être désactivés (règle 5 ; 03 §2 : "
                "réduire invariant_run_sample_rate après la porte V1)"
            )
        return value


class CollectSettings(ConfigModel):
    person_steps: bool
    household_steps: bool
    ledger: bool
    decisions: Literal["all", "sample", "none"]
    decisions_sample_households: int = Field(ge=0)
    nta: bool


class OutputSettings(ConfigModel):
    dir: str
    collect: CollectSettings


# --- cognitive_profiles.yaml (03 §3)


def _since(version: str) -> Any:
    """Marque un paramètre de profil actif seulement à partir de ``version`` (03 §3)."""
    return {"active_since": version}


class AspirationAdapt(ConfigModel):
    up: float = Field(ge=0.0)
    down: float = Field(ge=0.0)
    min: Share
    max: Share

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) > max ({self.max})")
        return self


class MemoryParams(ConfigModel):
    capacity: int = Field(ge=0)
    decay: float = Field(ge=0.0)
    retrieval_threshold: float


class DiscountingParams(ConfigModel):
    mode: DiscountingMode
    beta: float = Field(gt=0.0, le=1.0)
    delta: float = Field(gt=0.0, le=1.0)


class RiskParams(ConfigModel):
    lambda_: float = Field(alias="lambda", gt=0.0)
    alpha: float = Field(gt=0.0, le=1.0)


class CognitiveProfile(ConfigModel):
    """Un profil = un jeu de paramètres ; aucun code ne connaît les noms de profils (03 §3)."""

    capabilities: tuple[Capability, ...]
    max_alternatives: int = Field(ge=1)
    planning_horizon: int = Field(ge=0)
    aspiration_init: Share
    aspiration_adapt: AspirationAdapt = Field(json_schema_extra=_since("v2"))
    impulsivity: Probability
    memory: MemoryParams = Field(json_schema_extra=_since("v2"))
    intention_commitment: Share = Field(json_schema_extra=_since("v2"))
    discounting: DiscountingParams = Field(json_schema_extra=_since("v2"))
    risk: RiskParams = Field(json_schema_extra=_since("v3"))
    stress_sensitivity: Share = Field(json_schema_extra=_since("v3"))
    attended_needs: tuple[NeedKind, ...]

    @field_validator("capabilities", "attended_needs")
    @classmethod
    def _no_duplicates[T](cls, items: tuple[T, ...]) -> tuple[T, ...]:
        return _unique(items)


_PROFILE_META_FIELDS = frozenset({"provenance", "source"})


def active_profile_fields(version: str) -> frozenset[str]:
    """Paramètres de profil actifs dans ``version`` ; les autres sont lus sans effet (03 §3)."""
    level = MODEL_VERSIONS.index(version)
    active = set()
    for name, info in CognitiveProfile.model_fields.items():
        if name in _PROFILE_META_FIELDS:
            continue
        extra = info.json_schema_extra
        since = extra.get("active_since", MODEL_VERSIONS[0]) if isinstance(extra, dict) else None
        if since is None or MODEL_VERSIONS.index(str(since)) <= level:
            active.add(name)
    return frozenset(active)


# --- household_rules.yaml (03 §4)


class Member(ConfigModel):
    key: str
    profile: str
    age: Age
    employment: EmploymentStatus
    wage_key: str | None = None


class InitialAssets(ConfigModel):
    pot: Amount
    savings: Amount
    loan: Amount


class BaselineHousehold(ConfigModel):
    members: tuple[Member, ...] = Field(min_length=1)
    initial_assets: InitialAssets
    head: str
    ownership: dict[str, Share]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        keys = [m.key for m in self.members]
        _unique(tuple(keys))
        if self.head not in keys:
            raise ValueError(f"head {self.head!r} n'est pas un membre ({keys})")
        unknown = set(self.ownership) - set(keys)
        if unknown:
            raise ValueError(f"ownership : membres inconnus {sorted(unknown)}")
        total = math.fsum(self.ownership.values())
        if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
            raise ValueError(f"Σω = {total!r} ≠ 1 (INV-10)")
        return self


class ProfileTransition(ConfigModel):
    from_: str = Field(alias="from")
    to: str
    at_age: Age


class VariableWeights(ConfigModel):
    gamma: float = Field(ge=0.0)


class UnitaryRule(ConfigModel):
    priority_owner: str


class AllocationRules(ConfigModel):
    mode: AllocationMode
    weights: dict[str, float]
    variable_weights: VariableWeights
    unitary: UnitaryRule
    tier_order: tuple[TierName, ...]
    rationing: Literal["weighted_proportional"]

    @field_validator("weights")
    @classmethod
    def _normalized(cls, weights: dict[str, float]) -> dict[str, float]:
        """Poids normalisés au chargement (03 §4, INV-10)."""
        if any(w < 0 for w in weights.values()):
            raise ValueError(f"poids négatif : {weights}")
        total = math.fsum(weights.values())
        if total <= 0:
            raise ValueError("la somme des poids doit être > 0")
        return {key: w / total for key, w in weights.items()}

    @field_validator("tier_order")
    @classmethod
    def _all_tiers_once(cls, order: tuple[Tier, ...]) -> tuple[Tier, ...]:
        if sorted(order) != sorted(Tier):
            raise ValueError("tier_order doit contenir chaque palier exactement une fois")
        return order


class CreditRules(ConfigModel):
    limit_months_income: float = Field(ge=0.0)
    annual_rate: float = Field(ge=0.0)
    min_repayment_share: Share
    borrow_for_tiers: tuple[TierName, ...]


class SavingsRules(ConfigModel):
    annual_rate: float = Field(ge=0.0)
    target_buffer_months: float = Field(ge=0.0)


class SeparateSpheres(ConfigModel):
    enabled: bool
    stress_threshold: Share
    enter_months: int = Field(ge=1)
    exit_months: int = Field(ge=1)
    hysteresis: float = Field(ge=0.0)
    spheres: dict[str, tuple[NeedKind, ...]]
    pooling_in_regime: Share


class LeaveRule(ConfigModel):
    min_age: Age
    min_months_employed: int = Field(ge=0)
    remittance_share: Share


class HouseholdRules(ConfigModel):
    baseline_household: BaselineHousehold
    default_pooling_key: str  # clé de ``pooling`` des membres qui n'y figurent pas (J1)
    pooling: dict[str, Share]
    profile_transitions: tuple[ProfileTransition, ...]
    allocation: AllocationRules
    credit: CreditRules
    savings: SavingsRules
    separate_spheres: SeparateSpheres
    young_adult_can_leave: bool
    leave_rule: LeaveRule

    @field_validator("profile_transitions")
    @classmethod
    def _deterministic_and_acyclic(
        cls, transitions: tuple[ProfileTransition, ...]
    ) -> tuple[ProfileTransition, ...]:
        """Au plus une règle par profil de départ, et aucun cycle (sinon le vieillissement
        ne termine pas)."""
        successor: dict[str, str] = {}
        for rule in transitions:
            if rule.from_ in successor:
                raise ValueError(f"plusieurs transitions depuis le profil {rule.from_!r}")
            successor[rule.from_] = rule.to
        for start in successor:
            seen, current = {start}, successor[start]
            while current in successor:
                if current in seen:
                    raise ValueError(f"cycle de transitions de profil passant par {current!r}")
                seen.add(current)
                current = successor[current]
        return transitions

    @model_validator(mode="after")
    def _member_references(self) -> Self:
        keys = {m.key for m in self.baseline_household.members}
        weights = set(self.allocation.weights)
        if weights != keys:
            raise ValueError(
                f"allocation.weights : manquants {sorted(keys - weights)}, "
                f"inconnus {sorted(weights - keys)}"
            )
        if self.default_pooling_key not in self.pooling:
            raise ValueError(
                f"default_pooling_key {self.default_pooling_key!r} absente de pooling "
                f"({sorted(self.pooling)})"
            )
        for label, refs in (
            ("pooling", set(self.pooling)),
            ("separate_spheres.spheres", set(self.separate_spheres.spheres)),
            ("allocation.unitary.priority_owner", {self.allocation.unitary.priority_owner}),
        ):
            unknown = refs - keys
            if unknown:
                raise ValueError(f"{label} : membres inconnus {sorted(unknown)}")
        return self


# --- needs.yaml (03 §5)


class NeedSpec(ConfigModel):
    tier: TierName
    divisible: bool
    persistence: Share
    active_ages: tuple[Age, Age]

    @field_validator("active_ages")
    @classmethod
    def _ordered(cls, ages: tuple[float, float]) -> tuple[float, float]:
        if ages[0] > ages[1]:
            raise ValueError(f"active_ages non ordonné : {ages}")
        return ages


class FoodNeed(NeedSpec):
    reduced_share: Share
    amount_min_share: Share


class HealthNeed(NeedSpec):
    reduced_share: Share
    amount_min_share: Share
    sat_untreated_factor: Share


class RestNeed(NeedSpec):
    monetary: Literal[False]
    labor_threshold: float = Field(ge=0.0)
    labor_slope: float = Field(ge=0.0)


class SecurityNeed(NeedSpec):
    monetary: Literal[True]
    saving_horizons_months: tuple[Annotated[int, Field(ge=1)], ...] = Field(min_length=1)


class Needs(ConfigModel):
    """Les six besoins de ``NeedKind`` ; pas de clé racine ``needs:`` dans le fichier (B1)."""

    food: FoodNeed
    health: HealthNeed
    education: NeedSpec
    housing: NeedSpec
    rest: RestNeed
    security: SecurityNeed


# --- economic_params.yaml (03 §6)


class EmploymentParams(ConfigModel):
    min_work_age: Age


class FormalShocks(ConfigModel):
    p_loss_monthly: Probability
    p_find_monthly: Probability


class InformalShocks(FormalShocks):
    volatility: float = Field(ge=0.0)


class IncomeShocks(ConfigModel):
    formal: FormalShocks
    informal: InformalShocks
    find_formal_share: Share


class TaxParams(ConfigModel):
    formal_rate: Share
    informal_rate: Share


class PriceParams(ConfigModel):
    inflation_annual: float = Field(gt=-1.0)


class ByAgeTable(ConfigModel):
    by_age: AgeTable

    @field_validator("by_age")
    @classmethod
    def _table(cls, table: AgeTable) -> AgeTable:
        return _check_age_table(table)


class HealthRequirements(ConfigModel):
    routine_by_age: AgeTable
    episode_cost: AgeTable

    @field_validator("routine_by_age", "episode_cost")
    @classmethod
    def _tables(cls, table: AgeTable) -> AgeTable:
        return _check_age_table(table)


class ConsumptionRequirements(ConfigModel):
    food: ByAgeTable
    health: HealthRequirements
    education: ByAgeTable
    rest: ByAgeTable


class EquivalenceWeights(ConfigModel):
    first_adult: float = Field(gt=0.0)
    other_adult: float = Field(ge=0.0)
    child: float = Field(ge=0.0)
    adult_age: Age


class HousingParams(ConfigModel):
    monthly_cost_household: Amount
    equivalence_scale: Literal["oecd_modified"]
    equivalence_weights: EquivalenceWeights


class InkindByAge(ConfigModel):
    education: AgeTable
    health: AgeTable

    @field_validator("education", "health")
    @classmethod
    def _tables(cls, table: AgeTable) -> AgeTable:
        return _check_age_table(table)


class CashTransfer(ConfigModel):
    from_step: int = Field(ge=0)
    to_step: int | None = None
    per_child_under: Age | None = None
    amount: Amount
    to: Literal["pot", "wallet"]

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.to_step is not None and self.to_step < self.from_step:
            raise ValueError(f"to_step ({self.to_step}) < from_step ({self.from_step})")
        return self


class PublicParams(ConfigModel):
    inkind_by_age: InkindByAge
    cash_transfers: tuple[CashTransfer, ...]


class EpisodeSeverity(ConfigModel):
    mean: Share
    sd: float = Field(ge=0.0)
    min: Share
    max: Share

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if not self.min <= self.mean <= self.max:
            raise ValueError(f"il faut min ≤ mean ≤ max ({self.min}, {self.mean}, {self.max})")
        return self


class HealthParams(ConfigModel):
    p_episode_monthly_by_age: AgeTable
    episode_severity: EpisodeSeverity
    recovery_with_care: Share
    recovery_without_care: Share
    natural_recovery: Share
    recovery_tolerance: Share
    max_episode_months: int = Field(ge=1)
    health_min_for_work: float = Field(ge=0.0, lt=1.0)  # h_min < 1 : capacité définie
    care_paid_by: Literal["household", "gov"]

    @field_validator("p_episode_monthly_by_age")
    @classmethod
    def _table(cls, table: AgeTable) -> AgeTable:
        return _check_age_table(table, probabilities=True)


class ExitAge(ConfigModel):
    secondary: Age
    tertiary: Age


class SchoolingParams(ConfigModel):
    entry_age: Age
    exit_age: ExitAge
    drop_after_refused_months: int = Field(ge=1)


class ParameterProvenance(ConfigModel):
    """Provenance d'une valeur isolée, quand le bloc qui la contient a une autre provenance."""

    provenance: Provenance
    source: str
    note: str | None = None


class EconomicParams(ConfigModel):
    """Paramètres économiques (03 §6)."""

    currency: str
    wage_scale: float = Field(gt=0.0)
    employment: EmploymentParams
    wages: dict[str, Amount]
    default_wage_key: str  # clé de ``wages`` des membres sans ``wage_key`` (J1)
    wage_growth_annual: float = Field(gt=-1.0)
    income_shocks: IncomeShocks
    tax: TaxParams
    prices: PriceParams
    consumption_requirements: ConsumptionRequirements
    housing: HousingParams
    public: PublicParams
    health: HealthParams
    schooling: SchoolingParams
    poverty_line_per_eq: float = Field(gt=0.0)
    poverty_line_per_capita_annual: float = Field(gt=0.0)  # taux de pauvreté par tête, P6 (J2)
    provenance_by_path: dict[str, ParameterProvenance] = Field(default_factory=dict)  # J3

    @model_validator(mode="after")
    def _default_wage_key_exists(self) -> Self:
        if self.default_wage_key not in self.wages:
            raise ValueError(
                f"default_wage_key {self.default_wage_key!r} absente de wages "
                f"({sorted(self.wages)})"
            )
        return self


# --- configuration résolue


class SimulationConfig(ConfigModel):
    """Configuration résolue d'un run (03) : clés de ``simulation.yaml`` + espaces de noms."""

    model: ModelSettings
    horizon_months: int = Field(ge=1)
    seed: int = Field(ge=0)
    demography: DemographySettings
    data: DataSettings
    loops: LoopsSettings
    cognition: CognitionSettings
    checks: ChecksSettings
    output: OutputSettings
    profiles: dict[str, CognitiveProfile] = Field(min_length=1)
    household_rules: HouseholdRules
    needs: Needs
    economic_params: EconomicParams

    @model_validator(mode="after")
    def _cross_references(self) -> Self:
        rules = self.household_rules
        for member in rules.baseline_household.members:
            if member.profile not in self.profiles:
                raise ValueError(
                    f"membre {member.key!r} : profil inconnu {member.profile!r} "
                    f"(profils : {sorted(self.profiles)})"
                )
            if member.wage_key is not None and member.wage_key not in self.economic_params.wages:
                raise ValueError(
                    f"membre {member.key!r} : wage_key inconnue {member.wage_key!r} "
                    f"(economic_params.wages : {sorted(self.economic_params.wages)})"
                )
        for transition in rules.profile_transitions:
            for name in (transition.from_, transition.to):
                if name not in self.profiles:
                    raise ValueError(f"profile_transitions : profil inconnu {name!r}")
        for member in rules.baseline_household.members:
            for transition in rules.profile_transitions:
                if transition.from_ == member.profile and member.age >= transition.at_age:
                    raise ValueError(
                        f"membre {member.key!r} : {member.age} ans, mais le profil "
                        f"{member.profile!r} cède la place à {transition.to!r} à "
                        f"{transition.at_age} ans"
                    )
        return self


# --- registre (03 §12)


class ParameterSpec(ConfigModel):
    path: str
    bounds: tuple[float, float] | None = None
    scale_bounds: tuple[float, float] | None = None
    treatment: Treatment
    sa: bool
    treatment_variable_of: tuple[str, ...] = ()
    per_profile: bool = False

    @model_validator(mode="after")
    def _one_kind_of_bounds(self) -> Self:
        if (self.bounds is None) == (self.scale_bounds is None):
            raise ValueError(f"{self.path} : exactement un de bounds / scale_bounds")
        bounds = self.bounds if self.bounds is not None else self.scale_bounds
        assert bounds is not None
        low, high = bounds
        if low > high:
            raise ValueError(f"{self.path} : borne basse {low} > borne haute {high}")
        return self


class ParametersRegistry(ConfigModel):
    parameters: tuple[ParameterSpec, ...]

    @model_validator(mode="after")
    def _unique_paths(self) -> Self:
        _unique(tuple(p.path for p in self.parameters))
        return self
