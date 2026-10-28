# 03 — Configuration : schémas et valeurs par défaut

> **Règle :** aucun nombre du modèle n'est écrit dans le code (`src/`). Tout paramètre vit dans `config/*.yaml`, est validé par un modèle Pydantic v2 `frozen=True` (`config/schemas.py`) et porte une **provenance**.
>
> **Avertissement :** les valeurs monétaires ci-dessous sont des **placeholders** plausibles (`provenance: PLACEHOLDER`) destinés à faire tourner la V1. Elles doivent être remplacées par des valeurs issues des profils NTA Sénégal (CREFAT) ou de l'EHCVM dès que les données sont disponibles (`provenance: DIRECT`, avec `source:` renseigné). Un run dont la configuration contient au moins un `PLACEHOLDER` est marqué `illustrative: true` dans ses métadonnées, et l'UI l'affiche.

---

## 1. Conventions

- Montants : FCFA par **mois**, sauf mention `_annual`.
- Taux : décimaux (`0.18` = 18 %). Les taux annuels sont convertis en mensuels par `(1 + r)^(1/12) − 1` dans `economy/`, jamais dans le YAML.
- Âges : en **années** dans le YAML ; en mois dans le modèle.
- Chaque bloc numérique peut porter `provenance: PLACEHOLDER | DIRECT | CALIBRATED | FIX_LIT | EXPLORED` et `source: "…"`.
- Surcharge : un scénario ou une expérience modifie la configuration par **chemins pointés** (`economic_params.wages.father: 180000`). Le `loader` applique les surcharges puis revalide l'ensemble.
- **Espaces de noms des chemins pointés (normatif, B1) :** le premier segment est le **nom du fichier** sans extension — `economic_params.`, `household_rules.`, `needs.`, `plans.`, `affect.`, `risk.`, `population.`, `patterns.` — **sauf** deux exceptions : `simulation.yaml`, dont les clés sont à la racine (`model.version`, `horizon_months`, `seed`, `data.*`, `loops.*`, `cognition.*`, `nta.*`, `checks.*`, `output.*`), et `cognitive_profiles.yaml`, préfixé `profiles.`. **Interdit :** une clé racine de `simulation.yaml` portant le nom d'un autre fichier (`affect`, `risk`, `population`, `needs`…). Les bascules propres à un fichier vivent dans ce fichier : `affect.enabled` (affect.yaml), `risk.cpt.enabled` (risk.yaml), `population.n_households` (population.yaml ; vaut 1 si le fichier est absent ou si `model.version` < v3), `household_rules.separate_spheres.enabled`.
- Les fichiers `needs.yaml`, `affect.yaml`, `risk.yaml`, `population.yaml` n'ont **pas** de clé racine portant leur propre nom : leur contenu commence directement par leurs sections (ex. `needs.food.persistence`, `affect.modulation.horizon`).
- Empreinte : `ConfigHash = sha256(json canonique de la config résolue)` ; stockée dans chaque run.

## 2. `config/simulation.yaml`

```yaml
model:
  version: v1                    # v1 | v2 | v3 — active les blocs correspondants
horizon_months: 240              # D12 : 120 | 240 | cycle de vie
seed: 42
demography:
  mode: fixed_cohort             # Q5 — seule valeur implémentée
data:
  source: synthetic              # Q6 : synthetic | nta_profiles | ehcvm
loops:                           # bascules des boucles (S8)
  b2: { enabled: true }          # ignoré si version < v2
  b3: { enabled: true }          # ignoré si version < v3
cognition:
  bdi: { enabled: true }         # V2
  memory: { enabled: true }      # V2
  discounting: { enabled: false }# V2 optionnel (β-δ) — E3
# NB (B1) : les bascules affect.enabled, risk.cpt.enabled et population.n_households
#            vivent dans affect.yaml, risk.yaml et population.yaml, pas ici.
checks:
  invariants: true                   # vérification active ; violation ⇒ échec dur
  invariant_run_sample_rate: 1.0     # fraction des runs vérifiés à CHAQUE pas (< 1 autorisé seulement après porte V1, campagnes SA/population)
  invariant_period_unsampled: 12     # les autres runs sont vérifiés tous les N pas (les invariants ne sont jamais totalement désactivés)
output:
  dir: experiments/results
  collect:
    person_steps: true
    household_steps: true
    ledger: true                 # désactivable pour population > 100 foyers
    decisions: sample            # all | sample | none — sample = foyers échantillonnés
    decisions_sample_households: 5
    nta: true
```

## 3. `config/cognitive_profiles.yaml`

Un profil = un jeu de paramètres. **Aucun code ne connaît les noms de profils** ; le foyer initial référence un profil par clé.

```yaml
profiles:
  baby:
    capabilities: [consume, seek_care]
    max_alternatives: 1          # réactif pur : 1 alternative, horizon 0 (audit, problème 2)
    planning_horizon: 0          # mois
    aspiration_init: 0.60
    aspiration_adapt: { up: 0.0, down: 0.0, min: 0.3, max: 0.9 }
    impulsivity: 1.0
    memory: { capacity: 0, decay: 0.5, retrieval_threshold: -1.0 }
    intention_commitment: 0.0
    discounting: { mode: none, beta: 1.0, delta: 1.0 }
    risk: { lambda: 1.0, alpha: 0.88 }
    stress_sensitivity: 0.0
    attended_needs: [food, health, rest]
  child:
    capabilities: [consume, seek_care, study, rest, remember]   # mémoire simple (capacité 10) — « cognition simple ; apprentissage » (DOC §3)
    max_alternatives: 2
    planning_horizon: 1
    aspiration_init: 0.60
    aspiration_adapt: { up: 0.05, down: 0.10, min: 0.3, max: 0.9 }
    impulsivity: 0.7
    memory: { capacity: 10, decay: 0.5, retrieval_threshold: -1.0 }
    intention_commitment: 0.2
    discounting: { mode: exponential, beta: 1.0, delta: 0.99 }
    risk: { lambda: 2.25, alpha: 0.88 }
    stress_sensitivity: 0.2
    attended_needs: [food, health, education, rest]
  adolescent:
    capabilities: [consume, seek_care, study, rest, remember, plan, appraise]
    max_alternatives: 3
    planning_horizon: 3
    aspiration_init: 0.65
    aspiration_adapt: { up: 0.10, down: 0.15, min: 0.3, max: 0.95 }
    impulsivity: 0.6             # FIX_LIT puis EXPLORED (Steinberg)
    memory: { capacity: 20, decay: 0.5, retrieval_threshold: -1.0 }
    intention_commitment: 0.3
    discounting: { mode: naive, beta: 0.7, delta: 0.995 }
    risk: { lambda: 2.25, alpha: 0.88 }
    stress_sensitivity: 0.5
    attended_needs: [food, rest, education, health]
  young_adult:
    capabilities: [work, consume, save, seek_care, study, rest, seek_job, borrow_request,
                   remember, plan, appraise, risk_eval, leave_household]
    max_alternatives: 5
    planning_horizon: 12
    aspiration_init: 0.65
    aspiration_adapt: { up: 0.10, down: 0.15, min: 0.3, max: 0.95 }
    impulsivity: 0.3
    memory: { capacity: 40, decay: 0.5, retrieval_threshold: -1.0 }
    intention_commitment: 0.6
    discounting: { mode: naive, beta: 0.85, delta: 0.995 }
    risk: { lambda: 2.25, alpha: 0.88 }
    stress_sensitivity: 0.5
    attended_needs: [food, education, health, security, rest]
  mother:
    capabilities: [work, consume, save, seek_care, rest, seek_job, borrow_request,
                   remember, plan, appraise, risk_eval]
    max_alternatives: 8
    planning_horizon: 24
    aspiration_init: 0.70
    aspiration_adapt: { up: 0.10, down: 0.15, min: 0.3, max: 0.95 }
    impulsivity: 0.2
    memory: { capacity: 60, decay: 0.5, retrieval_threshold: -1.0 }
    intention_commitment: 0.8
    discounting: { mode: sophisticated, beta: 0.95, delta: 0.995 }
    risk: { lambda: 2.25, alpha: 0.88 }
    stress_sensitivity: 0.6
    attended_needs: [food, health, housing, security, rest]
  father:
    capabilities: [work, consume, save, seek_care, rest, seek_job, borrow_request,
                   remember, plan, appraise, risk_eval]
    max_alternatives: 8
    planning_horizon: 24
    aspiration_init: 0.70
    aspiration_adapt: { up: 0.10, down: 0.15, min: 0.3, max: 0.95 }
    impulsivity: 0.2
    memory: { capacity: 60, decay: 0.5, retrieval_threshold: -1.0 }
    intention_commitment: 0.8
    discounting: { mode: sophisticated, beta: 0.95, delta: 0.995 }
    risk: { lambda: 2.25, alpha: 0.88 }
    stress_sensitivity: 0.6
    attended_needs: [food, housing, health, security, rest]
provenance: PLACEHOLDER          # sauf risk.lambda/alpha : FIX_LIT (Tversky & Kahneman 1992)
```

**Paramètres actifs par version** (les autres sont lus mais sans effet — documenté dans l'ODD) :

| Paramètre | V1 | V2 | V3 |
|---|:-:|:-:|:-:|
| `capabilities`, `max_alternatives`, `planning_horizon`, `attended_needs`, `aspiration_init`, `impulsivity` | ✔ | ✔ | ✔ |
| `aspiration_adapt`, `memory.*`, `intention_commitment` | — | ✔ | ✔ |
| `discounting.*` | — | ✔ (si activé) | ✔ |
| `risk.*`, `stress_sensitivity` | — | — | ✔ |

## 4. `config/household_rules.yaml` — composition et règles du foyer

```yaml
baseline_household:              # foyer de référence (DOC §3) — âges à t0, en années
  members:
    - { key: father,      profile: father,      age: 45, employment: employed_formal,   wage_key: father }
    - { key: mother,      profile: mother,      age: 40, employment: employed_informal, wage_key: mother }
    - { key: young_adult, profile: young_adult, age: 20, employment: student,           wage_key: young_adult }
    - { key: adolescent,  profile: adolescent,  age: 15, employment: student }
    - { key: child,       profile: child,       age: 9,  employment: student }
    - { key: baby,        profile: baby,        age: 1,  employment: inactive }
  initial_assets: { pot: 50000, savings: 150000, loan: 0 }
  head: father                   # pour l'imputation ONU uniquement
  ownership: { father: 0.5, mother: 0.5 }   # parts ω du pot commun (attribution comportementale)

pooling:                         # part du revenu du travail versée au pot
  father: 1.0
  mother: 0.8
  young_adult: 0.5

profile_transitions:             # le profil suit l'âge (cohorte fixe, 20 ans) — donnée, pas code
  - { from: baby,       to: child,       at_age: 5 }
  - { from: child,      to: adolescent,  at_age: 13 }
  - { from: adolescent, to: young_adult, at_age: 18 }
  # young_adult → (pas de transition dans l'horizon par défaut)

allocation:
  mode: fixed_weights            # unitary | fixed_weights | variable_weights  (E6)
  weights:                       # poids initiaux (normalisés au chargement)
    father: 1.0
    mother: 1.0
    young_adult: 0.8
    adolescent: 0.7
    child: 0.6
    baby: 0.6
  variable_weights:              # V2 : w_i = normalise(w0_i · (1 + γ · part_revenu_i))
    gamma: 1.0
  unitary:
    priority_owner: father       # ordre de priorité des besoins appliqué à tous (désirs du décideur)
  tier_order: [commitment, essential, education, other, saving]
  rationing: weighted_proportional   # dans un palier insuffisant : au prorata poids × demande, puis plancher amount_min

credit:
  limit_months_income: 3.0       # κ
  annual_rate: 0.18              # PLACEHOLDER — microcrédit / informel
  min_repayment_share: 0.05      # échéance minimale = min_repayment_share × (dette_{t−1} + intérêts du mois) (G12)
  borrow_for_tiers: [essential]  # V1 : emprunt automatique seulement pour l'essentiel
savings:
  annual_rate: 0.03
  target_buffer_months: 3        # sert au besoin SECURITY

separate_spheres:                # V3 — Lundberg & Pollak (1993)
  enabled: true
  stress_threshold: 0.6          # s*
  enter_months: 3
  exit_months: 3
  hysteresis: 0.1
  spheres:                       # qui finance quoi en régime dégradé
    father: [housing, security]
    mother: [food, health, education]
  pooling_in_regime: 0.4         # pooling réduit pour tous les apporteurs

young_adult_can_leave: false     # D13
leave_rule:                      # V2, si true
  min_age: 22
  min_months_employed: 12
  remittance_share: 0.1          # part du revenu envoyée au foyer d'origine (INTER_HOUSEHOLD_TRANSFER)
provenance: PLACEHOLDER
```

## 5. `config/needs.yaml`

Le fichier n'a pas de clé racine `needs:` (B1) : chemins `needs.food.persistence`, etc. Toutes les clés de premier niveau sont des besoins (le joker `needs.*` du registre les parcourt).

```yaml
food:
  tier: essential
  divisible: true
  persistence: 0.5               # ρ : level_t = ρ·level_{t-1} + (1−ρ)·satisfaction_t
  active_ages: [0, 120]
  reduced_share: 0.7             # niveau « réduit » d'un panier = 0.7 × r_k (10 §7.3)
  amount_min_share: 0.5          # amount_min = 0.5 × r_food (10 §7.3)
health:
  tier: essential                # soins urgents (épisode de maladie) ; soins préventifs (routine) = other
  divisible: false               # un épisode de soin est tout ou rien
  persistence: 0.8
  active_ages: [0, 120]
  reduced_share: 0.7             # routine
  amount_min_share: 0.0          # routine ; l'épisode est indivisible (amount_min = r)
  sat_untreated_factor: 0.2      # malade sans soin : sat = 0.2 × min(1, routine payée / r_routine) (10 §4)
education:
  tier: education
  divisible: false               # frais de scolarité mensualisés indivisibles
  persistence: 0.9
  active_ages: [5, 25]           # restreint en plus par SchoolStatus
housing:
  tier: commitment               # loyer/énergie : engagement du foyer, réparti par échelle d'équivalence
  divisible: false
  persistence: 0.9
  active_ages: [0, 120]
rest:
  tier: other
  divisible: true
  persistence: 0.5
  active_ages: [0, 120]
  monetary: false                # sat_rest = clip(1 − labor_slope·max(0, labor_supply − labor_threshold) − fatigue, 0, 1) (10 §4)
  labor_threshold: 0.8
  labor_slope: 0.6
security:
  tier: saving
  divisible: true
  persistence: 0.9
  active_ages: [18, 120]
  monetary: true                 # satisfaction = min(1, épargne / (target_buffer_months × dépense mensuelle))
  saving_horizons_months: [12, 24]   # options d'épargne d'un panier : écart/12, écart/24, 0 (10 §7.3)
```

## 6. `config/economic_params.yaml`

```yaml
currency: XOF
wage_scale: 1.0                  # multiplicateur appliqué à TOUS les salaires (facteur de budget_pressure, E6/E8)
employment:
  min_work_age: 15               # âge minimal pour passer de STUDENT/DROPPED_OUT à UNEMPLOYED (10 §3)
wages:                           # salaire mensuel à plein temps à t0 (× wage_scale)
  father: 250000
  mother: 120000
  young_adult: 60000             # quand employé
wage_growth_annual: 0.02
income_shocks:
  formal:   { p_loss_monthly: 0.004, p_find_monthly: 0.05 }
  informal: { p_loss_monthly: 0.010, p_find_monthly: 0.10, volatility: 0.15 }  # revenu informel ~ LogNormal(0, σ)
  find_formal_share: 0.2         # part des retours à l'emploi qui sont formels
tax:
  formal_rate: 0.10              # PLACEHOLDER
  informal_rate: 0.0
prices:
  inflation_annual: 0.02
consumption_requirements:        # r_k(âge) : coût mensuel pour satisfaction = 1 (FCFA, prix t0)
  food:      { by_age: [[0, 15000], [5, 22000], [13, 30000], [18, 35000], [60, 30000]] }
  health:    { routine_by_age: [[0, 3000], [5, 2000], [18, 3000], [50, 6000]], episode_cost: [[0, 25000], [18, 40000]] }
  education: { by_age: [[5, 8000], [12, 15000], [16, 25000], [19, 40000]] }   # privé + fournitures
  rest:      { by_age: [[0, 0]] }    # non monétaire
housing:
  monthly_cost_household: 90000  # loyer + énergie, payé par le pot (COMMITMENT)
  equivalence_scale: oecd_modified
  equivalence_weights: { first_adult: 1.0, other_adult: 0.5, child: 0.3, adult_age: 14 }
public:
  inkind_by_age:                 # Cg : consommation publique en nature (PUBLIC_INKIND)
    education: [[6, 6000], [12, 9000], [16, 12000]]   # si ENROLLED
    health:    [[0, 2000], [5, 1000], [60, 3000]]
  cash_transfers: []             # surchargé par le scénario family_allowance
  # schéma d'un élément de cash_transfers :
  #   { from_step: int, to_step: int | null, per_child_under: int | null (âge, années),
  #     amount: FCFA/mois (par enfant éligible si per_child_under, sinon par foyer), to: pot | wallet }
health:
  p_episode_monthly_by_age: [[0, 0.06], [5, 0.03], [18, 0.02], [50, 0.04]]
  episode_severity: { mean: 0.25, sd: 0.10, min: 0.05, max: 0.9 }   # perte de santé en début d'épisode (tirage tronqué)
  recovery_with_care: 0.15       # santé regagnée / mois si soin alloué
  recovery_without_care: 0.03
  natural_recovery: 0.01         # récupération mensuelle hors épisode
  recovery_tolerance: 0.05       # guérison si santé ≥ santé pré-épisode − tolérance
  max_episode_months: 6          # durée maximale d'un épisode
  health_min_for_work: 0.3       # h_min dans labor_capacity
  care_paid_by: household        # household | gov — gov ⇒ soins payés en PUBLIC_INKIND (scénario free_care, via policy_change daté)
schooling:
  entry_age: 6
  exit_age: { secondary: 19, tertiary: 25 }
  drop_after_refused_months: 3   # m_drop (V1 : mécanique)
poverty_line_per_eq: 35000       # FCFA/mois/équivalent-adulte — PLACEHOLDER (à remplacer par le seuil ANSD/EHCVM)
provenance: PLACEHOLDER
```

Interpolation des tables `[[âge, valeur], …]` : **constante par morceaux** (valeur du dernier âge ≤ âge courant) — choix explicite, documenté dans l'ODD, pour éviter des sauts artificiellement lissés.

## 7. `config/plans.yaml` (V2) — format

```yaml
plans:
  - id: cope_job_loss/seek_and_cut
    goal: cope_income_loss
    context: "belief.job_lost and not belief.debt_critical"      # mini-DSL, voir 20_SPEC_V2 §7.1
    priority: 1
    body:
      - { action: seek_job }
      - { action: reduce_consumption, need: rest, factor: 0.5 }
      - { subgoal: "satisfy:food" }
    success: "belief.employed"
    failure: "plan.step_failures >= 3"
    max_duration_months: 6
  # … liste complète dans 20_SPEC_V2_COGNITIVE.md §7.3
```

## 8. `config/affect.yaml` et `config/risk.yaml` (V3) — format

Contenus complets : `affect.yaml` en `30_SPEC_V3` §2.6, `risk.yaml` en §7.3. Clés `affect.` : `enabled`, `appraisal.*`, `emotions.decay`, `stress.*`, `mood.*`, `modulation.{form, horizon, alternatives, aspiration, beta, commitment, lambda, sigmoid}`, `health_feedback.*`. Clés `risk.` : celles de 30 §7.3 (dont `risk.cpt.enabled`).

## 9. `config/population.yaml` (V3) — format

Contenu complet : `30_SPEC_V3_AFFECTIVE_POPULATION.md` §3.4. Clés : `n_households`, `source`, `templates[]` (composition, poids), `age_jitter_years`, `min_parent_gap`, `ownership_rule`, `head_rule`, `synthetic.{wage_sigma_scale, wages, employment_shares, assets, assets_income_corr}`, `sampling.*`, `parallel_households`.

## 10. `config/scenarios/*.yaml`

```yaml
# config/scenarios/job_loss.yaml
id: job_loss
label: "Perte d'emploi du père"
description: "Le père perd son emploi formel au mois 36 ; retour à l'emploi selon les probabilités standard."
overrides: {}                    # surcharges de config par chemin pointé
events:
  - { step: 36, type: job_loss, target: { member_key: father } }
```

| Scénario (DOC §6) | `id` | Événements / surcharges |
|---|---|---|
| Référence | `baseline` | aucun |
| Perte d'emploi | `job_loss` | `job_loss` père au mois 36 |
| Maladie grave | `illness` | `health_episode` enfant au mois 48, `severity: 0.6`, `duration: 6` |
| Allocation familiale | `family_allowance` | `economic_params.public.cash_transfers: [{from_step: 24, per_child_under: 15, amount: 10000, to: pot}]` |
| Gratuité des soins | `free_care` | `economic_params.health.care_paid_by: gov` à partir du mois 24 (soins → `PUBLIC_INKIND`) |
| Choc économique | `economic_shock` | `price_shock` +20 % au mois 60 ; `income_shock` informel −15 % au mois 60 |

Types d'événements (`model/events.py`) : `job_loss`, `job_gain`, `health_episode`, `price_shock`, `income_shock`, `policy_change` (surcharge datée), `asset_loss`.

## 11. `config/experiments/E*.yaml` — format générique

```yaml
id: E2
title: "Réactif vs délibératif"
hypothesis: "La persistance des intentions réduit la volatilité de la consommation et augmente le taux d'épargne."
base_scenario: baseline
factors:                         # plan factoriel complet sur ces chemins
  model.version: [v1, v2]
fixed:
  population.n_households: 1
replications: { n: 100, seed_start: 1000 }   # seeds 1000..1099, identiques entre niveaux de facteur
metrics: [consumption_volatility, savings_rate_mean, debt_to_income_terminal]
outputs: [table_metrics, fig_E2_volatility, fig_E2_savings]
```

## 12. `config/parameters_registry.yaml` — registre des paramètres (§13.6 de la feuille de route)

Sert à la fois à l'analyse de sensibilité (bornes), à la calibration (liste des libres) et au garde-fou « on ne calibre jamais une variable de traitement ».

```yaml
parameters:
  - { path: profiles.*.aspiration_init,         bounds: [0.4, 0.9],  treatment: CALIBRATE, sa: true }
  - { path: profiles.*.aspiration_adapt.up,     bounds: [0.0, 0.3],  treatment: CALIBRATE, sa: true }
  - { path: profiles.*.aspiration_adapt.down,   bounds: [0.0, 0.3],  treatment: CALIBRATE, sa: true }
  - { path: profiles.*.memory.capacity,         bounds: [5, 100],    treatment: FIX,       sa: true }
  - { path: profiles.*.memory.decay,            bounds: [0.3, 0.8],  treatment: FIX_LIT,   sa: true }
  - { path: profiles.*.planning_horizon,        bounds: [0, 36],     treatment: EXPLORE,   sa: true, treatment_variable_of: [E2, E9] }
  - { path: profiles.*.max_alternatives,        bounds: [1, 10],     treatment: EXPLORE,   sa: true, treatment_variable_of: [E2, E9] }
  - { path: profiles.*.impulsivity,             bounds: [0.0, 1.0],  treatment: FIX_LIT,   sa: true }
  - { path: profiles.*.intention_commitment,    bounds: [0.0, 1.0],  treatment: CALIBRATE, sa: true }
  - { path: profiles.*.discounting.beta,        bounds: [0.5, 1.0],  treatment: EXPLORE,   sa: false, treatment_variable_of: [E3] }
  - { path: profiles.*.risk.lambda,             bounds: [1.0, 3.0],  treatment: FIX_LIT,   sa: false, treatment_variable_of: [E5] }
  - { path: profiles.*.stress_sensitivity,      bounds: [0.0, 1.0],  treatment: CALIBRATE, sa: true }
  - { path: household_rules.allocation.weights.*, bounds: [0.3, 1.5], treatment: CALIBRATE, sa: true }
  - { path: household_rules.allocation.variable_weights.gamma, bounds: [0, 3], treatment: CALIBRATE, sa: true }
  - { path: household_rules.pooling.mother,     bounds: [0.3, 1.0],  treatment: CALIBRATE, sa: true }
  - { path: household_rules.pooling.young_adult,bounds: [0.0, 1.0],  treatment: CALIBRATE, sa: true }
  - { path: household_rules.credit.limit_months_income, bounds: [0, 6], treatment: DIRECT, sa: true }
  - { path: household_rules.credit.annual_rate, bounds: [0.05, 0.40], treatment: DIRECT,   sa: true }
  - { path: economic_params.income_shocks.*.p_loss_monthly, bounds: [0.001, 0.03], treatment: DIRECT, sa: true }
  - { path: economic_params.income_shocks.*.p_find_monthly, bounds: [0.01, 0.2],   treatment: DIRECT, sa: true }
  - { path: economic_params.health.p_episode_monthly_by_age, scale_bounds: [0.5, 2.0], treatment: DIRECT, sa: true }
  - { path: needs.*.persistence,                bounds: [0.3, 0.95], treatment: FIX,       sa: true }
  - { path: affect.modulation.horizon,          bounds: [0.0, 1.0],  treatment: CALIBRATE, sa: true }
  - { path: affect.modulation.alternatives,     bounds: [0.0, 1.0],  treatment: CALIBRATE, sa: true }
  - { path: affect.stress.decay,                bounds: [0.05, 0.5], treatment: CALIBRATE, sa: true }
```

**Sémantique du joker `profiles.*` (G11) :**
- **dans ce registre** (sensibilité, calibration), `profiles.*.x` désigne **un multiplicateur commun** appliqué à la valeur de chaque profil (préserve la gradation bébé→parent), sauf déclaration `per_profile: true` ;
- **dans les facteurs et `fixed` d'une expérience**, `profiles.*.x: v` affecte la **valeur absolue** `v` à tous les profils, et `profiles.{a,b}.x: v` à la sélection explicite des profils `a` et `b` (ex. E3 : `profiles.{adolescent,young_adult,mother,father}.discounting.beta`). Le chargeur refuse une calibration qui inclut un paramètre dont `treatment_variable_of` contient une expérience du plan courant (règle §13.6).

## 13. `config/patterns.yaml` — affectation figée (D10, RV-16)

```yaml
frozen: true                     # toute modification exige de changer assignment_hash ET d'écrire une entrée dans docs/DECISIONS.md
assignment_hash: "<sha256 des couples (id, role)>"
patterns:
  - { id: P1, name: "Signature du LCD par âge",          level: population, role: calibration, metric: lcd_age_profile_nrmse }
  - { id: P2, name: "Revenu du travail par âge",         level: population, role: calibration, metric: yl_age_profile_nrmse }
  - { id: P3, name: "Consommation par âge",              level: population, role: calibration, metric: c_age_profile_nrmse }
  - { id: P4, name: "Orientation et volume des transferts", level: population, role: validation, metric: transfer_direction_by_age }
  - { id: P5, name: "Distribution dette/revenu",         level: population, role: validation, metric: dti_distribution_ks }
  - { id: P6, name: "Distribution reste-à-vivre / pauvreté", level: population, role: validation, metric: poverty_rate_and_rav_ks }
  - { id: P7, name: "Trajectoires intergénérationnelles", level: population, role: exploratory, metric: education_by_income_gradient }
```

Test `tests/unit/test_patterns_frozen.py` : recalcule le hash et échoue s'il diffère de `assignment_hash`.

## 14. Extensions déclarées par les specs de version (consolidées ici)

Ces clés sont **ajoutées** par les specs de version ; elles ne modifient aucune clé existante et leur valeur neutre reproduit le comportement de la version précédente (tests de non-régression, 90 §2.3). La définition détaillée est dans la spec citée.

| Fichier | Clés ajoutées | Spec |
|---|---|---|
| `simulation.yaml` | `cognition.memory.noise_s` (0.0) ; `nta.ntta.{enabled (false), domestic_hours, shadow_wage_per_hour}` ; `output.collect.beliefs` (none \| sample) | 20 §11, §13 |
| `economic_params.yaml` | `actions.{seek_job_multiplier, max_labor_supply, fatigue_per_extra, fatigue_recovery, enter_work_find_multiplier}` | 20 §13 |
| `household_rules.yaml` | `leave_rule.housing_cost_single` | 20 §13 |
| `plans.yaml` | `max_subgoal_depth`, `desires.long_term.*`, `amounts` (liste fermée des montants symboliques) ; `beliefs.{income_cv_stable: 0.10, min_episodes_stable: 3, confidence_saturation_n: 6, job_loss_memory_months: 12, debt_manageable_dti: 1.0, debt_critical_arrears: 2, school_risk_window_months: 3, adult_age: 18, job_risk_conf_base: 0.5, job_risk_shock_saturation: 3}` (seuils des croyances, 20 §4) | 20 §4, §7, §13 |
| `affect.yaml` | contenu complet | 30 §2.6 |
| `risk.yaml` | contenu complet (dont `cpt.enabled`) | 30 §7.3 |
| `population.yaml` | contenu complet (dont `synthetic.wage_sigma_scale`, `parallel_households`) | 30 §3.4, §11 |
| `experiments/E9.yaml` | `analysis.equivalence.{method, alpha, margins}` (marges TOST de E9, nom unique) | 30 §9, 50 E9 |
| `config/calibration.yaml` | paramètres de la campagne de calibration (grille/LHS, réplications, tolérances) | 40 §6 |
| `scenarios/graded_income_shock.yaml` | scénario paramétré de E4 (`params: {start, amplitude, duration}`) | 50 E4 |
| `scenarios/budget_pressure.yaml` | scénario de E6/E8 ; la pression budgétaire est le facteur `economic_params.wage_scale` (aucune expression arithmétique dans un scénario) | 50 E6 |
| `experiments/E*.yaml` | `requires_version` (comparé au niveau **maximal** de `model.version` présent dans le plan, facteurs inclus), `analysis`, `apply_calibration`, `kind` (factorial \| sensitivity), `registry`, `morris`, `sobol` ; facteurs spéciaux `scenario.id`, `scenario.params.<nom>` | 50 §1, E-SA |

**Scénarios paramétrés :** un scénario peut déclarer un bloc `params:` ; ses événements y font référence par `${params.<nom>}` (substitution textuelle avant validation, aucune évaluation d'expression).

**Ordre d'application des surcharges** (normatif) : configuration de base → scénario → `fixed` de l'expérience → paramètres calibrés (si `apply_calibration`) → facteurs de l'expérience. La configuration résolue est revalidée puis hachée (`ConfigHash`).
