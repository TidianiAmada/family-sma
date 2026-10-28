# 04 — Modèle de données de sortie et catalogue d'indicateurs

> Toutes les sorties sont des tables **Parquet** (schémas Arrow fixés dans `io/parquet.py`), une table par fichier, partitionnées par run. L'API et l'UI ne lisent **que** ces tables (via DuckDB) — jamais l'état vivant du modèle. Les indicateurs sont calculés dans `analysis/indicators.py` et **nulle part ailleurs** (S7).

---

## 1. Organisation physique

```
experiments/results/
├── runs/
│   └── run_id=<ULID>/
│       ├── run.json                      ← métadonnées (§2.1) — aussi copiées dans SQLite côté API
│       ├── config.resolved.yaml          ← configuration résolue (reproductibilité)
│       ├── person_steps.parquet
│       ├── household_steps.parquet
│       ├── ledger.parquet                ← optionnel (output.collect.ledger)
│       ├── demands.parquet
│       ├── decisions.parquet             ← optionnel / échantillonné
│       ├── events.parquet
│       ├── nta_person_steps.parquet
│       ├── nta_transfer_matrix.parquet   ← agrégé par année simulée
│       ├── nta_age_profile.parquet
│       └── metrics.parquet               ← indicateurs scalaires du run
├── experiments/<experiment_id>/
│   ├── design.json                       ← plan factoriel résolu, liste des run_id
│   └── summary.parquet                   ← métriques × facteurs × réplications
├── sensitivity/<study_id>/indices.parquet
└── calibration/<calibration_id>/{candidates,pattern_results}.parquet
catalog.duckdb                            ← vues sur les globs ci-dessus (io/catalog.py)
```

Écriture : listes Python accumulées par bloc de 12 pas → `pyarrow.Table` → fichier. Jamais de `DataFrame.append` dans la boucle.

## 2. Schémas des tables

Types : `str`, `i32`, `i64`, `f64`, `bool`, `json` (= `str` contenant du JSON), `cat` (dictionnaire Arrow).

### 2.1 `run.json` / table `runs`

| Champ | Type | Description |
|---|---|---|
| `run_id` | str | ULID |
| `created_at` | str (ISO 8601) | |
| `engine_version` | str | version du paquet `family_abm` |
| `git_commit` | str | `git rev-parse HEAD` si disponible |
| `config_hash` | str | empreinte de la config résolue |
| `model_version` | cat | v1 / v2 / v3 |
| `scenario_id` | str | |
| `experiment_id` | str \| null | |
| `factor_values` | json | valeurs des facteurs de l'expérience |
| `seed` | i64 | |
| `n_households` | i32 | |
| `horizon_months` | i32 | |
| `data_source` | cat | synthetic / nta_profiles / ehcvm |
| `illustrative` | bool | vrai si au moins un `PLACEHOLDER` dans la config |
| `status` | cat | completed / failed |
| `failure` | json \| null | type, message, pas, compte (ex. `InvariantViolation`) |
| `duration_s` | f64 | |
| `invariant_checks` | i64 | nombre de vérifications passées |

### 2.2 `person_steps` — une ligne par personne et par pas

| Champ | Type | V | | Champ | Type | V |
|---|---|---|---|---|---|---|
| `run_id` | str | 1 | | `need_level_{k}` ×6 | f64 | 1 |
| `step` | i32 | 1 | | `need_sat_{k}` ×6 | f64 | 1 |
| `household_id` | str | 1 | | `aspiration_{k}` ×6 | f64 | 1 |
| `person_id` | str | 1 | | `intention_goal` | str \| null | 2 |
| `role` | cat | 1 | | `plan_id` | str \| null | 2 |
| `profile_key` | cat | 1 | | `n_beliefs_active` | i32 | 2 |
| `age_years` | f64 | 1 | | `memory_size` | i32 | 2 |
| `employment` | cat | 1 | | `stress` | f64 | 3 |
| `school_status` | cat | 1 | | `mood` | f64 | 3 |
| `labor_supply` | f64 | 1 | | `emo_joy`, `emo_sadness`, `emo_fear`, `emo_anger` | f64 | 3 |
| `yl` | f64 | 1 | | `horizon_eff` | i32 | 1* |
| `cf` | f64 | 1 | | `alternatives_eff` | i32 | 1* |
| `cg` | f64 | 1 | | `beta_eff` | f64 | 2* |
| `wallet` | f64 | 1 | | `fatigue` | f64 | 2 |
| `health` | f64 | 1 | | `in_household` | bool | 2 (D13) |
| `sick` | bool | 1 | | | | |
| `labor_capacity` | f64 | 1 | | | | |

\* égal au profil de base tant que la modulation (V3) est inactive.

### 2.3 `household_steps` — une ligne par foyer et par pas

`run_id, step, household_id, regime (cat), n_members (i32), pot, savings, debt (f64, ≥ 0), net_worth, income_labor, income_total (Yl + Ya⁺ + transferts reçus), consumption_private, consumption_public, commitments (logement + service de la dette), borrowing, repayment, interest_paid, credit_limit, arrears_months (i32), demands_n (i32), demands_partial_n, demands_refused_n, essential_unmet (f64, FCFA d'essentiel non couvert), debt_to_income, savings_rate_12m, rav_per_eq (reste-à-vivre par équivalent-adulte), eq_size (f64), parent_stress_mean (V3)`.

### 2.4 `ledger` — une ligne par écriture (§8 du modèle de domaine)

`run_id, entry_id (i64), step, household_id, src_kind (cat), src_owner, dst_kind (cat), dst_owner, amount (f64), category (cat), need (cat), beneficiary, initiator, ref`.

### 2.5 `demands`

`run_id, step, household_id, demand_id, person_id, need, tier (i32), action (cat), requested, amount_min, priority, divisible, plan_id, granted, status (cat), reason (cat)`.

### 2.6 `decisions` — traces (échantillonnées en population)

`run_id, step, person_id, rule (cat), chosen_id, chosen_description, n_considered (i32), considered (json: liste d'AlternativeEval), aspiration (json), profile_eff (json), intention_goal, plan_id, cpt (json)`.

### 2.7 `events`

`run_id, step, household_id, person_id (nullable), type (cat), origin (cat: scenario | endogenous), payload (json)`.

Types endogènes : `job_loss`, `job_found`, `health_episode`, `recovered`, `school_enrolled`, `school_dropout`, `school_completed`, `profile_transition`, `arrears_start`, `arrears_end`, `credit_limit_hit`, `intention_adopted`, `intention_failed`, `plan_switched`, `no_applicable_plan`, `regime_change`, `left_household`.

### 2.8 `nta_person_steps` — sortie de `NTACalculator`

`run_id, step, household_id, person_id, age_years, c, cf, cg, yl, lcd (= c − yl), tau_in_intra, tau_out_intra, tau_in_pub, tau_out_pub, tau_in_inter, tau_out_inter, ya, s, residual (identité, doit être |·| ≤ ε), tau_net_behav, tau_net_imputed (règle ONU), tau_gap (= behav − imputed)`.

`tau_net_behav = tau_in_intra − tau_out_intra` : transfert net **intra-ménage seulement**, même périmètre que `tau_net_imputed` (la règle ONU n'impute que les transferts privés intra-ménage) ; c'est la grandeur comparée en M15 et reproduite au centime par `test_imputation` (10 §15).

### 2.9 `nta_transfer_matrix` — agrégée par année simulée

`run_id, year (i32), household_id, src_person, dst_person, amount (f64, annuel)`. Alimente le graphe du foyer (épaisseur des arêtes) et les « flèches de Lee ».

### 2.10 `nta_age_profile` — profils par âge (années entières)

`run_id, age (i32), person_years (f64), c, cf, cg, yl, lcd, tau_net_intra, tau_net_pub, tau_net_inter, ya_minus_s, tau_net_imputed` — **moyennes annuelles par tête** ; plus les colonnes normalisées `*_norm` = valeur / moyenne de `yl` sur les âges 30–49 (convention NTA de normalisation, à vérifier contre le manuel ONU par l'auteur).

### 2.11 `metrics` — scalaires par run

`run_id, scope (cat: household | population), household_id (nullable), metric (cat), value (f64)`.

### 2.12 `pattern_results`, `sensitivity_indices`, `calibration_candidates`

- `pattern_results` : `context_id (run, expérience ou calibration), pattern_id, role, simulated (json), target (json), distance, tolerance, pass (bool)`.
- `sensitivity_indices` : `study_id, method (morris|sobol), output_metric, parameter, mu_star, mu_star_conf, sigma, s1, s1_conf, st, st_conf, rank`.
- `efficiency_gap` (V3, E8) : `run_id, step, household_id, w_star, w_sim, gap` — `gap = (W* − W_sim) / |W*|` (repère ex post, `analysis/efficiency.py`, voir 30_SPEC_V3 §6).
- `calibration_candidates` : `calibration_id, candidate_id, params (json), loss, per_pattern_loss (json), n_replications, selected (bool)`.

## 3. Catalogue d'indicateurs (`analysis/indicators.py`)

Toute formule ici est **la** définition (le champ `direction` de chaque indicateur est déclaré dans `CATALOG`, §3.5) ; l'UI affiche le libellé et l'unité, jamais un recalcul.

### 3.1 Économiques (DOC §6)

| `metric` | Libellé | Formule | Unité |
|---|---|---|---|
| `debt_to_income` | Ratio dette/revenu | `debt_t / Σ_{12 derniers mois} income_total` | ratio |
| `savings_rate_12m` | Taux d'épargne | `Σ₁₂ S_h / Σ₁₂ (income_total − taxes)` | % |
| `rav_per_eq` | Reste-à-vivre par équivalent-adulte | `(income_total − commitments) / eq_size` | FCFA/mois |
| `lcd_household` | LCD agrégé du foyer | `Σᵢ (cᵢ − ylᵢ)` | FCFA/mois |
| `p_insolvency` | Probabilité d'insolvabilité | part des (foyers × réplications) ayant `arrears_months ≥ 3` au moins une fois | % |
| `consumption_volatility` | Volatilité de la consommation | écart-type des variations mensuelles relatives de `consumption_private` | — |
| `debt_to_income_terminal` | Dette/revenu terminal | `debt_to_income` au dernier pas | ratio |
| `lock_in_flag` | Enfermement (E4, V3) | 0/1 par run : récupération censurée ou dette/revenu strictement croissant sur 24 mois (30 §12) | booléen |
| `lock_in_rate` | Taux d'enfermement endogène (E4, V3) | par cellule : part des paires (seed) enfermées avec B3 et non sans B3 (30 §12) | % |
| `recovery_time` | Temps de retour après choc | premier pas après le choc où `consumption_private ≥ 0,95 ×` moyenne des 12 mois pré-choc | mois (censuré à l'horizon) |

### 3.2 Sociaux

| `metric` | Libellé | Formule |
|---|---|---|
| `education_years_{person}` | Années d'éducation atteintes | mois `ENROLLED` / 12 |
| `cohesion_index` | Indice de cohésion familiale | `(1 − Gini des niveaux essentiels {food, health} entre membres) × part des mois en régime NORMAL` |
| `wellbeing` | Bien-être | moyenne des `need_level` sur les `attended_needs` |
| `stress_mean` | Stress moyen (V3) | moyenne de `stress` |
| `mobility_gradient` | Mobilité intergénérationnelle (P7, exploratoire) | pente de la régression `education_years_enfants ~ rang percentile du revenu du foyer à t0` |

### 3.3 Santé

| `metric` | Libellé | Formule |
|---|---|---|
| `healthy_years` | Années en bonne santé simulées | mois avec `health ≥ 0,7` / 12, par personne, sur l'horizon |
| `health_spending` | Dépenses de santé | `Σ cf[need=health] + Σ cg[need=health]` |
| `crisis_frequency` | Fréquence des crises | épisodes / personne-année |

### 3.4 Systémiques (population, V3)

| `metric` | Libellé | Formule |
|---|---|---|
| `gini_income` | Gini des revenus | Gini de `income_total / eq_size` entre foyers (moyenne annuelle) |
| `poverty_rate` | Taux de pauvreté | part des foyers avec `rav_per_eq < poverty_line` (`economic_params.poverty_line_per_eq`) |
| `public_load` | Charge sur les services publics | `Σ cg + Σ transferts publics` par foyer |
| `nta_age_profile` | Profils NTA agrégés | table §2.10 |
| `behav_vs_imputed_gap` | Écart transferts comportementaux / imputés | `Σ |tau_gap| / Σ |tau_net_imputed|` par âge et global |

### 3.5 Interface programmatique de `analysis/indicators.py` (consommée par l'API)

| Symbole | Rôle |
|---|---|
| `CATALOG: dict[str, IndicatorDef]` | une entrée par `metric` ci-dessus : `label_fr`, `unit`, `scope`, `direction` (`lower_is_better` \| `higher_is_better` \| `neutral`), `version_min`, fonction de calcul. **Seule source des libellés et du sens de variation** pour l'UI. |
| `summarize(run_dirs, scope, metrics) -> IndicatorSummary` | valeur, dispersion (§3.6), série miniature (`sparkline`) et variation (`delta`) par indicateur ; médianes de distribution incluses |
| `compare(run_groups, metrics, baseline) -> Comparison` | écarts en % au scénario de référence + domaine d'axes partagé (`shared_domain`) |
| `age_bins(profile, bins) -> Table` | regroupement des profils par classes d'âge (flèches de Lee), côté serveur |

### 3.6 Agrégation sur réplications

Tout indicateur affiché pour une **expérience** est accompagné de sa dispersion : moyenne, écart-type, quantiles 5 % et 95 %, n. (« Toujours afficher l'incertitude », UX §17.)

## 4. Extensions déclarées par les specs de version (consolidées ici)

| Élément | Ajout | Spec |
|---|---|---|
| `run.json` / `runs` | `data_fallback` (json \| null) : `{requested, used, reason}` quand la source de données demandée est indisponible et que le run se replie sur `synthetic` | 40 §données |
| `person_steps` | `intention_status` (cat), `plan_step_index` (i32), `failure_streak_{k}` (i32 ×6) | 20 §14 |
| table `household_weights` | `run_id, step, household_id, person_id, weight, ownership` | 20 §14 |
| table `beliefs_steps` (optionnelle) | `run_id, step, person_id, key, value, confidence` | 20 §14 |
| table `ntta_person_steps` (si NTTA) | voir 20 §11 | 20 §11 |
| table `efficiency_gap` | voir §2.12 | 30 §6 |

**Métriques ajoutées au catalogue** (même règle : définition unique dans `analysis/indicators.py`) :

| `metric` | Définition | Spec |
|---|---|---|
| `savings_rate_mean` | moyenne de `savings_rate_12m` sur les pas 12…H | 50 §2 |
| `education_years_mean` | moyenne de `education_years_{person}` sur les personnes d'âge scolaire pendant l'horizon | 50 §2 |
| `education_years_children` | idem, membres de moins de 18 ans à t₀ | 50 §2 |
| `consumption_share_{role}` | `Σ_t (cf + cg)_role / Σ_t (cf + cg)_foyer` | 50 §2 |
| `lcd_sign_correct_share` | part des (personne, pas) où le signe du LCD est celui attendu | 50 §2 |
| `max_abs_residual` | `max |residual|` de `nta_person_steps` | 50 §2 |
| `horizon_eff_mean_post` | horizon effectif moyen des parents sur les 12 mois suivant le choc | 50 §2 |
| `lock_in_flag` (run), `lock_in_rate` (cellule) | enfermement endogène (définition opérationnelle : 30 §12, E4) | 30, 50 |
| `credit_acceptance_rate`, `dissaving_delay` | E5 | 50 §2 |
| `efficiency_gap` (moyenne) | `(W* − W_sim)/W*` moyenné sur les pas | 30 §6, 50 §2 |
| `no_applicable_plan_rate`, `intention_persistence_mean`, `plan_success_rate`, `dropout_by_plan` | V2 | 20 §14 |
| `run_time_s` | `run.json.duration_s` | 50 §2 |
| `essential_unmet` | moyenne sur les pas de `household_steps.essential_unmet` (FCFA d'essentiel non couvert) | 50 E6, E8 |
