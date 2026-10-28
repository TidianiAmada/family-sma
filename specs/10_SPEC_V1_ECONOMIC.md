# 10 — Spécification V1 : baseline économique

> **Objectif scientifique** (feuille de route §11) : établir qu'un modèle multi-agents de foyer produit des flux économiquement cohérents et reproduit la signature du déficit du cycle de vie (LCD). **Rien de plus.**
> **Pré-requis :** `00`–`04` de ce dossier ; ODD-V1 (`odd/ODD_v1_economic.md`) — règle dure : aucun sous-modèle n'est codé avant d'y être décrit.
> **Boucle active :** B1 (économique) uniquement.

---

## 0. Périmètre

| Inclus | Spécification |
|---|---|
| 6 `PersonAgent` | père, mère, jeune adulte, adolescent, enfant, bébé — **une seule classe** |
| `CognitiveProfile` | chargé depuis YAML ; en V1 n'agissent que `capabilities`, `max_alternatives`, `planning_horizon`, `attended_needs`, `aspiration_init`, `impulsivity` |
| États | `EconomicState`, `PhysicalState`, `NeedsState` (+ `CognitiveState.aspiration` fixe) |
| Besoins | 6 besoins (`needs.yaml`) à seuil de satisfaction |
| Décision | `SatisficingEngine` sans croyances, mémoire ni plans |
| Actions | travailler (offre constante), consommer, épargner, se soigner, étudier, se reposer |
| `HouseholdAgent` | `allocate()` en mode `fixed_weights` (et `unitary` pour les tests), budget commun, dette collective |
| NTA | `NTACalculator`, attribution ω, imputation ONU, profils par âge |
| `Ledger` + invariants | double entrée, échec dur à chaque pas |
| Collecte | tables `04_DATA_MODEL` §2.1–2.11 |
| Reproductibilité | `RngStreams`, même seed ⇒ trajectoire identique |
| Scénarios | `baseline`, `job_loss`, `illness`, `family_allowance`, `free_care`, `economic_shock` (événements exogènes ; pas de réponse cognitive) |

**Exclus explicitement :** croyances/désirs/intentions · mémoire · plans · adaptation de l'aspiration · β-δ · appraisal, émotions · CPT · poids variables · sphères séparées · départ du jeune adulte · population de foyers (le code accepte `n_households > 1` mais la V1 n'est validée que pour 1).

**Commande de référence :** `uv run family-abm run --scenario baseline --seed 42` → `experiments/results/runs/run_id=…/`.

---

## 1. Fichiers à créer en V1

| Fichier | Contenu V1 |
|---|---|
| `core/types.py` | enums de `02` §2 (toutes, y compris V2/V3, pour figer les schémas) ; `Money = Decimal` ; `q(x) -> Decimal` (quantize 0.01, `ROUND_HALF_EVEN`) |
| `core/rng.py` | `RngStreams` (`01` §7) |
| `core/errors.py` | `ConfigError`, `LedgerError`, `InvariantViolation(inv_id, step, household_id, detail)`, `AllocationError` |
| `config/schemas.py`, `config/loader.py` | modèles Pydantic de `03` ; `load_config(paths, overrides) -> SimulationConfig` ; `config_hash()` ; `is_illustrative()` |
| `agents/states.py` | dataclasses `02` §4 |
| `agents/person.py` | `PersonAgent` |
| `agents/household.py` | `HouseholdAgent` |
| `agents/allocation.py` | `allocate()` pure |
| `decision/engine.py`, `alternatives.py`, `satisficing.py` | `DecisionEngine` (Protocol), `Percept`, `SatisficingEngine` |
| `economy/accounts.py`, `ledger.py`, `actions.py`, `labor.py`, `credit.py`, `prices.py`, `public.py` | |
| `health/health.py` | |
| `nta/accounts.py`, `attribution.py`, `imputation.py`, `profiles.py`, `invariants.py` | |
| `model/family_model.py`, `scheduler.py`, `events.py`, `collectors.py` | |
| `io/parquet.py`, `io/catalog.py` | |
| `analysis/indicators.py`, `analysis/figures.py` (figures E1) | |
| `__main__.py` | CLI Typer : `run`, `gate`, `experiment` (stub E1), `figures` |

---

## 2. Horloge, indices et vieillissement

```python
# economy/prices.py
def price_index(step: int, cfg: EconomicParams, shocks: PriceShockLog) -> Decimal:
    """P_t = (1 + π)^(t/12) × Π(1 + choc) pour les chocs de prix déjà survenus."""
def wage_index(step: int, cfg: EconomicParams) -> Decimal:
    """W_t = (1 + g)^floor(t/12)  — revalorisation annuelle."""
def monthly_rate(annual: float) -> Decimal:   # (1 + r)^(1/12) − 1
```

Toute valeur monétaire de besoin, de logement, de soins, de frais de scolarité et de consommation publique est multipliée par `P_t` ; tout salaire par `W_t`.

**Vieillissement** (fin du pas, **après** le calcul NTA, les invariants et la collecte — G1 ; les tables du pas portent donc l'âge en vigueur pendant le pas) : `age_months += 1`. **Transition de profil** : si `age_months` franchit `at_age × 12` d'une règle `profile_transitions` dont `from == profile_key` → `profile_key = to`, `aspiration[k] = profiles[to].aspiration_init` pour tout k, `needs.active` recalculé (`active_ages`), événement `profile_transition`. Le `role` (étiquette) ne change jamais.

```python
def lookup_by_age(table: list[tuple[float, float]], age_years: float) -> float:
    """Constante par morceaux : valeur du dernier âge ≤ age_years ; 0 si age < premier seuil."""
```

---

## 3. Sous-modèle Travail, emploi et chocs (`economy/labor.py`)

**Revenu brut du mois** (personne employée) :

```
Yl_i,t = wage_monthly_i × W_t × labor_supply_i × labor_capacity_i × m_i,t
m_i,t = 1                                   si EMPLOYED_FORMAL
m_i,t ~ LogNormal(μ = −σ²/2, σ = volatility) si EMPLOYED_INFORMAL   (E[m] = 1 ; flux rng "income_shocks")
Yl = 0 sinon
```

`labor_supply = 1.0` constant en V1 pour tout employé. `labor_capacity` : `02` §4.2.

**Transitions d'emploi** (début du Temps 2, avant le versement ; flux `employment`) :

| État | Transition |
|---|---|
| `EMPLOYED_FORMAL` | `UNEMPLOYED` avec p = `income_shocks.formal.p_loss_monthly` |
| `EMPLOYED_INFORMAL` | `UNEMPLOYED` avec p = `income_shocks.informal.p_loss_monthly` |
| `UNEMPLOYED` | trouve un emploi avec p = `p_find_monthly` du **secteur du dernier emploi** (jamais employé ⇒ informel) ; l'emploi trouvé est formel avec probabilité `find_formal_share`, sinon informel |
| `STUDENT` | `UNEMPLOYED` quand `SchoolStatus → COMPLETED` (âge ≥ `schooling.exit_age.tertiary`) ou `DROPPED_OUT` et âge ≥ `economic_params.employment.min_work_age` |
| `INACTIVE` | `STUDENT` à l'inscription scolaire |

Salaire (initial ou d'un nouvel emploi) : `wages[wage_key] × economic_params.wage_scale` (défaut 1,0 ; facteur de E6/E8) ; membre sans `wage_key` ⇒ `wages.young_adult`. `months_unemployed` incrémenté chaque mois en `UNEMPLOYED`. Événements `job_loss` / `job_found` (`origin = endogenous`). L'événement de scénario `job_loss` force la transition au pas indiqué (`origin = scenario`).

Une personne n'est éligible au travail que si `Capability.WORK ∈ capabilities` ; sinon `Yl = 0` quel que soit l'état.

**Impôt** : `tax_i,t = formal_rate × Yl_i,t` si formel, `informal_rate × Yl` sinon ; prélevé à la source (écriture `TAX` immédiatement après `LABOR_INCOME`).

**Mise en commun** : `pool_i,t = pooling[member_key] × (Yl − tax)` (clé absente ⇒ `pooling.young_adult`) → écriture `POOLING` wallet → pot. Le reste demeure dans le portefeuille.

---

## 4. Sous-modèle Besoins (`agents/states.py` + `economy/actions.py`)

Pour chaque besoin actif k de la personne i :

```
level_k,t = ρ_k · level_k,t−1 + (1 − ρ_k) · sat_k,t          ρ_k = needs.<k>.persistence
```

| Besoin | Exigence mensuelle r_k (× P_t) | Satisfaction sat_k,t |
|---|---|---|
| FOOD | `consumption_requirements.food.by_age` | `min(1, spent_food / r_food)` |
| HEALTH | routine : `health.routine_by_age` ; épisode : `health.episode_cost` | non malade : `min(1, spent_routine / r_routine)` ; malade : `1` si soin d'épisode obtenu ce pas ou un pas antérieur de l'épisode (`cared = True`), sinon `needs.health.sat_untreated_factor × min(1, spent_routine/r_routine)` |
| EDUCATION | `education.by_age` si `ENROLLED` | `1` si frais intégralement payés, `0` sinon (indivisible) |
| HOUSING | part `e_i / Σe` du coût foyer (échelle OCDE modifiée) | `paid_housing_i / share_i` |
| REST | non monétaire | `clip(1 − labor_slope·max(0, labor_supply − labor_threshold) − fatigue, 0, 1)` avec `needs.rest.labor_slope` (0,6) et `needs.rest.labor_threshold` (0,8) ; V1 : `fatigue = 0` |
| SECURITY | — | `min(1, savings / (target_buffer_months × spend_avg_12m))` — **valeur du foyer**, identique pour tous les membres où le besoin est actif |

`spend_avg_12m` = moyenne des `consumption_private` du foyer sur les 12 derniers pas disponibles ; au pas 0 : `housing + Σ_i (r_food + r_routine + r_edu si inscrit)`.

`level` initial = 1.0 pour tous les besoins actifs, sauf SECURITY = `sat_security,0`.

**Échelle OCDE modifiée** (`economic_params.housing.equivalence_weights`) : premier adulte (le `head`) = `first_adult` (1) ; autres membres ≥ `adult_age` (14 ans) = `other_adult` (0,5) ; plus jeunes = `child` (0,3). `eq_size = Σ e_i`.

---

## 5. Sous-modèle Santé (`health/health.py`) — début du Temps 1, flux `health`

```python
def update_health(p: PhysicalState, age_years: float, cfg: HealthParams, rng, P_t) -> Event | None:
    if not p.sick:
        if rng.random() < lookup_by_age(cfg.p_episode_monthly_by_age, age_years):
            sev = clip(rng.normal(cfg.episode_severity.mean, cfg.episode_severity.sd),
                       cfg.episode_severity.min, cfg.episode_severity.max)
            p.health_pre_episode = p.health
            p.health = max(0.0, p.health - sev)
            p.sick, p.cared, p.episode_months = True, False, 0
            p.care_need = lookup_by_age(cfg.episode_cost, age_years) * P_t   # demandé UNE fois
            return Event("health_episode", payload={"severity": sev})
        p.health = min(1.0, p.health + cfg.natural_recovery)   # récupération naturelle hors épisode
    else:
        p.episode_months += 1
        p.health = min(1.0, p.health + (cfg.recovery_with_care if p.cared else cfg.recovery_without_care))
        if (p.health >= p.health_pre_episode - cfg.recovery_tolerance
                or p.episode_months >= cfg.max_episode_months):
            p.sick, p.care_need = False, 0;  return Event("recovered")
    p.labor_capacity = clip((p.health - cfg.health_min_for_work) / (1 - cfg.health_min_for_work), 0, 1)
```

La demande d'épisode (`SEEK_CARE`, ESSENTIAL, indivisible, `care_need`) n'est émise **qu'au premier mois** de l'épisode ; si elle est refusée, la personne reste `cared = False` pour tout l'épisode. Scénario `free_care` : le soin d'épisode et la routine sont payés par `PUBLIC_INKIND` (aucune demande au foyer, `cared = True`). Scénario `illness` : épisode forcé (gravité et durée du scénario ; `episode_months` max = `duration`).

Champs ajoutés à `PhysicalState` (détails d'implémentation, non exportés) : `health_pre_episode`, `cared`, `episode_months`.

---

## 6. Sous-modèle Scolarité

- `NOT_SCHOOL_AGE → ENROLLED` au premier mois où `age ≥ schooling.entry_age` (frais demandés dès ce mois).
- `ENROLLED` : demande mensuelle EDUCATION indivisible `r_edu(âge)·P_t`. Compteur `refused_edu_months` : +1 si refusée, remis à 0 si accordée. `≥ drop_after_refused_months` ⇒ `DROPPED_OUT` (événement `school_dropout`).
- Âge `≥ exit_age.secondary` : poursuite automatique vers le supérieur en V1 (la table `by_age` passe au tarif supérieur) — la décision de poursuite est V3 (`KEEP_IN_SCHOOL`).
- Âge `≥ exit_age.tertiary` ⇒ `COMPLETED`, et `employment: STUDENT → UNEMPLOYED`.
- Le jeune adulte de référence (20 ans, `student`) est `ENROLLED` à t0.
- `PUBLIC_INKIND` éducation versé chaque mois pour tout `ENROLLED` (indépendamment des frais privés).

---

## 7. Moteur de décision V1 (`decision/`)

### 7.1 Interface

```python
# decision/engine.py
@dataclass(frozen=True, slots=True)
class Percept:
    step: int
    person_id: PersonId
    age_years: float
    needs_level: Mapping[NeedKind, float]
    active_needs: frozenset[NeedKind]
    requirements: Mapping[NeedKind, Money]        # r_k(âge)·P_t (épisode de soin inclus si 1er mois)
    amount_min: Mapping[NeedKind, Money]
    expected_grant_ratio: Mapping[NeedKind, float]   # ê_k ; V1 : ratio accordé au pas précédent, 1.0 au départ
    envelope: Money | None                        # E_i ; None au pas 0
    habitual: Mapping[NeedKind, Money] | None     # panier choisi au pas précédent
    savings_gap: Money                            # (cible − épargne) du foyer, ≥ 0
    ownership_share: float                        # ω_i
    sick_first_month: bool
    school_enrolled: bool

class DecisionEngine(Protocol):
    def decide(self, percept: Percept, profile: EffectiveCognitiveProfile,
               base: CognitiveProfile, aspiration: Mapping[NeedKind, float],
               rng: np.random.Generator) -> DemandSet: ...
```

En V1, `EffectiveCognitiveProfile` est construit tel quel depuis le `CognitiveProfile` (`aspiration_scale = 1`, pas de modulation).

### 7.2 Besoins demandables

Un besoin k entre dans les paniers de i ssi : k ∈ `active_needs`, k est monétaire, son palier n'est pas `COMMITMENT` (logement = engagement du foyer, pas de choix individuel), et la capacité requise est présente (`CONSUME` pour FOOD/HEALTH-routine, `SEEK_CARE` pour l'épisode, `STUDY` + `school_enrolled` pour EDUCATION, `SAVE` et `ω_i > 0` pour SECURITY).

### 7.3 Génération des alternatives (`decision/alternatives.py`)

```python
# Tous les coefficients viennent de needs.yaml (B2) : reduced_share, amount_min_share, saving_horizons_months
def amount_min(k) -> Money:   # détail tranché
    divisible   ⇒ needs.<k>.amount_min_share · r_k     (FOOD : 0,5 ; HEALTH routine : 0)
    indivisible ⇒ r_k                                  (HEALTH épisode, EDUCATION)
    SECURITY    ⇒ 0

def level_options(k) -> list[Money]:
    indivisible ⇒ [r_k, 0]
    SECURITY    ⇒ [ω_i·gap/h for h in needs.security.saving_horizons_months] + [0]   # défaut [12, 24]
    sinon       ⇒ [r_k, needs.<k>.reduced_share·r_k, amount_min_k]                  # dédoublonnés

def generate(percept, profile, attended: list[NeedKind]) -> Iterator[Basket]:
    dims = [k for k in attended if demandable(k)]          # ordre = attended_needs
    candidates = itertools.product(*(level_options(k) for k in dims))  # ordre lexicographique : plein d'abord
    ordered = []
    if percept.habitual: ordered.append(habitual)           # saillance : l'habitude d'abord
    ordered += candidates                                    # sans doublon
    if profile.planning_horizon >= 1 and percept.envelope is not None:
        # partition stable : d'abord les paniers dont le total ≤ enveloppe attendue
        ordered = [b for b in ordered if total(b) <= envelope] + [b for b in ordered if total(b) > envelope]
    yield from ordered[: profile.max_alternatives]           # troncature = rationalité limitée
```

`envelope E_i,t = Σ accordé à i au pas t−1 + solde du portefeuille` (pas 0 : `None`). Un agent réactif (`H = 0`) ignore l'enveloppe.

### 7.4 Projection et score

Pour un panier `a` et un besoin k, sur `t = 0..H` (`H = planning_horizon`) :

```
ê_k(a) = 1                    si total(a) ≤ E_i (ou E_i = None)
       = ê_k (ratio passé)    sinon
ŝ_k(a) = min(1, a_k · ê_k(a) / r_k)          (besoin monétaire ; SECURITY : savings projetée, voir ci-dessous)
n̂_k,0 = ρ_k·level_k + (1 − ρ_k)·ŝ_k(a) ;    n̂_k,t = ρ_k·n̂_k,t−1 + (1 − ρ_k)·ŝ_k(a)
s_k(a) = Σ_t D(t)·n̂_k,t / Σ_t D(t)           V1 : D(t) = 1
```

SECURITY : `ŝ_t = min(1, (savings + (t+1)·a_SEC_total·ê) / target)` où `a_SEC_total = a_SEC / ω_i` (hypothèse : l'autre propriétaire épargne symétriquement). Besoins non monétaires ou non demandables mais attendus (HOUSING, REST) : `ŝ = sat` du pas précédent (constant sur l'horizon).

### 7.5 Règle de choix

```python
def decide(...):
    attended = [k for k in base.attended_needs if k in percept.active_needs]
    theta = {k: aspiration[k] * profile.aspiration_scale for k in attended}
    shortcut = rng.random() < base.impulsivity            # flux "decision_ties"
    checked = attended[:1] if shortcut else attended
    evals = []
    for a in generate(percept, profile, attended):
        s = {k: score(a, k) for k in attended}
        failed = next((k for k in checked if s[k] < theta[k]), None)
        evals.append(AlternativeEval(a.id, describe(a), s, failed is None, failed))
        if failed is None:
            rule = "reactive" if (profile.max_alternatives == 1 and profile.planning_horizon == 0) else "first_acceptable"
            return to_demandset(a, evals, rule)
    # repli lexicographique
    k_star = first k in attended such that no eval has s[k] ≥ theta[k] among evals passing all needs before k
    pool = [e for e in evals if all(e.projected[j] >= theta[j] for j in attended_before(k_star))] or evals
    best = max(pool, key=lambda e: (e.projected[k_star], -index(e)))
    rule = "reactive" if (profile.max_alternatives == 1 and profile.planning_horizon == 0) else "fallback_top_need"
    return to_demandset(best, evals, rule)
```

`to_demandset` : une `Demand` par besoin à montant > 0 (`tier` depuis `needs.yaml`, sauf HEALTH routine ⇒ `OTHER`, HEALTH épisode ⇒ `ESSENTIAL`, SECURITY ⇒ `SAVING`) ; `priority = rang de k dans attended_needs` ; `divisible` depuis `needs.yaml` (épisode et EDUCATION : False) ; `labor_supply = 1.0` si employé, sinon 0 ; `DecisionTrace` complète (`02` §7).

**Cas limites :** aucun besoin demandable (bébé sans besoin monétaire ? impossible — FOOD toujours) ⇒ DemandSet vide valide ; `max_alternatives = 1` sans habitude ⇒ premier produit (tout plein) ; égalités ⇒ ordre de génération (déterministe).

---

## 8. Sous-modèle Allocation du foyer (`agents/allocation.py`) — Temps 2

### 8.1 Séquence du Temps 2 (`HouseholdAgent.run_time2`)

```
1. Transitions d'emploi ; versement LABOR_INCOME, TAX (§3)
2. Transferts publics en espèces vers le pot ou les portefeuilles (PUBLIC_CASH_TRANSFER, scénario)
3. Intérêts : ASSET_INCOME = savings × r_s,m ; INTEREST_ACCRUED = debt × r_d,m
3b. [V3] Test de régime du foyer (sphères séparées, 30 §5.1) — AVANT la mise en commun, car le régime modifie le pooling
3c. Mise en commun : POOLING (§3)
4. credit_limit = κ × moyenne(income_total, 12 derniers mois)  [pas 0 : revenu du travail attendu du mois]
5. Engagements : logement (`housing.monthly_cost_household`·P_t réparti OCDE) + échéance = min_repayment_share × (debt_t−1 + INTEREST_ACCRUED_t) (§8.4)
6. allocations = allocate(...)  — fonction pure, ci-dessous
7. Écritures de financement : SAVING_WITHDRAWAL, BORROWING, DEBT_REPAYMENT, SAVING_DEPOSIT
8. Notification des Allocation aux personnes ; mise à jour arrears_months
```

### 8.2 Signature

```python
@dataclass(frozen=True, slots=True)
class AllocationInput:
    demands: tuple[Demand, ...]
    pot: Money                     # après versements, impôts, mise en commun, transferts publics
    savings: Money
    debt: Money
    credit_limit: Money
    housing_shares: Mapping[PersonId, Money]
    min_repayment: Money
    weights: Mapping[PersonId, float]
    mode: AllocationMode
    priority_order: tuple[NeedKind, ...] | None   # UNITARY : attended_needs du priority_owner
    borrow_for_tiers: frozenset[Tier]

@dataclass(frozen=True, slots=True)
class AllocationResult:
    allocations: tuple[Allocation, ...]
    housing_paid: Mapping[PersonId, Money]
    repayment_paid: Money
    withdrawal: Money
    borrowing: Money
    deposit: Money
    arrears: bool

def allocate(inp: AllocationInput) -> AllocationResult: ...
```

### 8.3 Algorithme

```
Sources de financement, dans cet ordre : pot → retrait d'épargne → emprunt (≤ marge = credit_limit − debt)
  • COMMITMENT et ESSENTIAL peuvent mobiliser pot + épargne + emprunt (emprunt si Tier ∈ borrow_for_tiers ;
    COMMITMENT emprunte toujours) ;
  • EDUCATION et OTHER : pot + épargne ;
  • SAVING : pot uniquement (SAVING_DEPOSIT du reliquat demandé).

1. COMMITMENT : payer le logement intégralement si possible, puis l'échéance.
   Insuffisant : logement prioritaire, payé au prorata des parts ; échéance non (ou partiellement) payée ⇒ arrears = True.
2. Pour chaque palier T ∈ (ESSENTIAL, EDUCATION, OTHER, SAVING) :
   B = ressources mobilisables pour T ; D = Σ demandes du palier
   si D ≤ B : tout accorder (GRANTED)
   sinon :
     (a) indivisibles triés par (poids desc, priority asc, demand_id asc) : accorder en entier tant que ≤ reste
         sinon REFUSED "budget_exhausted"
     (b) divisibles : part_d = reste × w_p(d)·req_d / Σ w·req ; si part_d < amount_min_d ⇒ REFUSED "below_min",
         retirer d et redistribuer (itérer jusqu'à stabilité) ; sinon PARTIAL (ou GRANTED si part = req)
   Paliers suivants sans ressources : REFUSED "budget_exhausted".
3. Le reliquat du pot reste au pot.
Modes : FIXED_WEIGHTS : w = poids normalisés ;
        UNITARY : w uniformes ; priority réécrite = rang du besoin dans priority_order ;
        VARIABLE_WEIGHTS : levée d'erreur en V1 (NotInV1Error) — activé en V2.
```

Propriétés (testées) : `Σ granted + housing_paid + repayment_paid + deposit ≤ pot + withdrawal + borrowing` ; `granted ≤ requested` ; indivisible ⇒ `granted ∈ {0, requested}` ; `borrowing ≤ marge` ; résultat indépendant de l'ordre des demandes en entrée (tri interne déterministe).

### 8.4 Crédit et dette (`economy/credit.py`)

```
r_d,m = monthly_rate(credit.annual_rate)
debt_t = debt_t−1 + INTEREST_ACCRUED_t + BORROWING_t − DEBT_REPAYMENT_t        (INV-07)
échéance_t = min_repayment_share × (debt_t−1 + INTEREST_ACCRUED_t)
arrears_months = arrears_months + 1 si échéance non intégralement payée, sinon 0
```

Événements : `arrears_start` (passage de 0 à 1), `arrears_end`, `credit_limit_hit` (emprunt plafonné). Pas de pénalité supplémentaire en V1 (les intérêts continuent de courir).

### 8.5 Épargne

`r_s,m = monthly_rate(savings.annual_rate)` ; `ASSET_INCOME = q(savings × r_s,m)` versé au début du Temps 2. Dépôt = montant accordé aux demandes SAVING (tier SAVING). Retrait = seulement pour COMMITMENT/ESSENTIAL/EDUCATION/OTHER (8.3).

---

## 9. Temps 3 — exécution des actions → écritures (`economy/actions.py`)

```python
def execute(household, allocations, persons, ledger, step, P_t):
    for a in allocations (ordre : demand_id) :
        if a.granted > 0:
            ledger.post(PRIVATE_CONSUMPTION, src=POT, dst=MARKET, amount=a.granted,
                        need=d.need, beneficiary=d.person_id, ref=d.demand_id)   # SAVING : déjà SAVING_DEPOSIT
    for pid, x in housing_paid: ledger.post(PRIVATE_CONSUMPTION, POT→MARKET, x, need=HOUSING, beneficiary=pid)
    # complément personnel (consommation seulement, pas l'épargne)
    for d in demandes PARTIAL/REFUSED, need ≠ SECURITY, triées par priority :
        manque = d.requested − granted ; si indivisible : manque doit être payé en entier
        if wallet(d.person_id) ≥ manque (ou ≥ montant payable si divisible) :
            ledger.post(PRIVATE_CONSUMPTION, WALLET(d.person_id)→MARKET, payable, need, beneficiary=d.person_id)
    # consommation publique en nature (Cg)
    for p in persons: PUBLIC_INKIND GOV→MARKET : éducation si ENROLLED, santé routine (economic_params.public.inkind_by_age × P_t)
    # mises à jour d'état dérivées des écritures : spent_by_need, sat, level, cared, refused_edu_months
```

ALLOCATION_CASH n'est pas émis par la V1 (catégorie disponible pour V2 : argent de poche, `CONTRIBUTE_MORE`). Arrondi du logement : parts calculées en `Decimal`, le **dernier bénéficiaire** (ordre `person_id`) reçoit le résidu pour que `Σ = coût` exactement.

---

## 10. Ledger (`economy/ledger.py`)

```python
class Ledger:
    def post(self, step, household_id, src: AccountId, dst: AccountId, amount: Money,
             category: FlowCategory, *, need=None, beneficiary=None, initiator="", ref=None) -> LedgerEntry
    def balance(self, account: AccountId) -> Money
    def entries(self, step: int, household_id: str | None = None) -> Sequence[LedgerEntry]
    def balances_snapshot(self) -> dict[AccountId, Money]
    def subscribe(self, callback: Callable[[LedgerEntry], None]) -> None   # mise à jour des caches d'état
```

Validations à `post` (lever `LedgerError`) : `amount > 0` et déjà quantifié ; couple (src, dst) autorisé pour `category` (table `02` §8.3, encodée comme `ALLOWED: dict[FlowCategory, set[tuple[AccountKind, AccountKind]]]`) ; consommation ⇒ `beneficiary` et `need` non nuls, bénéficiaire membre du foyer ; débit d'un compte d'actif interne qui deviendrait négatif ; crédit du compte `HOUSEHOLD_LOAN` (remboursement) au-delà de 0. Stockage : liste append-only + soldes courants (`dict`). Les entrées sont vidées vers Parquet par bloc de 12 pas si `output.collect.ledger`.

---

## 11. Couche NTA (`nta/`) — fin du Temps 3, lecture seule

### 11.1 `NTACalculator.compute(step) -> list[NTAStepRecord]`

À partir des seules écritures du pas et des snapshots de soldes (début/fin de pas) :

```
Yl_i      = Σ LABOR_INCOME vers i
Cf_i      = Σ PRIVATE_CONSUMPTION de bénéficiaire i (payée par pot ou portefeuille)
Cg_i      = Σ PUBLIC_INKIND de bénéficiaire i
τ⁺pub_i   = Cg_i + PUBLIC_CASH_TRANSFER vers i + ω_i·PUBLIC_CASH_TRANSFER vers pot
τ⁻pub_i   = Σ TAX de i
τ±intra_i = depuis la matrice T (attribution.py)
τ±inter_i = INTER_HOUSEHOLD_TRANSFER (0 en V1)
Ya_i      = ω_i·(ASSET_INCOME − INTEREST_ACCRUED)
S_i       = Δwallet_i + ω_i·Δ(pot + savings + loan)
lcd_i     = Cf_i + Cg_i − Yl_i
residual_i = (C_i − Yl_i) − [(τ⁺_i − τ⁻_i) + (Ya_i − S_i)]
```

Calculs en `Decimal` **sans quantification intermédiaire** ; seul `residual` est comparé à ε.

### 11.2 `nta/attribution.py`

```python
def transfer_matrix(entries: Sequence[LedgerEntry], owners: Mapping[PersonId, float],
                    members: Sequence[PersonId]) -> dict[tuple[PersonId, PersonId], Decimal]:
    """Règle 02 §9. POOLING, ALLOCATION_CASH, PRIVATE_CONSUMPTION payée par le pot, flux pot↔extérieur."""
```

### 11.3 `nta/imputation.py` — règle du manuel ONU (comparaison uniquement)

Hypothèse : le `head` détient tous les actifs du foyer ; les autres membres n'ont ni Ya ni S d'actifs du foyer.

```
YD_i = Yl_i − tax_i + PUBLIC_CASH_TRANSFER vers i         (i ≠ head)
τ_imp_net_i    = Cf_i + Δwallet_i − YD_i                   (i ≠ head ; > 0 : reçu du head)
τ_imp_net_head = − Σ_{i≠head} τ_imp_net_i
```

Le terme `+Δwallet_i` conserve l'épargne personnelle du non-chef (sinon l'identité ne boucle pas) — **détail tranché, à vérifier par l'auteur contre UN (2013)**. Sortie : `tau_net_imputed`, `tau_gap = tau_net_behav − tau_net_imputed`. Ne lit pas `accounts.py` (contrat C3).

### 11.4 `nta/profiles.py`

Agrégation par âge entier (`floor(age_years)`) : moyennes **annuelles** par tête (`Σ mensuel × 12 / person_months`), colonnes `*_norm` (÷ moyenne de `yl` des âges 30–49 ; si vide : colonne nulle). Table `nta_age_profile`. Matrice annuelle `nta_transfer_matrix`.

---

## 12. Invariants (`nta/invariants.py`) — vérifiés à chaque pas ; violation ⇒ `InvariantViolation`, run `failed`

| ID | Formule | ε | Portée | Quand |
|---|---|---|---|---|
| INV-01 | `Σ_tous comptes balance = 0` (double entrée) | 0 exact | global | fin de pas |
| INV-02 | Pour tout compte interne : `balance_fin − balance_début = Σ entrées − Σ sorties` du pas **et** cache d'état = solde Ledger | 0 exact | compte | fin de pas |
| INV-03 | portefeuilles, pot, épargne ≥ 0 ; prêt ≤ 0 | 0 | compte | fin de pas |
| INV-04 | `|residual_i| ≤ ε` (identité NTA individuelle) | 0,01 FCFA | personne | fin de pas |
| INV-05 | `|Σ_i (τ⁺intra_i − τ⁻intra_i)| ≤ ε` | 0,01 FCFA | foyer | fin de pas |
| INV-06 | `ΣYl + ΣYa + τnet_pub_cash + τnet_inter − ΣCf − ΣS = 0` (désépargne ; `τnet_pub_cash` = transferts publics en espèces − impôts, la part en nature compensant Cg) | 0,01 FCFA | foyer | fin de pas |
| INV-07 | `debt_t = debt_t−1 + intérêts + emprunts − remboursements` | 0 exact | foyer | fin de Temps 2 |
| INV-08 | toute consommation a `need` et un `beneficiary` membre du foyer | — | écriture | à `post` |
| INV-09 | allocations : `granted ≤ requested` ; indivisible ⇒ {0, requested} ; financements ≤ ressources ; `borrowing ≤ credit_limit − debt` | 0 exact | foyer | fin de Temps 2 |
| INV-10 | `Σω = 1`, `Σ weights = 1`, ω ≥ 0 | 1e-12 | foyer | chargement + chaque pas |
| INV-11 | `Σ_i tau_net_imputed_i = 0` | 0,01 FCFA | foyer | fin de pas |
| INV-12 | Collecte : `cf` de `person_steps` = `Σ PRIVATE_CONSUMPTION` du bénéficiaire ; `yl` idem | 0,01 FCFA | personne | fin de pas (si collecte active) |

`checks.invariant_run_sample_rate < 1` n'est accepté par le loader que si `docs/GATES.md` déclare la porte V1 verte (lecture d'un drapeau `gate_v1: passed`).

---

## 13. Modèle et ordonnancement (`model/`)

```python
class FamilyModel(mesa.Model):
    def __init__(self, config: SimulationConfig, scenario: Scenario, run_id: str): ...
    def step(self) -> None:
        events.apply(self.step_index)                 # 0. chocs exogènes
        for h in self.households: scheduler.time1(h)  # perception, santé, besoins, décision → DemandSet
        for h in self.households: scheduler.time2(h)  # revenus, intérêts, allocate, financements
        for h in self.households: scheduler.time3(h)  # exécution, complément, Cg, mise à jour des niveaux de besoins
        self.nta.compute(...); invariants.check(...); collectors.collect(...)
        for h in self.households: scheduler.age(h)    # vieillissement + transitions de profil, APRÈS la collecte (G1)
    def run(self) -> RunResult: ...                   # horizon_months pas ; écrit run.json en fin (completed|failed)
```

- Ordre des personnes au Temps 1 : `rng["scheduling"].permutation` — sans effet sur le résultat (test).
- Les états de besoins (`level`) sont mis à jour au Temps 3 (après dépense) ; le Temps 1 du pas suivant les lit.
- `RunResult(run_id, status, failure, duration_s, n_steps)`. Une `InvariantViolation` arrête le run, écrit les tables jusqu'au pas fautif et `failure = {inv_id, step, household_id, detail}`.

**Initialisation** (`model/family_model.py::build_household`) : membres de `baseline_household` ; `age_months = age × 12` ; `SchoolStatus` déduit de l'âge et de `employment` ; `level` initial §4. Détail tranché : les soldes initiaux (`initial_assets`) sont posés par une écriture spéciale `category = OPENING_BALANCE` (src `BANK`, dst pot/épargne ; prêt initial : src `HOUSEHOLD_LOAN`, dst `BANK`) au **pas −1**, exclue de tous les calculs NTA (qui ne portent que sur les pas ≥ 0). `FlowCategory.OPENING_BALANCE` est ajoutée à l'enum.

---

## 14. Collecte (`model/collectors.py`)

Remplit les tables `04` §2.2–2.11 selon `output.collect`. Valeurs `float` ; colonnes V2/V3 aux valeurs neutres (`02` §4). `metrics` en fin de run : indicateurs `04` §3.1–3.3 calculables sur un foyer. `decisions` : `all` en V1 (un foyer).

---

## 15. Trace numérique d'un pas complet (pas 0, scénario `baseline`, aucun épisode de santé, tirage informel m = 1,00)

Configuration : `03` (placeholders). P₀ = W₀ = 1. Taux mensuels : épargne r_s,m = 1,03^(1/12) − 1 = 0,0024663 ; dette 0.

**Temps 2 — revenus**

| Écriture | Montant |
|---|---|
| LABOR_INCOME père | 250 000 |
| TAX père (10 %) | 25 000 |
| POOLING père (100 %) | 225 000 |
| LABOR_INCOME mère (informel) | 120 000 |
| POOLING mère (80 %) | 96 000 → portefeuille mère : 24 000 |
| ASSET_INCOME (150 000 × 0,0024663) | 369,94 |

Pot = 50 000 + 225 000 + 96 000 = **371 000**. credit_limit = 3 × 370 000 = 1 110 000.

**Logement (COMMITMENT)** — échelle OCDE : père 1, mère 0,5, jeune adulte 0,5, adolescent (15 ans) 0,5, enfant 0,3, bébé 0,3 ; Σ = 3,1 :
père 29 032,26 · mère, JA, ado 14 516,13 chacun · enfant 8 709,68 · bébé 8 709,67 (résidu) — Σ = 90 000,00. Reste : **281 000**.

**Demandes (paniers « tout plein » acceptés au pas 0)**

| Personne | FOOD (ESS.) | HEALTH routine (OTHER) | EDUCATION (EDU.) | SECURITY (SAVING) |
|---|---|---|---|---|
| Père (45) | 35 000 | 3 000 | — | 36 375 |
| Mère (40) | 35 000 | 3 000 | — | 36 375 |
| Jeune adulte (20, inscrit) | 35 000 | 3 000 | 40 000 | — (ω = 0) |
| Adolescent (15) | 30 000 | 2 000 | 15 000 | — |
| Enfant (9) | 22 000 | 2 000 | 8 000 | — |
| Bébé (1) | 15 000 | 3 000 | — | — |
| **Total** | **172 000** | **16 000** | **63 000** | **72 750** |

SECURITY : cible = 3 × 341 000 (dépense initiale estimée) = 1 023 000 ; écart = 873 000 ; demande foyer = 873 000/12 = 72 750, soit ω·72 750 = 36 375 par parent.

**Allocation** : ESSENTIAL 172 000 → reste 109 000 ; EDUCATION 63 000 → 46 000 ; OTHER 16 000 → 30 000 ; SAVING : 72 750 > 30 000 ⇒ prorata poids (1 : 1) → 15 000 + 15 000 (`PARTIAL`). SAVING_DEPOSIT 30 000. Pot final **0**. Épargne = 150 000 + 369,94 + 30 000 = **180 369,94**.

**Temps 3** : 15 écritures PRIVATE_CONSUMPTION depuis le pot (Σ 251 000) + 6 logement (90 000) ; aucun complément personnel (épargne exclue). PUBLIC_INKIND : éducation JA 12 000, ado 9 000, enfant 6 000 ; santé : père, mère, JA, ado, enfant 1 000 chacun, bébé 2 000 ⇒ Cg total 34 000.

**NTA du pas 0** (ω père = mère = 0,5 ; Δ(pot + épargne + prêt) = −50 000 + 30 369,94 = −19 630,06)

| | Père | Mère | Jeune adulte |
|---|---|---|---|
| Cf | 67 032,26 | 52 516,13 | 92 516,13 |
| Cg | 1 000 | 1 000 | 13 000 |
| Yl | 250 000 | 120 000 | 0 |
| LCD = C − Yl | −181 967,74 | −66 483,87 | 105 516,13 |
| τ⁺intra | 48 000 + 33 516,13 = 81 516,13 | 112 500 + 26 258,065 = 138 758,065 | 92 516,13 |
| τ⁻intra | 112 500 + 26 258,065 + 110 725,805 = 249 483,87 | 48 000 + 33 516,13 + 110 725,805 = 192 241,935 | 0 |
| τ⁺pub / τ⁻pub | 1 000 / 25 000 | 1 000 / 0 | 13 000 / 0 |
| Ya | 184,97 | 184,97 | 0 |
| S | 0 − 9 815,03 = −9 815,03 | 24 000 − 9 815,03 = 14 184,97 | 0 |
| (τ⁺−τ⁻) + (Ya − S) | −191 967,74 + 10 000,00 = **−181 967,74** ✓ | −52 483,87 − 14 000,00 = **−66 483,87** ✓ | **105 516,13** ✓ |

Transferts reçus des non-propriétaires (Cf payée par le pot) : JA 92 516,13 ; ado 61 516,13 ; enfant 40 709,68 ; bébé 26 709,67 — Σ 221 451,61, financée à moitié par chaque parent (110 725,805). INV-05 : −167 967,74 − 53 483,87 + 221 451,61 = 0 ✓. INV-06 : 370 000 + 369,94 − 25 000 − 341 000 = 4 369,94 = ΣS (−9 815,03 + 14 184,97) ✓.

**Imputation ONU (head = père)** : mère τ_imp_net = 52 516,13 + 24 000 − 120 000 = −43 483,87 (elle « verse » au chef) contre −53 483,87 en comportemental ⇒ `tau_gap = −10 000,00` (exactement sa part ω des actifs du foyer, Ya − S = 10 000, que la règle ONU attribue au chef) ; JA, ado, enfant, bébé : imputé = comportemental (pas de revenu). Père : +43 483,87 − 221 451,61 = −177 967,74 (comportemental −167 967,74 ⇒ gap +10 000,00). Σ imputé = 0 ✓ (INV-11).

Signes LCD : parents < 0, enfants > 0 ✓ (critère E1).

---

## 16. Tests à écrire

| Fichier | Test | Critère |
|---|---|---|
| `unit/test_ledger.py` | refus montant ≤ 0, couple (src,dst) interdit, consommation sans bénéficiaire, découvert | `LedgerError` |
| `unit/test_attribution.py` | trace §15 reproduite au centime | égalité exacte aux valeurs du tableau |
| `unit/test_imputation.py` | trace §15, Σ = 0, chef unique | idem |
| `unit/test_allocation.py` | tous les cas de 8.3 ; mode UNITARY ; indivisibles ; plancher ; ordre d'entrée permuté | propriétés 8.3 |
| `unit/test_satisficing.py` | `max_alternatives = 1 ∧ H = 0` ⇒ rule `reactive` ; seuil très bas ⇒ première alternative acceptée ; seuil > 1 ⇒ repli ; impulsivité 1 ⇒ seul le besoin n°1 vérifié | Fiche 1 (TEST) |
| `unit/test_alternatives.py` | troncature à `max_alternatives` ; habitude en tête ; partition par enveloppe si H ≥ 1 seulement | |
| `unit/test_labor.py`, `test_health.py`, `test_schooling.py` | transitions, E[m] = 1 (10⁵ tirages, tolérance 1 %), épisode demandé une seule fois, abandon après m_drop refus | |
| `unit/test_config.py` | bornes, profils inconnus, ω ≠ 1 ⇒ `ConfigError` ; hash stable ; `illustrative = True` avec placeholders | |
| `unit/test_architecture.py` (`tests/architecture/`) | contrats C1–C5 (import-linter) ; **une seule sous-classe/implémentation de `DecisionEngine` dans `src/`** ; aucun littéral numérique métier dans `agents/`, `decision/`, `cognition/`, `economy/`, `health/` (scan AST : ensemble autorisé unifié `{0, 1, -1, 0.0, 1.0, 2, 12}`, identique à 90 §2.1) | |
| `invariants/test_property_ledger.py` (hypothesis) | séquences aléatoires d'écritures valides ⇒ INV-01/02/03 | 200 exemples |
| `invariants/test_property_allocation.py` (hypothesis) | demandes/budgets aléatoires ⇒ INV-09, Σ financements ≤ ressources | 500 exemples |
| `invariants/test_property_nta.py` (hypothesis) | flux de foyers aléatoires ⇒ INV-04/05/06/11 | 200 exemples |
| `integration/test_run_baseline.py` | 240 pas, seed 42, `status = completed` ; tables présentes et schémas conformes | |
| `invariants/test_invariants_100_seeds.py` (`-m slow`) | 100 seeds × 240 pas × 6 scénarios, zéro violation | porte V1 |
| `regression/test_reproducibility.py` | même seed ⇒ Parquet identiques octet par octet (hors `created_at`, `duration_s`) ; seeds différentes ⇒ trajectoires différentes | |
| `integration/test_scheduling_order.py` | permutation forcée de l'ordre du Temps 1 ⇒ allocations identiques | |
| `integration/test_lcd_signs.py` | LCD moyen annuel : > 0 bébé/enfant/adolescent, < 0 parents, sur toute la période et 100 seeds | critère E1 |
| `integration/test_scenarios.py` | `job_loss` ⇒ dette ↑ vs baseline (même seed) ; `free_care` ⇒ `health_spending` privé ↓ ; `family_allowance` ⇒ `rav_per_eq` ↑ | signes |
| `performance/test_budget_v1.py` | 1 foyer × 240 pas < 5 s (médiane de 5 exécutions) | porte V1 |

---

## 17. Expérience E1 (protocole complet : `50_SPEC_EXPERIMENTS.md`)

Run de référence, aucune variable manipulée, 100 réplications (seeds 1000–1099). Métriques : LCD par membre, `debt_to_income`, `savings_rate_12m`, `rav_per_eq`, résidus de bouclage. Résultat attendu : LCD > 0 pour bébé, enfant, adolescent ; < 0 pour les parents ; bouclage exact. Figures : `fig_E1_lcd_by_member`, `fig_E1_household_balance`.

---

## 18. Porte V1 — critères de sortie (tous verts avant la V2)

`uv run family-abm gate v1` (équivalent `make gate-v1`) exécute les vérifications et coche `docs/GATES.md`. **La liste normative est `90_TEST_STRATEGY_AND_GATES.md` §3.1 (G1.1–G1.10)** ; elle est reprise ici avec les tests de cette spec :

| # | Critère (feuille de route §11) | Vérification |
|---|---|---|
| G1.1 | Identités NTA bouclent à ε à chaque pas, 20 ans, 100 seeds | `tests/invariants/test_invariants_100_seeds.py` (INV-04/05/06/11) |
| G1.2 | Aucune valeur ne disparaît : Σ entrées − Σ sorties = Δactifs | INV-01, INV-02 (même test) |
| G1.3 | La dette suit exactement l'équation de désépargne | INV-07 + `tests/invariants/test_property_nta.py` |
| G1.4 | Même seed ⇒ trajectoire strictement identique | `tests/regression/test_reproducibility.py` |
| G1.5 | Signe du LCD correct pour les six membres sur toute la période | `tests/integration/test_lcd_signs.py` |
| G1.6 | ODD-V1 écrit et cohérent avec le code | attestation de l'auteur + `tests/architecture/test_odd_sync.py` (chaque paramètre de `config/` actif en V1 est cité dans `odd/ODD_v1_economic.md`) |
| G1.7 | Suite de tests verte, couverture ≥ 90 % sur `economy/`, `nta/`, `agents/allocation.py` | `uv run pytest --cov` |
| G1.8 | 1 foyer × 20 ans < 5 s | `tests/performance/test_budget_v1.py` |
| G1.9 | Contrats d'architecture | `lint-imports` + `tests/architecture/` |
| G1.10 | E1 exécutée et rapportée | `experiments/results/experiments/E1/summary.parquet` + figure `fig_E1_lcd_by_member` |

## 19. Risques V1

| Risque | Signe précurseur | Parade |
|---|---|---|
| Sur-ingénierie | une `Factory` ou une hiérarchie d'allocation | S1 ; test d'architecture « une seule implémentation » |
| Fuite comptable | invariants qui échouent « parfois » | Decimal, Ledger seule source, échec dur, propriétés hypothesis |
| Paramètres implicites | littéraux dans le code | scan AST |
| Glissement de périmètre | « juste la mémoire » | porte V1 fermée |
| Comportement trivial | tous les agents demandent toujours le panier plein | attendu en V1 (rationnement par le foyer) ; la variation vient de la troncature, de l'enveloppe et de l'impulsivité — documenter, ne pas « corriger » en V1 |

## 20. Détails tranchés dans ce document

1. Revenu informel : `LogNormal(−σ²/2, σ)` (espérance 1).
2. Retour à l'emploi : `p_find` du secteur du dernier emploi ; formel avec `find_formal_share`.
3. Membres sans clé `pooling` / `wage_key` : valeurs `young_adult`.
4. HEALTH : épisode demandé une seule fois (1er mois) ; durée max `max_episode_months` (6) ; récupération naturelle `natural_recovery` (+0,01/mois) hors épisode ; formule de `sat_health` (§4) — toutes ces valeurs sont des clés de `economic_params.health` / `needs.health` (03 §5–§6).
5. SECURITY : valeur du foyer, demandée uniquement par les propriétaires (ω > 0), montant `ω·écart/12`.
6. Montants minimaux : FOOD 0,5·r ; autres §7.3.
7. Ordre de saillance : habitude, puis produit lexicographique « plein d'abord », puis partition par enveloppe (H ≥ 1).
8. Repli lexicographique sur le premier besoin non satisfaisable.
9. Financement : pot → épargne → emprunt ; SAVING sur pot seul ; logement prioritaire sur l'échéance.
10. Résidu d'arrondi du logement au dernier bénéficiaire.
11. `FlowCategory.OPENING_BALANCE` au pas −1, hors NTA.
12. Imputation ONU : ajout de `Δwallet_i` du non-chef (épargne personnelle conservée ; à vérifier contre UN 2013).
13. INV-06 : `τnet_pub` = transferts publics **en espèces** nets d'impôts (la part en nature compense Cg) — précise la formule de `02` §9, qui doit être lue ainsi.
14. Aspiration réinitialisée à `aspiration_init` du nouveau profil lors d'une transition (V1).
