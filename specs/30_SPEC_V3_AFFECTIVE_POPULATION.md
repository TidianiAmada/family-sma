# 30 — Spécification V3 : cognitive-affective et population

> **Prérequis bloquant :** porte V2 verte (`20_SPEC_V2_COGNITIVE.md` §critères de sortie, `docs/GATES.md`). Aucune ligne de ce document n'est implémentée tant qu'une case V1 ou V2 est rouge.
> **Objectif scientifique (feuille de route §14) :** étudier la boucle **B3** — rétroaction entre contrainte économique, état affectif et capacité de décision — et produire un profil NTA agrégé comparable aux profils nationaux.
> **Règle ODD :** chaque sous-modèle ci-dessous est d'abord décrit dans `odd/ODD_v3_affective_population.md`, puis codé, dans le même commit que sa mise à jour éventuelle.
> **Avertissement 【HYP】 :** toutes les formes fonctionnelles de l'appraisal, des émotions, du stress, de la modulation et de la rétroaction santé sont des **hypothèses de modélisation**, non des faits psychologiques. Elles sont linéaires par morceaux par défaut, avec une variante sigmoïde pour le test de robustesse (Chap. 9). Le code et l'UI doivent les présenter comme telles.

---

## 0. Ordre d'implémentation (priorité décroissante — s'arrêter où le temps s'arrête)

| # | Élément | Fichiers | Expérience | Abandonnable ? |
|---|---|---|---|---|
| 1 | Appraisal + 4 émotions + stress/humeur + `EffectiveCognitiveProfile` | `cognition/appraisal.py`, `cognition/modulation.py`, `agents/states.py` | **E4** | **Non** — raison d'être de la V3 |
| 2 | Population de ~1 000 foyers | `population/generator.py`, `population/sources.py`, `model/family_model.py` | **E7** | Non (condition de V-6) |
| 3 | Calibration + POM multi-patterns | `analysis/calibration.py`, `analysis/patterns.py` → **`40_SPEC_VALIDATION_CALIBRATION.md`** | Phase 9 | Repli : population paramétrée sur profils NTA publiés |
| 4 | Régime « sphères séparées » | `agents/household.py`, `agents/allocation.py` | E4 (variante), E6 | Oui (faible coût : à garder) |
| 5 | Repère d'efficacité collective | `analysis/efficiency.py` | **E8** | Oui (2ᵉ abandonné) |
| 6 | CPT sur 4 décisions binaires | `decision/risk.py` | **E5** | Oui (1ᵉʳ abandonné) |
| 7 | Chocs de santé avec rétroaction cognitive | `health/health.py`, `cognition/appraisal.py` | E4 (variante) | Oui |
| 8 | Extension d'échelle par dégradation cognitive contrôlée | `analysis/experiments.py` (facteurs) | **E9** | Oui (3ᵉ abandonné) |

## 1. La boucle B3 — description et bascule

```
contrainte économique (sat_k bas, budget refusé, buffer faible)
        │  Temps 1, après mise à jour des besoins et des croyances (correction n°1 de l'audit)
        ▼
AppraisalEngine.appraise(person) ──► Appraisal(r, d, c, p)
        ▼
AffectiveState.update(...)        ──► émotions, stress S, humeur
        ▼
ModulationEngine.effective(profile, affect) ──► EffectiveCognitiveProfile (H_eff, M_eff, β_eff, …)
        ▼
SatisficingEngine.decide(percept, profile=profile_eff, base, aspiration, rng)   (le moteur ne lit JAMAIS AffectiveState — contrat C4)
        ▼
demandes plus myopes / moins d'alternatives ─► allocation ─► actions ─► contrainte du pas suivant
```

**Bascules (S8)** :

| Clé | Effet si `false` |
|---|---|
| `affect.enabled` | `AffectiveState` reste neutre (0), `ModulationEngine` renvoie le profil de base, **aucun tirage aléatoire supplémentaire**. Résultat : V2 **bit à bit** (§10). |
| `loops.b3.enabled` | L'appraisal et les émotions sont calculés et collectés (observables), mais la modulation est l'identité : on observe l'affect sans qu'il rétroagisse. C'est la condition « contrôle » d'E4. |
| `affect.health_feedback.enabled` | coupe uniquement la rétroaction stress → santé (élément 7). |
| `household_rules.separate_spheres.enabled` | coupe uniquement le régime dégradé (élément 4). |

Distinction importante pour E4 : `loops.b3.enabled=false` (affect mesuré, sans effet) est le bon contrôle ; `affect.enabled=false` sert à la non-régression.

**Séquence complète du Temps 1 en V3 (normative, G3)** — reprise dans 01 §4 et ODD-V3 §3 :

```
1. perception : remise à zéro des dépenses du pas, santé (+ rétroaction stress→santé du pas précédent, §8)
2. mémoire : encodage des épisodes perçus ; croyances révisées ; désirs dérivés             [V2]
3. appraisal → émotions, stress, humeur                                                    [V3]
4. modulation → EffectiveCognitiveProfile                                                  [V3]
5. délibération (intentions) — lit profile_eff.intention_commitment                        [V2]
6. CPT, si une des 4 décisions binaires est ouverte ce pas (§7)                            [V3]
7. satisficing (profile_eff) → DemandSet + DecisionTrace                                    [V1]
```

## 2. Élément 1 — Appraisal, émotions, stress, modulation

### 2.1 Appraisal (`cognition/appraisal.py`) — personnes ayant la capacité `APPRAISE`

Exécuté au Temps 1, **après** la mise à jour des besoins et des croyances (V2), **avant** la décision. Entrées : `NeedsState.satisfaction` du pas courant (calculée sur les allocations du pas précédent), `CognitiveState.aspiration`, croyances, `HouseholdState`, résultats d'allocation du pas précédent.

Pour chaque besoin attendu k (ordre `attended_needs`, rang ρ_k = 0, 1, …), poids de rang `π_k = 1 / (1 + ρ_k)` :

```
g_k = sat_k − θ_k                                        congruence au but  ∈ [−1, 1]
r   = Σ π_k |g_k| / Σ π_k                                pertinence        ∈ [0, 1]
d   = Σ π_k g_k  / Σ π_k                                 désirabilité      ∈ [−1, 1]
c   = clip( w_buf · min(1, buffer_months / target_buffer_months)
          + w_cred · credit_headroom / max(credit_limit, 1)
          + w_sup · granted_ratio_recent , 0, 1 )        contrôlabilité    ∈ [0, 1]
p   = max( conf(job_at_risk), conf(debt_critical) )      menace prospective ∈ [0, 1]
refusal_rate = demandes REFUSED ou PARTIAL (pondérées par montant manquant) / demandé, pas précédent
```

- `buffer_months` = `savings / dépense mensuelle moyenne 12 m du foyer` (lecture de `HouseholdState`, jamais du NTA).
- `granted_ratio_recent` = moyenne sur `appraisal.support_window` mois du rapport accordé/demandé de la personne.
- Les membres non-adultes lisent les mêmes grandeurs foyer : la contrôlabilité d'un adolescent dépend du coussin du foyer (choix assumé, ODD).
- Personnes sans `APPRAISE` (bébé, enfant par défaut) : aucun appraisal ; `AffectiveState` reste neutre ; leur profil effectif = profil de base.

### 2.2 Émotions, stress, humeur (`AffectiveState`)

Décroissance λ_e = `affect.emotions.decay` ; toutes les intensités bornées [0, 1] :

```
joy     ← (1 − λ_e)·joy     + λ_e · max(0,  d) · r
sadness ← (1 − λ_e)·sadness + λ_e · max(0, −d) · r · (1 − c)
fear    ← (1 − λ_e)·fear    + λ_e · p · (1 − c)
anger   ← (1 − λ_e)·anger   + λ_e · refusal_rate · max(0, −d)
S       ← clip( (1 − δ_S)·S + κ_i · max(0, −d) · (1 − c), 0, 1 )      κ_i = profile.stress_sensitivity
mood    ← (1 − μ)·mood + μ · d
```

### 2.3 Modulation (`cognition/modulation.py`) → `EffectiveCognitiveProfile`

Forme `linear` (défaut) :

```
H_eff              = floor( H · (1 − m_H · S) )
M_eff              = max(1, round( M · (1 − m_M · S) ))
aspiration_scale   = 1 − m_θ · sadness             θ_eff,k = θ_k · aspiration_scale (utilisé pour l'acceptabilité seulement ; θ_k stocké n'est pas modifié)
β_eff              = β · (1 − m_β · S)
commitment_eff     = commitment · (1 − m_c · anger)
λ_eff              = λ · (1 + m_λ · fear)
```

Forme `sigmoid` (robustesse) : chaque facteur `(1 − m·x)` est remplacé par `1 − m · σ(k_s·(x − x_0))` avec `σ` logistique ; mêmes bornes. Le choix de forme est un facteur explorable d'E4 (`affect.modulation.form`).

`round` = arrondi bancaire de Python (`round()`), documenté. `floor` garantit qu'un stress nul redonne exactement H.

### 2.4 Signatures

```python
@dataclass(frozen=True, slots=True)
class Appraisal:
    relevance: float; desirability: float; controllability: float; threat: float
    refusal_rate: float; congruence: dict[NeedKind, float]

class AppraisalEngine:
    def __init__(self, cfg: AffectConfig) -> None: ...
    def appraise(self, person: PersonView, household: HouseholdView, step: Step) -> Appraisal: ...

def update_affect(state: AffectiveState, a: Appraisal, profile: CognitiveProfile, cfg: AffectConfig) -> None: ...

class ModulationEngine:
    def __init__(self, cfg: AffectConfig, b3_enabled: bool) -> None: ...
    def effective(self, profile: CognitiveProfile, affect: AffectiveState) -> EffectiveCognitiveProfile: ...
```

`PersonView` / `HouseholdView` : vues en lecture seule (Protocol) — l'appraisal ne mute rien.

### 2.5 Mémoire (V2) et affect

L'appraisal écrit un épisode `kind="appraisal"`, `valence=d`, `value=S` dans la mémoire si la personne a `REMEMBER`. Il n'utilise pas la mémoire pour le calcul (évite une seconde boucle cachée) ; le point de référence CPT (§7) l'utilise.

### 2.6 `config/affect.yaml` (complet)

```yaml
enabled: true                                           # bascule (B1 : vit ici, chemin affect.enabled)
appraisal:
  weights: { buffer: 0.4, credit: 0.2, support: 0.4 }   # w_buf, w_cred, w_sup — PLACEHOLDER, Σ = 1
  support_window: 3                                     # mois
  sick_threat_weight: 0.5                               # §8 — PLACEHOLDER
emotions:
  decay: 0.3                                            # λ_e — PLACEHOLDER
stress:
  decay: 0.15                                           # δ_S — CALIBRATE (registre : affect.stress.decay)
mood:
  smoothing: 0.2                                        # μ — PLACEHOLDER
modulation:
  form: linear                                          # linear | sigmoid
  horizon: 0.6                                          # m_H — CALIBRATE
  alternatives: 0.5                                     # m_M — CALIBRATE
  aspiration: 0.3                                       # m_θ — PLACEHOLDER (fixé puis exploré)
  beta: 0.2                                             # m_β — PLACEHOLDER
  commitment: 0.3                                       # m_c — PLACEHOLDER
  lambda: 0.5                                           # m_λ — PLACEHOLDER
  sigmoid: { steepness: 10.0, midpoint: 0.5 }           # k_s, x_0
health_feedback:
  enabled: true
  stress_floor: 0.4                                     # S0
  rate: 0.02                                            # h_s : perte de santé / mois / unité de stress au-dessus de S0
provenance: PLACEHOLDER
source: "Formes 【HYP】 ; justification qualitative : Marsella & Gratch (2009, EMA), Mani et al. (2013)"
```

### 2.7 Tests (élément 1)

| Test | Vérifie |
|---|---|
| `test_appraisal_neutral` | sat_k = θ_k pour tout k ⇒ d = 0, r = 0, aucune émotion ne croît |
| `test_appraisal_bounds` (hypothesis) | toutes les sorties dans leurs bornes pour entrées aléatoires bornées |
| `test_stress_monotone` | à c fixé, d plus négatif ⇒ S non décroissant |
| `test_modulation_identity_zero_stress` | S = sadness = anger = fear = 0 ⇒ profil effectif = profil de base, champ par champ |
| `test_modulation_bounds` | M_eff ≥ 1, H_eff ≥ 0, β_eff ∈ (0, β], λ_eff ≥ λ |
| `test_b3_disabled_identity` | `loops.b3.enabled=false` ⇒ profil effectif = base même avec S > 0 |
| `test_decision_no_affect_import` | contrat C4 (import-linter) |
| `test_baby_neutral_affect` | personne sans APPRAISE ⇒ AffectiveState reste 0 sur 240 pas |
| `test_v2_bit_identical` | §10 |

## 3. Élément 2 — Population de foyers

### 3.1 Principe

Les foyers sont **indépendants** (aucune interaction inter-foyers, hors `OTHER_HOUSEHOLDS` pour les transferts du jeune adulte parti, D13). Le profil NTA par âge n'est reproductible qu'au niveau d'une population (feuille de route Chap. 7) : la diversité d'âges vient de la variété des compositions et du jitter.

### 3.2 Générateur (`population/generator.py`)

```python
@dataclass(frozen=True, slots=True)
class HouseholdSpec:
    household_id: HouseholdId
    members: tuple[MemberSpec, ...]       # profil, âge (années), emploi, salaire, clé de pooling
    initial_assets: AssetsSpec            # pot, savings, loan
    ownership: dict[str, float]; head: str
    rng_key: tuple[int, int]              # (seed, household_index) — S4

def generate_population(cfg: PopulationConfig, init: InitDistributions, seed: int) -> list[HouseholdSpec]: ...   # init = resolve_source(cfg).initial_distributions()
```

Algorithme (flux `rng.population`, dérivé de `(seed, "population")`, indépendant des flux de simulation) :

1. Tirer `n_households` gabarits selon `templates[].weight` (multinomial).
2. Pour chaque membre : âge = âge du gabarit + U(−j, +j) années (`age_jitter_years`, par rôle), borné par `age_bounds` du gabarit et cohérent (parent ≥ enfant aîné + `min_parent_gap`) ; profil déduit de l'âge via `profile_transitions` (donnée).
3. Salaires : tirage dans `init.wages(role, employment)` ; emploi formel/informel selon `init.employment_shares(role)`.
4. Actifs initiaux : `init.assets` (corrélés au revenu par copule gaussienne, ρ = `assets_income_corr`).
5. Sous-flux RNG du foyer : `SeedSequence(seed).spawn` indexé par `household_index` — un foyer donne la même trajectoire seul ou au sein de N (test).

Le foyer de référence (`household_rules.baseline_household`) est un gabarit parmi d'autres (`template: baseline_6`).

### 3.3 Sources (`population/sources.py`) — Q6 — interface normative : `40_SPEC_VALIDATION_CALIBRATION.md` §4

La V3 utilise **l'interface `DataSource` de 40 §4.1**, sans interface parallèle :

```python
class DataSource(Protocol):                      # 40 §4.1 — fait foi
    name: Literal["synthetic", "nta_profiles", "ehcvm"]
    def available(self) -> bool: ...
    def initial_distributions(self) -> InitDistributions: ...
    def direct_parameters(self) -> dict[str, Any]: ...
    def targets(self, pattern_ids: Sequence[str]) -> dict[str, pa.Table]: ...

@dataclass(frozen=True)
class InitDistributions:                         # ce que consomme le générateur (§3.2)
    template_weights: dict[str, float] | None    # None ⇒ poids de population.yaml
    wages: Callable[[str, EmploymentStatus], Distribution]          # (rôle, emploi) → loi du salaire
    employment_shares: Callable[[str], dict[EmploymentStatus, float]]
    assets: Distribution                         # pot, épargne, dette (corrélés au revenu)
```

- `synthetic` construit `InitDistributions` depuis `population.yaml` (`synthetic.*`, dont `wage_sigma_scale`) ; toujours disponible.
- `nta_profiles` et `ehcvm` lisent `data/processed/init/*.parquet` (`household_compositions`, `wages`, `assets`) et `data/processed/targets/*.parquet` (40 §4.3), produits par `python -m family_abm.population.prepare {nta|ehcvm}`.
- **Repli :** `resolve_source(cfg)` (40 §4.1) : source demandée indisponible ⇒ `synthetic`, avertissement journalisé, `data_source` = source effective et `run.json.data_fallback = {requested, used, reason}` (04 §4). Ce repli est aussi l'étape 4 de l'ordre d'abandon (§14).

Note : `DataSource` est un **adaptateur de données**, pas un point de variation comportementale (S1 reste respecté).

### 3.4 `config/population.yaml` (complet)

```yaml
n_households: 1                       # défaut : un foyer ; E7/E9 surchargent population.n_households ∈ {100, 1000}
source: synthetic                     # surcharge de data.source pour la population
templates:
  - key: baseline_6
    weight: 0.35
    members:
      - { profile_by_age: true, role: father,      age: 45, employment: employed_formal }
      - { profile_by_age: true, role: mother,      age: 40, employment: employed_informal }
      - { profile_by_age: true, role: young_adult, age: 20, employment: student }
      - { profile_by_age: true, role: adolescent,  age: 15, employment: student }
      - { profile_by_age: true, role: child,       age: 9,  employment: student }
      - { profile_by_age: true, role: baby,        age: 1,  employment: inactive }
  - key: young_couple_2
    weight: 0.20
    members:
      - { role: father, age: 30, employment: employed_informal }
      - { role: mother, age: 26, employment: employed_informal }
      - { role: child,  age: 4,  employment: inactive }
      - { role: baby,   age: 1,  employment: inactive }
  - key: mature_4
    weight: 0.25
    members:
      - { role: father,      age: 55, employment: employed_formal }
      - { role: mother,      age: 50, employment: inactive }
      - { role: young_adult, age: 24, employment: employed_informal }
      - { role: adolescent,  age: 17, employment: student }
  - key: large_8
    weight: 0.20
    members:
      - { role: father,      age: 50, employment: employed_informal }
      - { role: mother,      age: 44, employment: employed_informal }
      - { role: young_adult, age: 22, employment: unemployed }
      - { role: young_adult, age: 19, employment: student }
      - { role: adolescent,  age: 15, employment: student }
      - { role: child,       age: 11, employment: student }
      - { role: child,       age: 7,  employment: student }
      - { role: baby,        age: 2,  employment: inactive }
age_jitter_years: { father: 5, mother: 5, young_adult: 2, adolescent: 1, child: 2, baby: 1 }
min_parent_gap: 16                    # années entre la mère et l'aîné
ownership_rule: parents_equal         # parents_equal | head_only  (ω)
head_rule: oldest_earner              # imputation ONU uniquement
synthetic:
  wage_sigma_scale: 1.0               # multiplicateur des sigma ci-dessous (facteur d'hétérogénéité de E7)
  wages:                              # LogNormal(ln(median), sigma × wage_sigma_scale), FCFA/mois
    employed_formal:   { median: 220000, sigma: 0.5 }
    employed_informal: { median: 90000,  sigma: 0.7 }
  employment_shares:
    father:      { employed_formal: 0.30, employed_informal: 0.60, unemployed: 0.10 }
    mother:      { employed_formal: 0.10, employed_informal: 0.55, inactive: 0.35 }
    young_adult: { employed_informal: 0.35, student: 0.40, unemployed: 0.25 }
  assets:
    savings: { median: 100000, sigma: 1.0 }
    pot:     { median: 40000,  sigma: 0.6 }
    loan_share_indebted: 0.25         # part des foyers endettés à t0
    loan:    { median: 150000, sigma: 0.8 }
  assets_income_corr: 0.5
parallel_households: false           # §11 : blocs de foyers en parallèle intra-run (test d'égalité obligatoire)
sampling:
  decisions_households: 5             # foyers dont les traces de décision sont collectées
  ledger_households: 20               # foyers dont le Ledger est collecté (au-delà : agrégats seulement)
provenance: PLACEHOLDER
```

`profile_by_age: true` est la valeur par défaut pour tous les membres (le profil vient de l'âge et de `profile_transitions`, D1).

### 3.5 Tests (élément 2)

`test_generator_deterministic` (même seed ⇒ mêmes specs) · `test_household_independence` (foyer k seul ≡ foyer k dans N) · `test_template_weights_respected` (χ² à 1 %, N = 10 000) · `test_age_coherence` · `test_source_fallback` (EHCVM absent ⇒ synthetic + avertissement + métadonnée) · `test_nta_age_profile_coverage` (N = 1 000 ⇒ ≥ 30 personnes-années pour chaque âge 0–70 sur 20 ans, sinon avertissement).

## 4. Élément 3 — Calibration et POM

Spécifié dans **`40_SPEC_VALIDATION_CALIBRATION.md`** (Morris → ~8 libres → grille/LHS → perte sur P1–P3 → validation P4–P6, `CalibrationLeakError`, expérience jumelle, Sobol post-calibration). Contraintes propres à la V3 :

- La calibration s'exécute **sur la population** (N = 1 000 par défaut, 10 réplications par candidat), jamais sur un foyer seul.
- Les paramètres V3 calibrables sont ceux du registre marqués `CALIBRATE` : `affect.modulation.horizon`, `affect.modulation.alternatives`, `affect.stress.decay`, `profiles.*.stress_sensitivity`. `risk.lambda` (traitement d'E5) et `profiles.*.planning_horizon` / `max_alternatives` (traitement d'E2/E9) sont **exclus** par le chargeur.
- `affect.modulation.form` n'est jamais calibré (choix structurel).

## 5. Élément 4 — Régime « sphères séparées »

### 5.1 Transition (`agents/household.py`, Temps 2, après les intérêts et **avant la mise en commun** — étape 3b de 10 §8.1, car le régime modifie le pooling)

```
s̄ = moyenne de S des propriétaires (ownership ω > 0)
NORMAL → SEPARATE_SPHERES  si s̄ > s* pendant enter_months mois consécutifs
SEPARATE_SPHERES → NORMAL  si s̄ < s* − hysteresis pendant exit_months mois consécutifs
```

Événement `regime_change` (origin `endogenous`). Compteur `HouseholdState.stress_months`.

### 5.2 Allocation en régime dégradé

Même fonction `allocate()` (S1), appliquée par sous-budget :

1. `pooling_rate` de chaque apporteur remplacé par `min(pooling_rate, pooling_in_regime)` ; la part non mise en commun reste dans son portefeuille.
2. Budget de la sphère p (pour chaque parent listé dans `spheres`) = `pot × ω_p` + portefeuille de p.
3. Chaque demande est routée vers la sphère dont la liste contient son besoin ; COMMITMENT (logement, dette) suit `housing`/`security` → sphère du père par défaut (donnée).
4. Demande d'un besoin listé dans aucune sphère : `REFUSED`, raison `sphere_not_owner`.
5. L'emprunt automatique reste accessible à la sphère qui porte `security` (donnée).

Ledger : les paiements d'une sphère partent du portefeuille du parent (`PRIVATE_CONSUMPTION` wallet→market, `beneficiary` = bénéficiaire) ou du pot ; l'attribution NTA (§9 du modèle de domaine) reste inchangée — un paiement du portefeuille de p au bénéfice de j ≠ p est enregistré comme **transfert intra en nature p→j** par `nta/attribution.py` (règle ajoutée, voir §15).

### 5.3 Tests

`test_regime_hysteresis` (pas d'oscillation sous bruit autour de s*) · `test_spheres_same_allocate` (le régime appelle `allocate`) · `test_spheres_invariants` (identités V-2 valides en régime dégradé) · `test_spheres_disabled` (aucun changement de régime).

## 6. Élément 5 — Repère d'efficacité collective (E8) — `analysis/efficiency.py`

**Ex post, sur les tables de sortie uniquement (D2, D7).** Ne rétroagit jamais sur la simulation.

Pour chaque foyer et chaque pas : budget effectivement dépensé `B_t` (consommation privée + épargne du pas, depuis `demands`/`household_steps`), demandes du pas. Le repère résout :

```
max_{x_ik ≥ 0}  W(x) = Σ_i w_i Σ_k π_ik · log(ε + n̂_ik(x_ik))
s.c.            Σ_i Σ_k x_ik ≤ B_t ;  x_ik ≤ requested_ik ;  indivisibles ∈ {0, requested}
n̂_ik(x) = ρ_k·level_ik,t−1 + (1−ρ_k)·min(1, x / r_k(âge_i))
```

`w_i` = poids de négociation du pas, `π_ik` = poids de rang, `ε = 1e-3`. Résolution : relaxation continue (`scipy.optimize.minimize`, SLSQP) puis arrondi glouton des indivisibles ; documenté comme **repère approché**.

Distance : `gap_t = (W* − W_sim) / |W*|`. Métriques : moyenne et quantiles de `gap`, corrélation de Spearman `gap ~ parent_stress_mean`, `gap ~ essential_unmet`. Table `efficiency_gap` (`run_id, step, household_id, w_star, w_sim, gap`) — à ajouter au catalogue (§15).

Tests : `test_efficiency_upper_bound` (W* ≥ W_sim à tolérance solveur près) ; `test_efficiency_trivial` (budget ≥ demandes ⇒ gap ≈ 0).

## 7. Élément 6 — CPT sur 4 décisions binaires — `decision/risk.py`

Activé par `risk.cpt.enabled` (et capacité `RISK_EVAL`). Sinon, ces décisions sont prises par une règle par défaut neutre au risque (valeur espérée, `λ = 1`, `w(p) = p`) — ce qui fait de E5 un contraste propre.

### 7.1 Formes (Tversky & Kahneman 1992 — `FIX_LIT`)

```
v(x) = x^α           si x ≥ 0
v(x) = −λ_eff·(−x)^α si x < 0                 α = 0.88, λ = 2.25 (λ_eff après modulation par la peur)
w⁺(p) = p^γ⁺ / (p^γ⁺ + (1−p)^γ⁺)^(1/γ⁺)      γ⁺ = 0.61
w⁻(p) = p^γ⁻ / (p^γ⁻ + (1−p)^γ⁻)^(1/γ⁻)      γ⁻ = 0.69
V(option) = Σ_gains π⁺ v(x) + Σ_pertes π⁻ v(x)   (pondération cumulative, issues triées)
```

Montants exprimés en **FCFA relatifs au point de référence**, normalisés par `ref_scale` = consommation mensuelle de référence (pour que `x^α` ait une échelle sans dimension). Point de référence = `MemoryService.reference_level("consumption")` (moyenne pondérée par activation des épisodes de consommation du foyer, V2 §mémoire) ; repli = moyenne 12 mois si mémoire vide. Flux futurs actualisés par δ du décideur.

### 7.2 Les quatre décisions (décideur : parent avec `RISK_EVAL` de poids d'allocation maximal)

| Décision | Déclencheur (Temps 1) | Option A | Option B | Effet si choisie |
|---|---|---|---|---|
| `TAKE_LOAN` | manque essentiel prévu > 0 et marge de crédit formel | sans prêt : perte certaine = manque essentiel × `essential_loss_weight` | prêt L = manque : gain immédiat 0 (besoin couvert) ; pertes = intérêts actualisés ; avec p_default : pénalité `default_penalty` × L | `BORROWING` explicite (au lieu de l'emprunt automatique) |
| `JOIN_MUTUELLE` | annuel (mois `decision_month`), si non adhérent | ne pas adhérer : perte `episode_cost` avec p = p_épisode foyer sur 12 mois | adhérer : perte certaine = 12 × prime | `in_mutuelle=True` : soins d'épisode couverts à `coverage` ; prime et remboursements enregistrés en `INTER_HOUSEHOLD_TRANSFER` (§15.7) |
| `KEEP_IN_SCHOOL` | adolescent ENROLLED dont les frais ont été refusés ≥ 1 mois | retirer : gain = salaire informel ado sur `horizon_years` ; garder : perte certaine = frais × durée restante, gain incertain = prime salariale `school_wage_premium` avec p = `p_completion` | — | `DROP_SCHOOL`/maintien |
| `JOIN_TONTINE` | annuel, si `SAVE` et non membre | ne pas adhérer : 0 | adhérer : perte certaine = cotisation mensuelle × cycle ; gain = cagnotte à un mois tiré (flux `rng["tontine"]`, 01 §7) ; perte totale avec p_default | `in_tontine=True`, écritures `INTER_HOUSEHOLD_TRANSFER` (cotisation sortante, cagnotte entrante) |

L'option retenue est celle de V maximal ; égalité → statu quo. La décision est consignée dans `DecisionTrace.cpt` (`{"decision": …, "V_A": …, "V_B": …, "ref": …, "lambda_eff": …}`) et `rule="cpt"`.

### 7.3 `config/risk.yaml` (complet)

```yaml
cpt:
  enabled: false                 # E5 l'active ; défaut : règle neutre au risque
  alpha: 0.88                    # FIX_LIT T&K 1992 (même α pour gains et pertes)
  lambda: 2.25                   # FIX_LIT — surchargé par profiles.*.risk.lambda ; E5 : {1.0, 2.25, 3.0}
  gamma_gain: 0.61               # FIX_LIT
  gamma_loss: 0.69               # FIX_LIT
  ref_fallback_months: 12
decisions:
  take_loan:
    enabled: true
    essential_loss_weight: 1.5   # PLACEHOLDER — coût perçu d'un besoin essentiel non couvert, en multiples du manque
    p_default: 0.10              # PLACEHOLDER
    default_penalty: 0.5         # PLACEHOLDER
  join_mutuelle:
    enabled: true
    decision_month: 1            # mois de l'année
    premium_monthly: 3500        # PLACEHOLDER — FCFA par foyer
    coverage: 0.8
  keep_in_school:
    enabled: true
    horizon_years: 10
    school_wage_premium: 0.3     # PLACEHOLDER
    p_completion: 0.6            # PLACEHOLDER
    adolescent_informal_wage: 30000
  join_tontine:
    enabled: true
    decision_month: 1
    contribution_monthly: 10000  # PLACEHOLDER
    cycle_months: 10
    p_default: 0.05
provenance: PLACEHOLDER
source: "α, λ, γ : Tversky & Kahneman (1992)"
```

### 7.4 Tests

`test_cpt_value_function` (valeurs de référence calculées à la main) · `test_cpt_neutral_equals_ev` (λ=1, α=1, γ=1 ⇒ V = espérance) · `test_loss_aversion_direction` (λ↑ ⇒ option à perte certaine plus faible préférée, scénario construit) · `test_cpt_disabled_rule` · `test_tontine_ledger_balanced`.

## 8. Élément 7 — Chocs de santé avec rétroaction cognitive

`health/health.py`, appliqué au Temps 1 après l'appraisal du pas précédent (le stress de t−1 agit sur la santé de t, pour éviter une simultanéité) :

```
health ← clip( health − h_s · max(0, S_{t−1} − S0), 0, 1 )
labor_capacity = clip((health − h_min)/(1 − h_min), 0, 1)       (inchangé, V1)
```

Côté appraisal, un épisode de maladie d'un membre augmente `p` (menace) du parent décideur : croyance `child_sick:<id>` (V2) → `p ← max(p, conf(child_sick)·sick_threat_weight)` (`appraisal.sick_threat_weight`, §15). Boucle fermée : stress → santé → capacité de travail → revenu → contrainte → stress.

Tests : `test_health_feedback_off` ; `test_health_feedback_lag` (effet visible au pas suivant seulement).

## 9. Élément 8 — Extension d'échelle par dégradation cognitive contrôlée (E9)

Aucun nouveau mécanisme : facteurs `model.version ∈ {v1, v2, v3}` × `population.n_households ∈ {100, 1000}` (+ `affect.enabled`, `cognition.bdi.enabled` pour niveaux intermédiaires). Le runner est celui de `50_SPEC_EXPERIMENTS.md`.

Critère : agrégats (Gini, taux de pauvreté, profil LCD — NRMSE au profil v3) comparés au niveau v3 par **TOST** (deux tests unilatéraux) avec marges déclarées **avant** exécution dans `config/experiments/E9.yaml` (`analysis.equivalence.margins`). Le « niveau minimal suffisant » est le plus simple dont tous les agrégats sont équivalents. Sortie complémentaire : courbe coût (s) en fonction de N et du niveau → Chap. 7.

## 10. Non-régression (porte V3, critère n°1)

| Condition | Attendu |
|---|---|
| `model.version=v3`, `affect.enabled=false`, `risk.cpt.enabled=false`, `household_rules.separate_spheres.enabled=false`, `population.n_households=1` | tables `person_steps`, `household_steps`, `ledger`, `nta_person_steps` **identiques bit à bit** à `model.version=v2` (même seed), hors colonnes V3 (à leurs valeurs neutres) |
| idem `model.version=v1` + bascules V2 à false | identique à V1 |
| suites V1 et V2 | toutes vertes |

Implémentation : aucune consommation de nombres aléatoires dans les modules V3 quand ils sont désactivés ; test `test_v3_off_equals_v2` compare des hachages SHA-256 des tables Parquet (colonnes communes, tri `(step, person_id)`).

## 11. Performance — 1 000 foyers × 240 pas

Budget : < 10 min / run sur 1 cœur ; 100 réplications parallélisées.

| Levier | Spécification |
|---|---|
| Parallélisme | **par réplication** (`joblib.Parallel(n_jobs=-1, backend="loky")`, 1 run par processus) ; pas de parallélisme intra-run par défaut (déterminisme simple). Option `population.parallel_households` (blocs de foyers indépendants) permise car les flux RNG sont par foyer — test d'égalité obligatoire. |
| Collecte réduite | `output.collect.ledger` limité à `sampling.ledger_households` ; `decisions: sample` ; `person_steps` complet ; NTA calculé pour tous (nécessaire à P1–P6). |
| Invariants échantillonnés | `checks.invariant_run_sample_rate = 0.05` autorisé **après** porte V1 : 5 % des runs vérifiés à chaque pas (tous les foyers) ; les autres runs vérifiés tous les `checks.invariant_period_unsampled` = 12 pas (03 §2). |
| Structures | `__slots__` sur états ; accumulation en listes de tuples, conversion Arrow par blocs de 12 pas ; pas de pandas dans la boucle. |
| Profilage | `tests/performance/test_population_budget.py` (N = 100, extrapolation linéaire déclarée) ; script `scripts/profile_run.py` (`cProfile` + `pyinstrument`), rapport dans `docs/PERF.md`. |
| Mémoire | taille mémoire épisodique bornée par profil ; traces de décision non conservées en mémoire vive au-delà du pas pour les foyers non échantillonnés. |

## 12. Expériences V3 (runner : `50_SPEC_EXPERIMENTS.md`)

### E4 — Boucle affective (centrale)

- Facteurs : `loops.b3.enabled ∈ {false, true}` × amplitude de choc `∈ {0.25, 0.5, 0.75}` (perte de revenu du foyer, événement `income_shock` au mois 36, durée 12 mois) ; variante robustesse : `affect.modulation.form ∈ {linear, sigmoid}`.
- Contrôlé : tous les paramètres économiques, mêmes seeds (100 réplications), foyer de référence puis population.
- Métriques : `recovery_time`, `debt_to_income_terminal`, `horizon_eff` moyen des parents (pendant et après le choc), part du temps en `SEPARATE_SPHERES`.
- **Définition opérationnelle de l'enfermement endogène** (déclarée avant exécution) : `lock_in_flag` (par run, 0/1) = 1 si `recovery_time` est censuré à l'horizon (consommation jamais revenue à 95 % du niveau pré-choc) **ou** si `debt_to_income` est strictement croissant sur les 24 derniers mois. Un run B3 est « enfermé de façon endogène » si `lock_in_flag = 1` **alors que** le run apparié (même seed, même choc, `b3=false`) a `lock_in_flag = 0`. Indicateur de cellule : `lock_in_rate` = part des paires (seed) enfermées avec B3 et non sans B3 ; rapporté avec intervalle de confiance (Wilson). Il est aussi rapporté le cas inverse (récupère avec B3, pas sans), pour ne pas tester une seule direction.
- **Aucun résultat n'est prédit.** Une absence d'enfermement est un résultat rapporté, analysé via la sensibilité aux paramètres `affect.modulation.*`.

### E5 — Décision sous risque (si élément 6)
λ ∈ {1.0, 2.25, 3.0} ; métriques : taux d'acceptation de `TAKE_LOAN`, délai avant `SAVING_WITHDRAWAL`, adhésion mutuelle/tontine.

### E7 — Population (validation principale)
N ∈ {100, 1 000} × hétérogénéité des dotations (`synthetic.wage_sigma_scale` ∈ {0.5, 1}) ; métriques : `nta_age_profile`, `gini_income`, `poverty_rate` ; comparaison au profil cible (P1–P6) selon `40_SPEC`.

### E8 — Écart à l'efficacité (si élément 5)
Population N = 1 000 ; métriques §6.

### E9 — Dégradation cognitive (si élément 8)
§9.

## 13. Critères de sortie V3 (porte, contraignants)

- [ ] Tous les critères V1 et V2 restent verts ; `test_v3_off_equals_v2` vert
- [ ] Appraisal, émotions, stress, modulation implémentés, décrits dans l'ODD-V3, testés (§2.7)
- [ ] **E4 exécutée et rapportée, quel que soit son résultat**, avec la définition d'enfermement figée avant exécution
- [ ] Profil LCD agrégé sur **≥ 1 000 foyers** produit et comparé à une cible
- [ ] ≥ **3** patterns POM reproduits avec un seul jeu de paramètres, dont **≥ 1 du set validation** (`40_SPEC`)
- [ ] Séparation calibration/validation documentée et respectée (hash de `patterns.yaml` inchangé)
- [ ] 1 000 foyers × 240 pas dans le budget §11 ; mesure consignée dans `docs/PERF.md`
- [ ] ODD-V3 complet et cohérent avec le code

## 14. Risques V3 et ordre d'abandon

| Risque | Signe précurseur | Parade |
|---|---|---|
| Formes de modulation arbitraires | conclusions d'E4 changent avec `form` | rapporter les deux formes ; sensibilité Morris sur `affect.modulation.*` ; Chap. 9 |
| Sur-paramétrage affectif (R2) | +12 paramètres sans effet mesurable | Morris élimine ; ne calibrer que `CALIBRATE` |
| Prédiction de E4 (R12) | résultat attendu écrit au Chap. 8 avant le run | définition d'enfermement seule, figée dans `E4.yaml` |
| Coût de calcul | run 1 000 foyers > 10 min | §11 ; repli N = 500 déclaré |
| Données réelles absentes (R9) | EHCVM non reçue en Phase 9 | repli `synthetic`/`nta_profiles`, dit clairement |

**Ordre d'abandon si glissement > 2 semaines (feuille de route §22)** : 1. E5 (CPT) → 2. E8 (efficacité) → 3. E9 (Chap. 7 en conception + perspective) → 4. calibration EHCVM (repli population paramétrée sur profils NTA publiés) → 5. V3 entière (prototype démonstratif + Chap. 9). **Ne saute jamais** : critères V1/V2, sensibilité, séparation calibration/validation.

## 15. Détails tranchés dans ce document

1. **Timing** : appraisal au Temps 1 sur la satisfaction issue des allocations du pas précédent ; rétroaction santé décalée d'un pas (S_{t−1}).
2. **Poids de rang** `π_k = 1/(1+ρ_k)` pour l'appraisal (les notes partagées ne fixaient pas la forme).
3. `aspiration_scale` n'altère pas `θ_k` stocké : il ne s'applique qu'au test d'acceptabilité (évite une interaction cachée avec l'adaptation V2).
4. `round` = arrondi bancaire Python ; `floor` pour H.
5. Membres sans `APPRAISE` : affect neutre ; le stress parental moyen (`parent_stress_mean`) est la moyenne sur les **propriétaires** (ω > 0).
6. **Attribution NTA en régime dégradé** : un paiement depuis le portefeuille de p au bénéfice de j ≠ p est un transfert intra en nature p→j — règle à ajouter à `nta/attribution.py` et à `02_DOMAIN_MODEL.md` §9 (le rédacteur V1/coordinateur doit la reporter).
7. **Mutuelle** : la couverture d'un épisode est enregistrée comme `INTER_HOUSEHOLD_TRANSFER` entrant (mutuelle = pool d'autres ménages, compte `OTHER_HOUSEHOLDS`) et la prime comme `INTER_HOUSEHOLD_TRANSFER` sortant — pas de nouveau compte. Idem tontine.
8. `appraisal.sick_threat_weight` (défaut 0.5, PLACEHOLDER) — inclus dans `config/affect.yaml` §2.6.
9. Nouvelle table `efficiency_gap` (§6), métrique de run `lock_in_flag` et métrique de cellule `lock_in_rate` (§12, E4) — reportées dans `04_DATA_MODEL.md`.
10. Invariants en population : 5 % des runs à chaque pas + tous les runs tous les 12 pas.
11. Règle par défaut (CPT désactivée) : valeur espérée neutre au risque, pour que E5 contraste CPT vs EV et non CPT vs absence de décision.
