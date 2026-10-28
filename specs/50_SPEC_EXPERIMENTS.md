# 50 — Expériences : runner générique et fiches E1–E9, E-SA, scénarios contrefactuels

> **Statut :** normatif pour `analysis/experiments.py`, `analysis/figures.py` et `config/experiments/*.yaml`.
> Sources : feuille de route §11–§14, §18, §22 ; `03_CONFIG_SCHEMAS.md` §10–§12 ; `04_DATA_MODEL.md` ; `40_SPEC_VALIDATION_CALIBRATION.md`. Les sous-modèles invoqués sont spécifiés dans `10_SPEC_V1_ECONOMIC.md`, `20_SPEC_V2_COGNITIVE.md`, `30_SPEC_V3_AFFECTIVE_POPULATION.md`.
>
> **Règle (R12, 【DOC】) :** aucun résultat n'est écrit avant exécution. Les « résultats attendus » ci-dessous sont des critères de lecture, pas des prédictions — et pour **E4, aucun résultat n'est annoncé**.

---

## 1. `ExperimentRunner` (`analysis/experiments.py`)

### 1.1 Interface

```python
@dataclass(frozen=True)
class ExperimentSpec:                 # = contenu validé de config/experiments/<id>.yaml
    id: str
    title: str
    hypothesis: str
    requires_version: Literal["v1", "v2", "v3"]
    base_scenario: str
    factors: dict[str, list[Any]]     # chemin pointé → niveaux ; plan factoriel complet
    fixed: dict[str, Any]             # surcharges communes à toutes les cellules
    replications: ReplicationSpec     # n, seed_start
    metrics: list[str]                # noms du catalogue (04 §3 + §2 ci-dessous)
    analysis: AnalysisSpec            # référence, comparaisons, tests (§3)
    outputs: list[str]                # tables et figures à produire
    apply_calibration: str | None = None   # calibration_id dont on applique calibrated_overrides.yaml

class ExperimentRunner:
    def __init__(self, spec: ExperimentSpec, base_config: ResolvedConfig, out_dir: Path): ...
    def design(self) -> list[RunTask]                  # cellules × réplications
    def run(self, n_jobs: int = -1, resume: bool = True) -> ExperimentResult
    def summarize(self) -> pa.Table                    # summary.parquet
    def analyze(self) -> AnalysisReport                # §3 ; écrit analysis.md + tables
```

### 1.2 Plan et seeds communs

- Cellules = produit cartésien des niveaux de `factors` (ordre déterministe : clés triées, niveaux dans l'ordre du YAML). `cell_id = "c{index:03d}"`.
- Réplications : seeds `seed_start … seed_start + n − 1`, **identiques dans toutes les cellules** (nombres aléatoires communs) → comparaisons appariées. Les sous-flux nommés (`01_ARCHITECTURE.md` §7) garantissent qu'un facteur n'affecte pas les tirages des autres usages.
- `RunTask = (cell_id, factor_values, seed, resolved_config, config_hash)` ; `run_id` = ULID.
- Surcharges appliquées dans l'ordre : config de base → `scenario.overrides` → `fixed` → `calibrated_overrides` (si `apply_calibration`) → facteurs de la cellule. Revalidation Pydantic après chaque couche.
- Chemins de facteurs spéciaux : `scenario.id` (change le scénario de base) ; `scenario.params.<nom>` (paramètre déclaré dans le bloc `params:` d'un scénario, référencé par `${params.<nom>}` dans ses événements).

### 1.3 Exécution, parallélisme, reprise

- `joblib.Parallel(n_jobs, backend="loky")`, **un processus par run** ; chaque run écrit son dossier `runs/run_id=<…>/` de façon atomique (écriture dans `…/.tmp` puis renommage).
- `design.json` : spec résolue, liste des tâches avec `run_id`, `cell_id`, `seed`, `config_hash`, `status ∈ {pending, completed, failed}` ; mis à jour après chaque run (verrou fichier).
- **Reprise** (`resume=True`) : une tâche est sautée si un run `completed` existe avec le même `config_hash` et la même seed. Changer le code du moteur ne change pas le hash de config → `--force` relance tout ; `engine_version` est comparé et un avertissement est émis si différent.
- **Échec d'un run** (`InvariantViolation`, exception) : `status = failed`, `run.json.failure` renseigné, l'expérience **continue** ; l'analyse exclut les runs échoués et rapporte leur nombre par cellule. Un `InvariantViolation` dans une expérience **post-porte V1** est un bug bloquant : `analyze()` refuse de produire les figures tant qu'il en existe (`--allow-failed` pour diagnostic uniquement).
- Garde-fou : `requires_version` est comparé au **niveau maximal** de `model.version` présent dans le plan (valeur `fixed` et niveaux des facteurs inclus) : si ce maximum est inférieur à `requires_version` → erreur. Une cellule d'un niveau inférieur (ex. `v1` dans E2 ou E9) est donc autorisée. `apply_calibration` dont une surcharge porte sur un chemin de `factors` → `TreatmentCalibrationError` (`40` §8).

### 1.4 Sorties

```
experiments/results/experiments/<id>/
├── design.json
├── summary.parquet      # format long : experiment_id, cell_id, run_id, seed, <facteurs aplatis>, scope, household_id, metric, value
├── cells.parquet        # agrégat par cellule × métrique : n, mean, sd, q05, q50, q95
├── analysis.md          # rapport généré : hypothèse, tests, tailles d'effet, IC, runs exclus
├── tables/*.md
└── figures/*.svg (+ .png 300 dpi)
```

### 1.5 CLI

```
family-abm experiment <ID> [--n-jobs N] [--replications N] [--no-resume] [--force] [--dry-run]
family-abm experiment <ID> --analyze-only
family-abm figures <ID>|all            # régénère toutes les figures depuis les Parquet (MUST HAVE, §17 UX)
family-abm sa morris|sobol [...]       # voir 40 §5
```

`--dry-run` affiche le plan (cellules, nombre de runs, estimation de durée à partir du budget de performance).

## 2. Métriques dérivées utilisées par les expériences

Les noms de 04 §3 sont utilisés tels quels. Les métriques suivantes sont **à ajouter au catalogue** `analysis/indicators.py` (et à 04 §3) :

| `metric` | Formule | Unité | Expériences |
|---|---|---|---|
| `savings_rate_mean` | moyenne sur les pas 12…H de `savings_rate_12m` | % | E2, E-SA |
| `education_years_mean` | moyenne de `education_years_{person}` sur les personnes d'âge scolaire à un moment de l'horizon | années | E-SA, E3 |
| `education_years_children` | idem, restreint aux membres de moins de 18 ans à t₀ | années | E3, E6 |
| `consumption_share_{role}` | `Σ_t (cf + cg)_role / Σ_t (cf + cg)_foyer` | part | E6 |
| `lcd_sign_correct_share` | part des (personne, pas) où `sign(lcd)` est celui attendu pour son âge (positif < 18 ans et inactifs, négatif pour actifs employés) | part | E1 |
| `max_abs_residual` | `max |residual|` de `nta_person_steps` | FCFA | E1 |
| `horizon_eff_mean_post` | moyenne de `horizon_eff` des parents sur les 12 mois suivant le choc | mois | E4 |
| `lock_in_flag` | par run (0/1) : `recovery_time` censuré à l'horizon **ou** `debt_to_income` strictement croissant sur les 24 derniers mois (définition de 30 §12, E4) | bool | E4 |
| `lock_in_rate` | par cellule : part des paires (seed) avec `lock_in_flag = 1` sous B3 et `0` sans B3 (définition appariée de 30 §12) ; l'inverse est aussi rapporté | part | E4 |
| `credit_acceptance_rate` | décisions `TAKE_LOAN` acceptées / offertes (table `decisions`, `rule = "cpt"`) | part | E5 |
| `dissaving_delay` | mois entre le choc et la première écriture `SAVING_WITHDRAWAL` ou `BORROWING` | mois | E5 |
| `efficiency_gap` | `(W* − W_sim)/W*`, moyenne sur les pas (repère `analysis/efficiency.py`) | part | E6, E8 |
| `no_applicable_plan_rate` | événements `no_applicable_plan` / adoptions d'intention tentées (définition de 20 §7.4) | part | E2 (contrôle) |
| `run_time_s` | `run.json.duration_s` | s | E9 |

## 3. Analyse statistique — règles communes

- **Plan apparié** (seeds communes) : pour chaque comparaison cellule vs référence, on calcule les différences par seed.
- **Estimation d'abord** : différence moyenne + **IC 95 % bootstrap** (10 000 rééchantillonnages des seeds, percentile BCa) ; taille d'effet **Cohen dz** (différences appariées) et **delta de Cliff** si non normal.
- **Tests** : Wilcoxon signé (2 niveaux) ; Friedman + post-hoc Wilcoxon avec correction de **Holm** (≥ 3 niveaux) ; tendance monotone (facteur ordonné) : corrélation de Spearman sur les cellules + test de Page.
- **Avertissement normatif** : avec des réplications de simulation, la p-valeur peut être rendue arbitrairement petite en augmentant n ; le mémoire **rapporte et interprète les tailles d'effet et IC**, les p-valeurs sont secondaires. Une différence est dite « pertinente » si |dz| ≥ 0,2 **et** l'IC exclut 0.
- **Nombre de réplications** : 100 par cellule pour un foyer unique (CV de l'estimateur < 5 % visé) ; 20 pour les populations ≥ 1 000 foyers (la variabilité inter-foyers moyenne déjà). `analyze()` rapporte la demi-largeur de l'IC ; si > 10 % de la moyenne, il recommande d'augmenter n.
- **Incertitude toujours affichée** dans les figures : bande 5–95 % (lignes) ou barres d'erreur IC 95 % (barres).

## 4. Principes des figures (rappel de `70_SPEC_UX_UI.md` / feuille de route §17)

Lignes pour les séries temporelles ; barres pour les comparaisons ; aires empilées pour les décompositions ; **pas de camembert** ; **échelles identiques** entre panneaux comparés (petits multiples) ; couleur constante par membre du foyer ; **rouge réservé au déficit et aux alertes** ; thème clair ; SVG + PNG 300 dpi ; légende et unité systématiques ; chaque figure porte en pied « run(s) : …, seeds : …, config_hash : … » (traçabilité) et la mention « illustratif » si `illustrative = true`.

---

## 5. Fiches d'expérience

### E1 — Baseline économique (référence de tout le mémoire)

| | |
|---|---|
| **Question** | Les flux économiques d'un foyer simulé sont-ils comptablement cohérents, et le LCD a-t-il le bon signe par membre ? |
| **Hypothèse** 【HYP】 | Un foyer à six membres, avec règles simples et allocation à poids fixes, produit un LCD de signe correct par membre et des identités NTA qui bouclent. |
| **Version** | V1 |
| **Facteurs** | aucun |
| **Contrôlés** | revenus parentaux, prix, seuils, poids (config de base, scénario `baseline`) |
| **Réplications** | 100 seeds (critère de sortie V1) |
| **Métriques** | `lcd_household`, `lcd_sign_correct_share`, `max_abs_residual`, `debt_to_income`, `savings_rate_12m`, `rav_per_eq`, `run_time_s` |
| **Analyse** | descriptive ; `max_abs_residual ≤ 0,01` sur 100 % des runs (binaire) ; profil de LCD par membre (moyenne, bande 5–95 %) |
| **Figures** | `fig_E1_lcd_by_member.svg` (lignes, un trait par membre, couleur du membre, LCD mensuel lissé 12 mois, zéro marqué ; zone > 0 = déficit) ; `fig_E1_household_balance.svg` (aires empilées : Yl, Ya, transferts publics vs Cf ; dette en ligne sur axe séparé aligné) ; `fig_E1_transfers_matrix.svg` (barres : transferts nets intra-foyer par membre et par année) |
| **Lecture attendue** | LCD > 0 pour bébé, enfant, adolescent ; < 0 pour les parents employés ; bouclage exact — **critères de porte**, pas des résultats scientifiques |
| **Limites** | aucune prétention comportementale ; valeurs placeholders → « illustratif » |
| **Chapitre** | 4 (§4.1–4.4), 5 (§5.1–5.3), 6 (E1) |

```yaml
# config/experiments/E1.yaml
id: E1
title: "Baseline économique"
hypothesis: "Le LCD a le signe attendu par membre et les identités NTA bouclent à ε près."
requires_version: v1
base_scenario: baseline
factors: {}
fixed:
  model.version: v1
  population.n_households: 1
  checks.invariants: true
  checks.invariant_run_sample_rate: 1.0
replications: { n: 100, seed_start: 1000 }
metrics: [lcd_household, lcd_sign_correct_share, max_abs_residual, debt_to_income, savings_rate_12m, rav_per_eq, run_time_s]
analysis: { type: descriptive, gates: { max_abs_residual: { op: "<=", value: 0.01, share: 1.0 } } }
outputs: [tab_E1_summary, fig_E1_lcd_by_member, fig_E1_household_balance, fig_E1_transfers_matrix]
```

### E2 — Réactif vs délibératif

| | |
|---|---|
| **Question** | La persistance des intentions change-t-elle les trajectoires économiques ? |
| **Hypothèse** 【HYP】 | À revenus identiques, la V2 (BDI dégradé, mémoire, aspirations adaptatives) réduit la volatilité de la consommation et augmente le taux d'épargne. |
| **Version** | V2 |
| **Facteurs** | `model.version ∈ {v1, v2}` |
| **Contrôlés** | tous les paramètres économiques ; seeds communes ; scénarios `baseline` et `job_loss` (second facteur pour observer la réaction au choc) |
| **Réplications** | 100 |
| **Métriques** | `consumption_volatility`, `savings_rate_mean`, `debt_to_income_terminal`, `recovery_time` (job_loss), `no_applicable_plan_rate` (contrôle, V2) |
| **Analyse** | Wilcoxon apparié v2 − v1 par scénario ; dz, IC bootstrap ; interaction version × scénario rapportée par différences de différences |
| **Figures** | `fig_E2_volatility.svg` (barres + IC, v1/v2 côte à côte, par scénario) ; `fig_E2_savings.svg` (idem) ; `fig_E2_consumption_paths.svg` (petits multiples v1 | v2, même échelle, consommation mensuelle moyenne + bande) |
| **Lecture** | différence mesurable et explicable **ou absence de différence, également rapportée** |
| **Limites** | l'écart dépend de la bibliothèque de plans (choix de conception) ; `no_applicable_plan_rate > 5 %` invalide l'interprétation (Fiche 2, seuil de 20 §7.4) |
| **Chapitre** | 3, 6 |

```yaml
# config/experiments/E2.yaml
id: E2
title: "Réactif vs délibératif"
hypothesis: "La persistance des intentions réduit la volatilité de la consommation et augmente le taux d'épargne, à revenus identiques."
requires_version: v2
base_scenario: baseline
factors:
  model.version: [v1, v2]
  scenario.id: [baseline, job_loss]
fixed:
  population.n_households: 1
  cognition.discounting.enabled: false
replications: { n: 100, seed_start: 1000 }
metrics: [consumption_volatility, savings_rate_mean, debt_to_income_terminal, recovery_time, no_applicable_plan_rate]
analysis:
  reference: { model.version: v1 }
  paired: true
  tests: [wilcoxon]
  effect_sizes: [cohen_dz, cliff_delta]
  by: [scenario.id]
outputs: [tab_E2_effects, fig_E2_volatility, fig_E2_savings, fig_E2_consumption_paths]
```

### E3 — Présent-biais (si β-δ activé)

| | |
|---|---|
| **Question** | Le présent-biais explique-t-il la trajectoire de dette ? |
| **Hypothèse** 【HYP】 | β < 1 augmente le ratio dette/revenu et réduit le niveau d'éducation atteint par les enfants. |
| **Version** | V2 + `cognition.discounting.enabled = true` |
| **Facteurs** | `profiles.{adolescent,young_adult,mother,father}.discounting.beta ∈ {1.0, 0.9, 0.7, 0.5}` (valeur absolue sur la sélection explicite des profils à mode naïf/sophistiqué — sémantique 03 §12 ; les modes sont conservés) |
| **Contrôlés** | δ, revenus, prix ; seeds |
| **Réplications** | 100 |
| **Métriques** | `debt_to_income_terminal`, `p_insolvency`, `education_years_children`, `savings_rate_mean` |
| **Analyse** | Friedman + Holm vs β = 1,0 ; tendance : Spearman + test de Page sur β ordonné |
| **Figures** | `fig_E3_dti_by_beta.svg` (ligne β → métrique, points = moyenne, barres d'erreur IC) ; `fig_E3_education_by_beta.svg` |
| **Limites** | β est une variable de traitement : **jamais calibrée** ; la forme naïf/sophistiqué est une hypothèse |
| **Chapitre** | 3, 6 |

```yaml
# config/experiments/E3.yaml
id: E3
title: "Présent-biais (β-δ)"
hypothesis: "β < 1 augmente le ratio dette/revenu et réduit le niveau d'éducation atteint par les enfants."
requires_version: v2
base_scenario: baseline
factors:
  profiles.{adolescent,young_adult,mother,father}.discounting.beta: [1.0, 0.9, 0.7, 0.5]
fixed:
  model.version: v2
  cognition.discounting.enabled: true
  population.n_households: 1
replications: { n: 100, seed_start: 1000 }
metrics: [debt_to_income_terminal, p_insolvency, education_years_children, savings_rate_mean]
analysis:
  reference: { profiles.{adolescent,young_adult,mother,father}.discounting.beta: 1.0 }
  paired: true
  tests: [friedman, wilcoxon_holm, page_trend]
  effect_sizes: [cohen_dz]
outputs: [tab_E3_effects, fig_E3_dti_by_beta, fig_E3_education_by_beta]
```

### E4 — La boucle affective B3 (expérience centrale de la V3)

| | |
|---|---|
| **Question** | Comment articuler « dur » et « mou » sans tout convertir en utilité ? La boucle contrainte → stress → horizon réduit → décisions myopes → contrainte aggravée peut-elle produire un enfermement endogène ? |
| **Hypothèse** 【HYP】 | Il existe des amplitudes de choc absorbées par un foyer sans boucle B3 mais dont un foyer avec B3 ne se remet pas avant l'horizon. |
| **Version** | V3 |
| **Facteurs** | `loops.b3.enabled ∈ {false, true}` × `scenario.params.amplitude ∈ {0.25, 0.5, 0.75}` (part du revenu mensuel du foyer perdue pendant 12 mois, scénario `graded_income_shock` au mois 36 — valeurs de 30 §12, qui fait foi) |
| **Contrôlés** | tous les paramètres économiques ; seeds ; `affect.enabled = true` dans les deux cas (l'appraisal tourne, seule la **modulation** est coupée quand `b3 = false` → l'affect est observé mais n'agit pas) |
| **Réplications** | 100 |
| **Métriques** | `recovery_time`, `lock_in_flag`, `lock_in_rate`, `debt_to_income_terminal`, `horizon_eff_mean_post`, `stress_mean` |
| **Analyse** | par amplitude : différence appariée b3 on − off (dz, IC) ; `lock_in_rate` (paires enfermées avec B3 et non sans) avec IC de Wilson, et taux inverse ; recherche d'une amplitude seuil (plus petite amplitude où l'IC de `lock_in_rate` exclut 0) ; analyse de robustesse : même expérience avec `affect.modulation.form = sigmoid` |
| **Figures** | `fig_E4_lockin_by_amplitude.svg` (lignes : amplitude → part de `lock_in_flag`, deux traits on/off, bande IC ; `lock_in_rate` en annotation) ; `fig_E4_recovery_paths.svg` (petits multiples par amplitude, mêmes échelles, consommation relative au niveau pré-choc, on/off) ; `fig_E4_loop_trace.svg` (lignes alignées verticalement, axe temps partagé : rav, stress parental, horizon effectif, dette — un foyer représentatif, seed déclarée) |
| **Résultat attendu** | **AUCUN n'est annoncé.** Si l'enfermement n'apparaît pas, c'est un résultat ; on en cherche la raison dans les paramètres de modulation (Sobol, 40 §5.3). |
| **Limites** | l'existence de l'enfermement dépend de la forme fonctionnelle de la modulation (hypothèse) — Chapitre 9 ; aucune prétention de psychologie réelle |
| **Chapitre** | 3, 6, 8 |

```yaml
# config/experiments/E4.yaml
id: E4
title: "Boucle affective B3"
hypothesis: "La boucle contrainte → stress → horizon réduit peut produire un enfermement endogène après un choc absorbable sans elle."
requires_version: v3
base_scenario: graded_income_shock
factors:
  loops.b3.enabled: [false, true]
  scenario.params.amplitude: [0.25, 0.5, 0.75]
fixed:
  model.version: v3
  affect.enabled: true
  population.n_households: 1
  affect.modulation.form: linear
replications: { n: 100, seed_start: 1000 }
metrics: [recovery_time, lock_in_flag, lock_in_rate, debt_to_income_terminal, horizon_eff_mean_post, stress_mean]
analysis:
  reference: { loops.b3.enabled: false }
  paired: true
  tests: [wilcoxon]
  proportions: { metric: lock_in_rate, paired_on: loops.b3.enabled, ci: wilson }
  threshold_search: { factor: scenario.params.amplitude, metric: lock_in_rate }
  robustness: { override: { affect.modulation.form: sigmoid } }
  expected_result: none        # règle : aucune prédiction
outputs: [tab_E4_effects, fig_E4_lockin_by_amplitude, fig_E4_recovery_paths, fig_E4_loop_trace]
```

```yaml
# config/scenarios/graded_income_shock.yaml (scénario dédié à E4)
id: graded_income_shock
label: "Choc de revenu gradué"
params: { amplitude: 0.5, start: 36, duration: 12 }
overrides: {}
events:
  - { step: "${params.start}", type: income_shock,
      target: { household: all }, params: { amplitude: "${params.amplitude}", duration: "${params.duration}", basis: household_income } }
```

### E5 — Décision sous risque (CPT)

| | |
|---|---|
| **Question** | L'aversion aux pertes modifie-t-elle les décisions financières ? |
| **Hypothèse** 【HYP】 | L'aversion aux pertes modifie le taux d'acceptation du crédit et retarde la désépargne. |
| **Version** | V3 + `risk.cpt.enabled = true` |
| **Facteurs** | `profiles.*.risk.lambda ∈ {1.0, 2.25, 3.0}` |
| **Contrôlés** | scénario `economic_shock` (crée le besoin de crédit) ; seeds |
| **Réplications** | 100 |
| **Métriques** | `credit_acceptance_rate`, `dissaving_delay`, `debt_to_income_terminal`, `education_years_children` (via KEEP_IN_SCHOOL) |
| **Analyse** | Friedman + Holm vs λ = 1 ; tendance de Page |
| **Figures** | `fig_E5_credit_by_lambda.svg` (barres + IC) ; `fig_E5_dissaving_delay.svg` (barres + IC) |
| **Limites** | λ fixé aux valeurs publiées (T&K 1992), jamais calibré ; marginal pour la question centrale — **premier abandon** si un jalon glisse |
| **Chapitre** | 3, 6 |

```yaml
# config/experiments/E5.yaml
id: E5
title: "Aversion aux pertes"
hypothesis: "L'aversion aux pertes modifie le taux d'acceptation du crédit et retarde la désépargne."
requires_version: v3
base_scenario: economic_shock
factors:
  profiles.*.risk.lambda: [1.0, 2.25, 3.0]
fixed:
  model.version: v3
  risk.cpt.enabled: true
  population.n_households: 1
replications: { n: 100, seed_start: 1000 }
metrics: [credit_acceptance_rate, dissaving_delay, debt_to_income_terminal, education_years_children]
analysis:
  reference: { profiles.*.risk.lambda: 1.0 }
  paired: true
  tests: [friedman, wilcoxon_holm, page_trend]
outputs: [tab_E5_effects, fig_E5_credit_by_lambda, fig_E5_dissaving_delay]
```

### E6 — Foyer unitaire vs non unitaire (design repris de Beal Cohen et al. 2021)

| | |
|---|---|
| **Question** | Un foyer non unitaire produit-il des allocations différentes ? |
| **Hypothèse** 【HYP】 | Sous contrainte budgétaire forte, l'allocation d'un foyer non unitaire diffère qualitativement de celle d'un foyer unitaire. |
| **Version** | V2 (V3 pour `efficiency_gap`) |
| **Facteurs** | `household_rules.allocation.mode ∈ {unitary, fixed_weights, variable_weights}` × `economic_params.wage_scale ∈ {1.0, 0.6}` (scénario `budget_pressure`) |
| **Contrôlés** | seeds, besoins, prix |
| **Réplications** | 100 |
| **Métriques** | `consumption_share_{role}` (6 rôles), `education_years_children`, `essential_unmet` (moyenne), `efficiency_gap` (si V3) |
| **Analyse** | par niveau de contrainte : Friedman + Holm entre modes sur chaque part ; distance de Hellinger entre vecteurs de parts (mode vs unitaire) avec IC bootstrap |
| **Figures** | `fig_E6_shares.svg` (aires empilées à 100 % par mode — décomposition, une colonne par mode, petits multiples par contrainte, couleurs des membres) ; `fig_E6_education.svg` (barres + IC) |
| **Limites** | `bargaining_weights` et `gamma` sont calibrés (non observables) : E6 utilise les valeurs de référence avant calibration et est rejouée après calibration (`apply_calibration`), le mode restant le facteur |
| **Chapitre** | 4, 6 |

```yaml
# config/experiments/E6.yaml
id: E6
title: "Foyer unitaire vs non unitaire"
hypothesis: "Sous contrainte budgétaire forte, l'allocation d'un foyer non unitaire diffère qualitativement de celle d'un foyer unitaire."
requires_version: v2
base_scenario: budget_pressure
factors:
  household_rules.allocation.mode: [unitary, fixed_weights, variable_weights]
  economic_params.wage_scale: [1.0, 0.6]
fixed:
  population.n_households: 1
replications: { n: 100, seed_start: 1000 }
metrics: [consumption_share_father, consumption_share_mother, consumption_share_young_adult,
          consumption_share_adolescent, consumption_share_child, consumption_share_baby,
          education_years_children, essential_unmet, efficiency_gap]
analysis:
  reference: { household_rules.allocation.mode: unitary }
  paired: true
  tests: [friedman, wilcoxon_holm]
  distances: [hellinger_shares]
  by: [economic_params.wage_scale]
outputs: [tab_E6_effects, fig_E6_shares, fig_E6_education]
```

```yaml
# config/scenarios/budget_pressure.yaml
id: budget_pressure
label: "Contrainte budgétaire"
overrides: {}                  # la pression budgétaire est le facteur economic_params.wage_scale
                               # (multiplicateur de tous les salaires, 03 §6) — aucune expression évaluée
events: []
```

### E7 — Population de foyers (validation principale)

| | |
|---|---|
| **Question** | Quels phénomènes émergent au passage à une population ? Le profil de LCD agrégé est-il comparable aux profils NTA publiés ? |
| **Hypothèse** 【HYP】 | L'agrégation par âge de N foyers hétérogènes produit un profil de LCD de forme comparable aux profils NTA publiés. |
| **Version** | V3 |
| **Facteurs** | `population.n_households ∈ {100, 1000}` × `population.synthetic.wage_sigma_scale ∈ {0.5, 1.0}` (hétérogénéité des dotations) |
| **Contrôlés** | seeds, paramètres (calibrés si disponible : `apply_calibration`) |
| **Réplications** | 20 |
| **Métriques** | `nta_age_profile`, `lcd_age_profile_nrmse` (P1), `gini_income`, `poverty_rate`, `behav_vs_imputed_gap`, `public_load` |
| **Analyse** | P1 (forme et NRMSE, 40 §3) ; Gini et pauvreté avec IC sur réplications ; écart comportemental/imputé par âge |
| **Figures** | `fig_E7_lcd_age_profile.svg` (lignes : C, Yl, LCD par âge ; cible en trait discontinu ; bande 5–95 %) ; `fig_E7_lee_arrows.svg` (« flèches de Lee » : transferts nets entre classes d'âge) ; `fig_E7_behav_vs_imputed.svg` (lignes par âge, deux traits) ; `fig_E7_dti_hist.svg` (histogramme dette/revenu, médiane marquée) |
| **Lecture** | V-6 : forme en U ; écarts quantifiés et discutés |
| **Limites** | cohorte fixe (Q5) : âges élevés sous-représentés ; retraite hors horizon |
| **Chapitre** | 6, 7, 8 |

```yaml
# config/experiments/E7.yaml
id: E7
title: "Population de foyers"
hypothesis: "L'agrégation par âge de N foyers hétérogènes produit un profil de LCD de forme comparable aux profils NTA publiés."
requires_version: v3
base_scenario: baseline
factors:
  population.n_households: [100, 1000]
  population.synthetic.wage_sigma_scale: [0.5, 1.0]
fixed:
  model.version: v3
  output.collect.ledger: false
  output.collect.decisions: sample
replications: { n: 20, seed_start: 1000 }
apply_calibration: null        # renseigné après la Phase 9
metrics: [lcd_age_profile_nrmse, gini_income, poverty_rate, behav_vs_imputed_gap, public_load]
analysis:
  patterns: [P1]
  descriptive: true
outputs: [tab_E7_summary, fig_E7_lcd_age_profile, fig_E7_lee_arrows, fig_E7_behav_vs_imputed, fig_E7_dti_hist]
```

### E8 — Écart à l'efficacité collective

| | |
|---|---|
| **Question** | De combien la rationalité limitée éloigne-t-elle de l'efficacité collective ? |
| **Hypothèse** 【HYP】 | L'allocation d'un foyer à rationalité limitée s'écarte de l'allocation Pareto-efficace, et l'écart croît avec le stress et la contrainte. |
| **Version** | V3 |
| **Facteurs** | `affect.enabled ∈ {false, true}` × `economic_params.wage_scale ∈ {1.0, 0.8, 0.6}` (scénario `budget_pressure`) |
| **Réplications** | 50, `n_households = 100` |
| **Métriques** | `efficiency_gap`, `stress_mean`, `essential_unmet` |
| **Analyse** | dz et IC par cellule ; corrélation de Spearman (foyer-mois) entre `efficiency_gap` et stress parental, IC bootstrap par réplication |
| **Figures** | `fig_E8_gap_by_constraint.svg` (lignes : contrainte → écart, deux traits affect on/off, bandes IC) ; `fig_E8_gap_vs_stress.svg` (nuage hexbin + droite de tendance) |
| **Limites** | le repère (log-somme pondérée) est un **repère théorique** (D7), pas un comportement ; sa forme influence l'écart. 2ᵉ abandon si jalon glisse |
| **Chapitre** | 4, 8 |

```yaml
# config/experiments/E8.yaml
id: E8
title: "Écart à l'efficacité collective"
hypothesis: "L'écart à l'allocation Pareto-efficace croît avec le stress et la contrainte."
requires_version: v3
base_scenario: budget_pressure
factors:
  affect.enabled: [false, true]
  economic_params.wage_scale: [1.0, 0.8, 0.6]
fixed:
  model.version: v3
  population.n_households: 100
  output.collect.ledger: false
replications: { n: 50, seed_start: 1000 }
metrics: [efficiency_gap, stress_mean, essential_unmet]
analysis:
  reference: { affect.enabled: false }
  paired: true
  correlations: [{ x: parent_stress_mean, y: efficiency_gap, method: spearman, level: household_step }]
outputs: [tab_E8_effects, fig_E8_gap_by_constraint, fig_E8_gap_vs_stress]
```

### E9 — Dégradation cognitive contrôlée (passage à l'échelle)

| | |
|---|---|
| **Question** | Jusqu'où peut-on simplifier la cognition sans changer les agrégats ? |
| **Hypothèse** 【HYP】 | Il existe un niveau de simplification en deçà duquel les indicateurs agrégés (Gini, profil LCD, pauvreté) cessent de différer significativement. |
| **Version** | V3 |
| **Facteurs** | `model.version ∈ {v1, v2, v3}` × `population.n_households ∈ {100, 1000}` |
| **Réplications** | 20 |
| **Métriques** | `gini_income`, `poverty_rate`, `lcd_age_profile_nrmse` (entre versions : profil de v_k vs profil de v3 comme cible), `run_time_s` |
| **Analyse** | **équivalence par TOST** de chaque version vs v3, marges déclarées *avant* exécution : Gini ±0,01 ; pauvreté ±2 points ; NRMSE inter-versions ≤ 0,05 ; coût : `run_time_s` par foyer (régression log-log sur N) |
| **Figures** | `fig_E9_equivalence.svg` (barres : différence vs v3 + IC 90 % et marges d'équivalence en bandes grises) ; `fig_E9_cost_vs_n.svg` (lignes log-log, une par version) |
| **Lecture** | réponse **scientifique** à la question de l'échelle (feuille de route §14), pas un benchmark |
| **Limites** | dépend des indicateurs choisis ; 3ᵉ abandon si jalon glisse (Chap. 7 devient conception + perspective) |
| **Chapitre** | 7 |

```yaml
# config/experiments/E9.yaml
id: E9
title: "Dégradation cognitive contrôlée"
hypothesis: "En deçà d'un niveau de simplification, les agrégats cessent de différer significativement."
requires_version: v3
base_scenario: baseline
factors:
  model.version: [v1, v2, v3]
  population.n_households: [100, 1000]
fixed:
  output.collect.ledger: false
  output.collect.decisions: none
  checks.invariant_run_sample_rate: 0.05
replications: { n: 20, seed_start: 1000 }
metrics: [gini_income, poverty_rate, lcd_age_profile_nrmse, run_time_s]
analysis:
  reference: { model.version: v3 }
  paired: true
  equivalence:
    method: tost
    alpha: 0.05
    margins: { gini_income: 0.01, poverty_rate: 0.02, lcd_age_profile_nrmse: 0.05 }
  cost_model: { x: population.n_households, y: run_time_s, scale: loglog }
outputs: [tab_E9_equivalence, fig_E9_equivalence, fig_E9_cost_vs_n]
```

### E-SA — Analyse de sensibilité globale (V2)

| | |
|---|---|
| **Question** | Quels paramètres gouvernent réellement les résultats ? |
| **Version** | V2 (Phase 6) ; reprise V3 en Phase 9 (40 §5) |
| **Méthode** | Morris (r = 20, 4 niveaux) sur les paramètres `sa: true` du registre, puis Sobol (N = 512, sans 2ᵉ ordre) sur les 8–10 survivants (μ*_norm ≥ 0,1 sur au moins une sortie) — détails 40 §5 |
| **Réplications** | 10 par point (Morris), 5 (Sobol) |
| **Sorties analysées** | `debt_to_income_terminal`, `savings_rate_mean`, `consumption_volatility`, `education_years_mean`, `lcd_household` |
| **Figures** | **figure obligatoire du Chapitre 6** : `fig_sa_sobol_<metric>.svg` (barres horizontales triées, S1 et ST, IC) ; `fig_sa_morris_<metric>.svg` |
| **Lecture** | l'auteur peut nommer les cinq paramètres qui gouvernent les résultats (critère Phase 6) |
| **Chapitre** | 6 |

```yaml
# config/experiments/E_SA.yaml
id: E_SA
title: "Analyse de sensibilité globale"
hypothesis: "Un petit nombre de paramètres gouverne les sorties principales."
requires_version: v2
base_scenario: baseline
kind: sensitivity                # traité par analysis/sensitivity.py, pas par le plan factoriel
fixed:
  model.version: v2
  population.n_households: 1
  checks.invariant_run_sample_rate: 0.05
registry: config/parameters_registry.yaml
morris: { r: 20, num_levels: 4, n_rep: 10, seed: 7 }
sobol: { n: 512, second_order: false, n_rep: 5, seed: 11, select: { score_min: 0.1, k_min: 4, k_max: 10 } }
metrics: [debt_to_income_terminal, savings_rate_mean, consumption_volatility, education_years_mean, lcd_household]
outputs: [tab_sa_morris, tab_sa_sobol, fig_sa_morris, fig_sa_sobol]
```

### CF — Scénarios contrefactuels (DOC §6, Phase 10)

| | |
|---|---|
| **Question** | Que devient le foyer (et la population) si l'on introduit une allocation familiale, si un parent perd son emploi, si les soins deviennent gratuits, en cas de choc économique ? |
| **Hypothèses** 【HYP】 | `family_allowance` ↑ `rav_per_eq` et `education_years_children` ; `job_loss` ↑ `debt_to_income`, ↓ `rav_per_eq` ; `free_care` ↓ `health_spending` privé, ↑ `healthy_years` ; `economic_shock` ↑ `poverty_rate` — signes attendus = table V-3 (40 §2.1) ; amplitudes **non prédites** |
| **Version** | la plus haute version validée (V3 cible ; V2 si repli) |
| **Facteurs** | `scenario.id ∈ {baseline, job_loss, illness, family_allowance, free_care, economic_shock}` |
| **Réplications** | 50 si foyer unique ; 20 si population 1 000 |
| **Métriques** | tableau de bord complet : `debt_to_income`, `savings_rate_12m`, `rav_per_eq`, `p_insolvency`, `education_years_children`, `cohesion_index`, `wellbeing`, `stress_mean`, `healthy_years`, `health_spending`, `crisis_frequency`, `gini_income`, `poverty_rate`, `public_load` |
| **Analyse** | différences appariées vs `baseline`, % d'écart avec IC ; coût public (`public_load`) mis en regard des effets (ratio effet / FCFA public, descriptif — pas d'optimisation de politique, hors périmètre) |
| **Figures** | `fig_CF_small_multiples.svg` (petits multiples : un panneau par scénario, mêmes échelles, `rav_per_eq` et dette dans le temps) ; `tab_CF_deltas.md` (table des écarts % vs référence, IC) ; `fig_CF_dashboard_bars.svg` (barres d'écart par indicateur, rouge seulement pour une dégradation de déficit/pauvreté) |
| **Limites** | chaque conclusion du Chapitre 8 porte sa condition de validité ; modèle illustratif si placeholders ; pas d'effets d'équilibre général (pas de marché endogène) |
| **Chapitre** | 8 |

```yaml
# config/experiments/CF_scenarios.yaml
id: CF
title: "Scénarios contrefactuels"
hypothesis: "Les politiques et chocs modifient les indicateurs du foyer dans le sens de la table V-3 ; amplitudes non prédites."
requires_version: v2
base_scenario: baseline
factors:
  scenario.id: [baseline, job_loss, illness, family_allowance, free_care, economic_shock]
fixed:
  population.n_households: 1        # 1000 si la V3 population est validée (alors replications.n = 20)
replications: { n: 50, seed_start: 2000 }
apply_calibration: null
metrics: [debt_to_income, savings_rate_12m, rav_per_eq, p_insolvency, education_years_children,
          cohesion_index, wellbeing, stress_mean, healthy_years, health_spending, crisis_frequency,
          gini_income, poverty_rate, public_load]
analysis:
  reference: { scenario.id: baseline }
  paired: true
  report: percent_change_with_ci
outputs: [tab_CF_deltas, fig_CF_small_multiples, fig_CF_dashboard_bars]
```

## 6. Ordre d'exécution et abandon

| Phase | Expériences | Porte |
|---|---|---|
| 4 | E1 | V1 |
| 6 | E2, E3, E6, E-SA | V2 |
| 7 | E4 (centrale), E5 | 7 → 8 |
| 8 | E7 | 8 → 9 |
| 10 | E8, E9, CF (+ E6, E7 rejouées avec `apply_calibration`) | 10 → 11 |

Ordre d'abandon si un jalon glisse (feuille de route §22) : E5 → E8 → E9 → calibration EHCVM → V3 entière. **Ne sautent jamais :** E1, E2, E-SA, la séparation calibration/validation.

## 7. Tests du runner

| Fichier | Vérifie |
|---|---|
| `tests/unit/test_experiment_design.py` | plan factoriel, ordre déterministe, seeds communes, surcharges appliquées dans l'ordre §1.2, `scenario.params` |
| `tests/unit/test_experiment_resume.py` | reprise : runs `completed` sautés, `failed` relancés |
| `tests/unit/test_experiment_guards.py` | `requires_version`, `TreatmentCalibrationError` via `apply_calibration` |
| `tests/unit/test_stats.py` | bootstrap apparié, dz, Cliff, Holm, TOST sur données connues |
| `tests/integration/test_experiment_smoke.py` | E2 réduit (2 seeds, 24 pas) de bout en bout → `summary.parquet` + figures |

---

## Détails tranchés dans ce document

- Ordre des surcharges (base → scénario → fixed → calibration → facteurs) ; chemins `scenario.id` et `scenario.params.*` ; scénarios paramétrés `${params.x}` (substitution textuelle seule ; la pression budgétaire passe par `economic_params.wage_scale`) ; nouveaux scénarios `graded_income_shock` (E4) et `budget_pressure` (E6, E8) — à ajouter à `03_CONFIG_SCHEMAS.md` §10.
- Clé `requires_version`, `analysis`, `apply_calibration`, `kind: sensitivity` dans le format d'expérience (extension de 03 §11).
- E4 : `b3 = false` coupe la modulation mais laisse l'appraisal tourner ; amplitude = part du revenu du foyer perdue 12 mois à partir du mois 36 ; robustesse avec `affect.modulation.form = sigmoid`.
- E3 : β absolu appliqué par sélection explicite des profils à mode naïf/sophistiqué (`profiles.{adolescent,young_adult,mother,father}.discounting.beta`, sémantique 03 §12).
- E7 : hétérogénéité via `population.synthetic.wage_sigma_scale` (multiplicateur des σ de `synthetic.wages.*`, aligné sur `30_SPEC_V3` §3.4).
- E9 : marges TOST (Gini 0,01 ; pauvreté 2 points ; NRMSE 0,05).
- Réplications : 100 (foyer unique), 50 (E8, CF), 20 (populations 1 000) ; seuil de pertinence |dz| ≥ 0,2 et IC excluant 0.
- Métriques dérivées §2 à ajouter à `04_DATA_MODEL.md` §3 et `analysis/indicators.py`.
