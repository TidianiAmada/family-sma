# 40 — Vérification, validation, sensibilité et calibration

> **Statut :** normatif pour `analysis/patterns.py`, `analysis/sensitivity.py`, `analysis/calibration.py`, `population/sources.py`, `nta/invariants.py`, `data/` et les tests associés.
> Sources : feuille de route §13 et §24, `00_DECISIONS.md` (D10, Q6, Q7), `02_DOMAIN_MODEL.md` §9, `03_CONFIG_SCHEMAS.md` §12–13, `04_DATA_MODEL.md`. Les sous-modèles sont spécifiés dans `10_SPEC_V1_ECONOMIC.md`, `20_SPEC_V2_COGNITIVE.md`, `30_SPEC_V3_AFFECTIVE_POPULATION.md` ; les plans d'expérience dans `50_SPEC_EXPERIMENTS.md`.

---

## 1. Six opérations distinctes — ne jamais les confondre

| Opération | Définition | Porte sur | Module | Moment | Exemple |
|---|---|---|---|---|---|
| **Initialisation** (génération de population synthétique) | Fixer l'état à t = 0 | variables d'état | `population/generator.py`, `population/sources.py` | V1 (foyer unique), V3 (population) | âges, composition, salaires, actifs initiaux |
| **Paramétrage direct** | Fixer un paramètre observable depuis une source externe **sans faire tourner le modèle** | paramètres `treatment: DIRECT` | `population/sources.py` → surcharges de config | V1→V3 | prix, `credit.annual_rate`, `r_k(âge)` issus des NTA, `p_episode_monthly_by_age` |
| **Calibration** | Ajuster des paramètres **non observables** pour approcher des cibles | paramètres `treatment: CALIBRATE` retenus par Morris | `analysis/calibration.py` | fin V2 au plus tôt, V3 (Phase 9) | `aspiration_init`, poids d'allocation, `stress_sensitivity` |
| **Validation** | Confronter le modèle à des cibles **non utilisées** pour la calibration | le modèle entier | `analysis/patterns.py` | après calibration | P4, P5, P6 |
| **Analyse de sensibilité** | Mesurer l'influence des paramètres sur les sorties | registre | `analysis/sensitivity.py` | **avant** calibration (Morris, réduction de dimension) et **après** (Sobol, robustesse) | indices μ*, S1, ST |
| **POM** | Exiger la reproduction **simultanée** de plusieurs patterns à plusieurs niveaux | structure + paramètres | `config/patterns.yaml`, `analysis/patterns.py` | conception (Phase 2, filtre de complexité) et validation (Phase 9) | P1+P2+P3 en calibration, P4–P6 en validation |

Le niveau 1 « initialisation » du schéma de l'auteur **n'est pas de la calibration** ; le niveau 2 fusionnait paramétrage direct et calibration ; le niveau 3 fusionnait calibration et validation. Le code reflète cette séparation : une fonction par opération, aucune ne peut appeler l'autre en dehors du pipeline §6.

### 1.1 Chaîne complète (ordre d'exécution, commande `family-abm calibrate`)

```
data/raw ──► population/sources.py ──► (a) distributions d'initialisation  ──► generator
                                   └─► (b) surcharges DIRECT                ──► config résolue
                                   └─► (c) cibles P1–P7 (data/processed/targets/)
config/patterns.yaml (rôles FIGÉS, hash vérifié)  ──► partition {calibration, validation, exploratory}
Morris (registre, sa: true)  ──► ~8 paramètres libres (treatment: CALIBRATE uniquement)
CalibrationEngine(grille|LHS) sur P1–P3  ──► point calibré θ̂
Validation sur P4–P6 (jamais vue par la perte) ──► pattern_results(role=validation)
Sobol autour de θ̂  ──► robustesse des conclusions
```

## 2. Les six niveaux de validation

Seuls **V-1 et V-2 sont binaires** (porte). Les autres produisent des écarts **à discuter**, pas des verdicts.

| Niveau | Contenu | Version / Phase | Critère | Module | Test / commande |
|---|---|---|---|---|---|
| **V-1 CODE** | tests unitaires, invariants, conservation, déterminisme par seed, indépendance d'ordre, indépendance des foyers | V1 / Ph. 4 | 100 % des invariants passent sur 100 seeds × 240 pas | `nta/invariants.py`, `tests/` | `pytest tests/unit tests/invariants` ; `family-abm verify --seeds 100 --horizon 240` |
| **V-2 COMPTABLE** | identité NTA par personne, bouclage intra-ménage, équation de désépargne, conservation globale, cohérence caches/Ledger, imputation ONU bouclée indépendamment | V1 / Ph. 4 | `|residual| ≤ 0,01 FCFA` à chaque pas, pour chaque personne et chaque foyer | `nta/accounts.py`, `nta/attribution.py`, `nta/imputation.py` | `pytest tests/invariants/test_nta_identities.py` |
| **V-3 COMPORTEMENTALE** | réponses aux chocs : signe correct, ordre de grandeur plausible ; trajectoires cohérentes ; taux `no_applicable_plan` | V2 / Ph. 6 | table de signes §2.1 respectée sur la moyenne de 100 réplications ; `no_applicable_plan_rate ≤ 5 %` (définition 20 §7.4) | `analysis/patterns.py` | `family-abm validate --level behavioral` |
| **V-4 EMPIRIQUE** | comparaison aux données observées (âge, revenu, consommation, emploi, transferts) | V3 / Ph. 9 | écart quantifié par pattern et discuté — pas nécessairement faible | `analysis/patterns.py` | `family-abm validate --level empirical --calibration <id>` |
| **V-5 SENSIBILITÉ** | hiérarchie des influences ; robustesse des conclusions autour de θ̂ | V2 (Morris) / V3 (Sobol) | hiérarchie établie ; signe des effets des expériences inchangé sur le 90 % de l'intervalle Sobol | `analysis/sensitivity.py` | `family-abm sa morris` ; `family-abm sa sobol --around <calibration_id>` |
| **V-6 POPULATION** | profils NTA agrégés, distributions, Gini, pauvreté | V3 / Ph. 9 | le profil de LCD agrégé (≥ 1 000 foyers) présente la forme en U (§3.1, critère de forme) | `nta/profiles.py`, `analysis/patterns.py` | `family-abm validate --level population` |

### 2.1 Table de signes V-3 (réponses attendues aux chocs, à seed commun, scénario vs `baseline`)

| Scénario | Indicateur | Signe attendu | Fenêtre |
|---|---|---|---|
| `job_loss` | `debt_to_income` | + | 12 mois après le choc |
| `job_loss` | `consumption_private` | − | 6 mois après |
| `job_loss` | `rav_per_eq` | − | 6 mois après |
| `illness` | `health_spending` | + | 6 mois après |
| `illness` | `essential_unmet` | ≥ 0 | 6 mois après |
| `family_allowance` | `rav_per_eq` | + | après le mois 24 |
| `family_allowance` | `education_years_*` (enfants) | ≥ 0 | horizon |
| `free_care` | `cf[need=health]` | − ; `cg[need=health]` + | après le mois 24 |
| `economic_shock` | `rav_per_eq` | − | 12 mois après le mois 60 |

« Ordre de grandeur plausible » : l'effet relatif moyen est dans [0,1 ×, 10 ×] l'amplitude relative du choc ; hors de cet intervalle, l'écart est **rapporté et expliqué**, pas corrigé par ajustement.

## 3. Patterns P1–P7 — calcul exact

Notation : `prof_X(a)` = colonne `X` de `nta_age_profile` (moyenne annuelle par tête, âge entier `a`), agrégée sur l'ensemble des foyers et des réplications d'un contexte (moyenne pondérée par `person_years`). Âges retenus `A` = âges avec `person_years ≥ 30` dans la simulation **et** présents dans la cible. Normalisation NTA : `X_norm(a) = X(a) / ȳl₃₀₋₄₉` (moyenne de `yl` sur 30–49 ans) — appliquée **à la simulation et à la cible séparément**, ce qui rend la comparaison indépendante du niveau absolu des prix (utile tant que les montants sont des `PLACEHOLDER`).

`NRMSE(s, o) = sqrt( mean_{a∈A} (s(a) − o(a))² ) / (max_{a∈A} o(a) − min_{a∈A} o(a))`.

| ID | Nom | Niveau | Rôle | Métrique (`metric` de `patterns.yaml`) | Formule | Cible (fichier `data/processed/targets/`) | Tolérance (`pass`) |
|---|---|---|---|---|---|---|---|
| **P1** | Signature du LCD par âge | population | calibration | `lcd_age_profile_nrmse` | `NRMSE(lcd_norm_sim, lcd_norm_obs)` + **critère de forme** : signe de `lcd` correct sur ≥ 90 % des âges de `A` et deux passages par zéro (U) | `nta_profile.parquet` colonne `lcd` | NRMSE ≤ 0,15 et forme OK |
| **P2** | Revenu du travail par âge | population | calibration | `yl_age_profile_nrmse` | `NRMSE(yl_norm_sim, yl_norm_obs)` | `nta_profile.parquet` colonne `yl` (ou EHCVM) | ≤ 0,15 |
| **P3** | Consommation par âge | population | calibration | `c_age_profile_nrmse` | `NRMSE(c_norm_sim, c_norm_obs)` | `nta_profile.parquet` colonne `c` | ≤ 0,15 |
| **P4** | Orientation et volume des transferts | population | **validation** | `transfer_direction_by_age` | (i) concordance de signe `sign(tau_net_intra_sim(a)) = sign(tau_net_intra_obs(a))` sur `A` ; (ii) âge de bascule donneur→receveur `|a*_sim − a*_obs|` ; (iii) ratio de volume `Σ|tau_net_intra_sim| / Σ|tau_net_intra_obs|` (normalisés) | `nta_profile.parquet` colonne `tau_net_private` | concordance ≥ 80 %, `|Δa*| ≤ 5` ans, ratio ∈ [0,67 ; 1,5] |
| **P5** | Distribution dette/revenu entre foyers | population | **validation** | `dti_distribution_ks` | statistique de Kolmogorov–Smirnov D entre la distribution simulée de `debt_to_income` (dernière année, 1 valeur par foyer) et l'observée ; + écart de part de foyers endettés | `ehcvm_dti.parquet` | D ≤ 0,20 ; |Δ part endettée| ≤ 10 points |
| **P6** | Reste-à-vivre / pauvreté | population | **validation** | `poverty_rate_and_rav_ks` | `|poverty_rate_sim − poverty_rate_obs|` et KS sur `rav_per_eq` normalisé par sa médiane | `ehcvm_rav.parquet`, `ansd_poverty.parquet` | Δ ≤ 5 points ; D ≤ 0,20 |
| **P7** | Trajectoires intergénérationnelles | population | exploratoire | `education_by_income_gradient` | `mobility_gradient` (04 §3.2) comparé, **sans tolérance**, au gradient scolarisation × quintile de l'EHCVM | `ehcvm_education_gradient.parquet` | aucune — jamais une cible |

Les tolérances sont des **seuils de rapport**, pas des objectifs d'optimisation : un pattern de validation qui échoue est rapporté tel quel dans le Chapitre 6 (« reproduit P1 et P4, échoue sur P5, voici pourquoi »).

### 3.1 Patterns au niveau foyer (V1–V2, avant population)

Avant la V3, `nta_age_profile` d'un seul foyer couvre peu d'âges. On calcule alors les variantes **qualitatives** (V-3) : `P1q` = signe du LCD par membre sur toute la période (E1, critère de sortie V1) ; `P4q` = sens des transferts (parents donneurs, enfants receveurs). Ce sont des contrôles, pas des patterns POM.

### 3.2 Affectation figée et garde-fou

- `config/patterns.yaml` : `frozen: true`, `assignment_hash = sha256("P1:calibration|P2:calibration|…|P7:exploratory")` (couples triés par id, séparateur `|`).
- `tests/unit/test_patterns_frozen.py` : recalcule le hash ; échec si différent.
- Toute modification exige : nouveau hash + entrée datée dans `docs/DECISIONS.md` justifiant le changement **avant** toute nouvelle calibration. Un commit modifiant `patterns.yaml` sans modifier `docs/DECISIONS.md` fait échouer `tests/architecture/test_pattern_change_logged.py` (comparaison `git diff` de la PR, sauté hors CI).
- L'affectation est recopiée dans l'ODD (section « Purpose and patterns »).

## 4. Données (`data/`, `population/sources.py`)

### 4.1 Interface commune

```python
class DataSource(Protocol):
    name: Literal["synthetic", "nta_profiles", "ehcvm"]
    def available(self) -> bool: ...
    def initial_distributions(self) -> InitDistributions        # âges, composition, salaires, actifs, emploi
    def direct_parameters(self) -> dict[str, Any]               # surcharges par chemin pointé, avec provenance DIRECT + source
    def targets(self, pattern_ids: Sequence[str]) -> dict[str, pa.Table]
```

`resolve_source(cfg)` : si `data.source` indisponible → repli `synthetic`, avertissement journalisé et champ `data_source` du run = source **effective** ; `run.json.failure` reste nul mais `run.json` reçoit `data_fallback: {requested, used, reason}`.

### 4.2 Adaptateurs

| Source | Lit | Produit | Disponibilité |
|---|---|---|---|
| `synthetic` | `config/*` uniquement | distributions issues des placeholders ; **cibles jumelles** (§7) | toujours |
| `nta_profiles` | `data/raw/nta/senegal_profiles.{csv,xlsx}` (CREFAT) | `direct_parameters` : `consumption_requirements` relatifs par âge, profil `yl` ; cibles P1–P4 | dès réception |
| `ehcvm` | `data/raw/ehcvm/{2018,2021}/…` (Stata/CSV) | distributions d'initialisation (ménages 5–8 membres, composition comparable) ; cibles P5–P7 ; `p_episode_monthly_by_age`, chocs d'emploi | dès accord d'accès |

Scripts de préparation : `python -m family_abm.population.prepare {nta|ehcvm}` → écrit `data/processed/` (idempotent, journalise la version des fichiers bruts par sha256 dans `data/processed/MANIFEST.json`). Les calculs sur microdonnées utilisent les **poids d'échantillonnage** de l'enquête.

### 4.3 Schémas des fichiers `data/processed/`

| Fichier | Colonnes |
|---|---|
| `targets/nta_profile.parquet` | `age i32, yl f64, c f64, cf f64, cg f64, lcd f64, tau_net_private f64, tau_net_public f64, ya_minus_s f64, year i32, source str` (unités : FCFA annuels par tête) |
| `targets/ehcvm_dti.parquet` | `household_weight f64, debt_to_income f64, indebted bool, survey_year i32` |
| `targets/ehcvm_rav.parquet` | `household_weight f64, rav_per_eq f64, survey_year i32` |
| `targets/ansd_poverty.parquet` | `year i32, poverty_rate f64, poverty_line_per_eq f64, scope str` |
| `targets/ehcvm_education_gradient.parquet` | `income_quintile i32, mean_education_years f64, n i32` |
| `init/household_compositions.parquet` | `template_id str, member_ages json, weight f64` |
| `init/wages.parquet` | `role_hint str, employment str, wage_monthly f64, weight f64` |
| `init/assets.parquet` | `savings f64, debt f64, weight f64` |
| `MANIFEST.json` | provenance, sha256 des bruts, date, version du script |

### 4.4 Procédure d'accès (à lancer en Phase 0, risque R9)

1. **EHCVM 2018-19 et 2021-22** : demande sur le catalogue ANADS de l'ANSD (formulaire d'accès aux microdonnées, objet de recherche, engagement de confidentialité) et/ou catalogue Microdata de la Banque mondiale. Délai à anticiper ; aucune microdonnée commitée (`data/raw/` dans `.gitignore`) ; seules les cibles agrégées non identifiantes vont dans `data/processed/`.
2. **Profils NTA Sénégal** : demande au CREFAT (Université de Thiès) ; tracer dans `data/README.md` la référence, l'année et les conventions (normalisation, âge terminal).
3. **Repli** (ordre) : `ehcvm` indisponible → initialisation depuis `nta_profiles` + gabarits ; `nta_profiles` indisponible → `synthetic`, et le mémoire dit « modèle illustratif » (feuille de route §22, point 4).

## 5. Analyse de sensibilité (`analysis/sensitivity.py`, SALib)

### 5.1 Espace des paramètres

Construit depuis `config/parameters_registry.yaml` : entrées `sa: true`. `*` sur profils = **un multiplicateur commun** `m ∈ bounds/valeur_ref` appliqué à tous les profils (préserve la gradation bébé→parent). Paramètres entiers (`planning_horizon`, `max_alternatives`, `memory.capacity`) : échantillonnés en continu puis arrondis. Tables par âge : `scale_bounds` multiplicatif. Les variables de traitement (`treatment_variable_of` non vide) sont **incluses** dans Morris (on veut connaître leur influence) mais exclues de toute calibration (§8).

### 5.2 Morris (criblage, avant calibration)

- `SALib.sample.morris.sample(problem, N=20, num_levels=4, optimal_trajectories=None, seed=…)` → `r = 20` trajectoires × (k + 1) points ; k ≈ 25 → ≈ 520 points.
- Chaque point : `n_rep = 10` réplications (seeds communs à tous les points).
- Deux campagnes : **Phase 6 (E-SA, V2)** : `model.version = v2`, foyer de référence unique (`n_households = 1`, la population n'existe qu'en V3), sorties de niveau foyer ; **Phase 9 (V3)** : `model.version = v3`, `n_households = 100`, sorties de niveau population.
- Sorties analysées (une analyse par sortie) — Phase 6 : `debt_to_income_terminal`, `savings_rate_mean`, `consumption_volatility`, `education_years_mean`, `lcd_household` (moyenne) ; Phase 9 : en plus `lcd_age_profile_nrmse`, `yl_age_profile_nrmse`, `c_age_profile_nrmse` (vs cibles disponibles, sinon jumelles), `poverty_rate`, `gini_income`.
- Indices : μ*, intervalle de confiance bootstrap de μ* (1 000 rééchantillonnages), σ.
- **Règle de sélection** des paramètres libres de calibration (campagne Phase 9) : candidats = `treatment: CALIBRATE` ; on normalise μ* par sortie (`μ*/max μ*`), on prend le maximum sur les trois sorties P1–P3 ; on retient ceux avec score ≥ 0,1, triés, **au plus 8** ; si moins de 4 dépassent 0,1, on retient les 4 premiers et on le rapporte. Les paramètres non retenus sont **fixés** à leur valeur de référence (provenance `FIX`, note « écarté par Morris, μ*_norm = … »).
- Budget : Phase 6 : 5 200 runs × 1 foyer (≈ 22 h mono-cœur à 15 s/run → ≈ 3 h sur 8 cœurs) ; Phase 9 : 520 × 10 = 5 200 runs × 100 foyers. Objectif ≤ 12 h sur 8 cœurs ; sinon `n_rep = 5` et `n_households = 50`, rapporté.

### 5.3 Sobol (robustesse, après calibration)

- Espace : les paramètres libres retenus, bornes = θ̂ ± 20 % (tronquées aux bornes du registre) **+** les variables de traitement des expériences (bornes du registre), pour vérifier que les conclusions tiennent.
- `SALib.sample.sobol.sample(problem, N=512, calc_second_order=False, seed=…)` → 512 × (k + 2) points (k = 10 → 6 144 points), `n_rep = 5`.
- Indices S1, ST avec IC 95 %. Critère V-5 : pour chaque conclusion d'expérience (signe d'un effet), le signe est conservé sur ≥ 90 % des points échantillonnés.
- E-SA de V2 (`50_SPEC_EXPERIMENTS.md`) applique Sobol aux 8–10 survivants de Morris **sans** calibration préalable (feuille de route §12).

### 5.4 Sorties

`experiments/results/sensitivity/<study_id>/` : `problem.json`, `samples.parquet` (point × paramètres), `outputs.parquet` (point × réplication × sortie), `indices.parquet` (schéma `sensitivity_indices` de 04 §2.12). Figures : `fig_sa_morris_<metric>.svg` (nuage μ* × σ, étiquettes), `fig_sa_sobol_<metric>.svg` (**barres horizontales triées** S1 et ST, barres d'erreur IC 95 %).

## 6. `CalibrationEngine` (`analysis/calibration.py`)

```python
class CalibrationLeakError(RuntimeError): ...       # pattern non-calibration dans la perte
class TreatmentCalibrationError(RuntimeError): ...  # variable de traitement dans les libres

@dataclass(frozen=True)
class CalibrationSpec:
    calibration_id: str
    free_parameters: tuple[str, ...]          # chemins du registre, issus de Morris
    design: Literal["grid", "lhs"]
    levels: int = 4                            # grille : niveaux par paramètre
    n_lhs: int = 300                           # LHS : nombre de candidats
    n_replications: int = 10
    patterns: tuple[str, ...] = ("P1", "P2", "P3")
    n_households: int = 1000
    planned_experiments: tuple[str, ...] = ()  # pour le garde-fou §8
    seed: int = 0

class CalibrationEngine:
    def __init__(self, base_config: ResolvedConfig, registry: ParameterRegistry,
                 patterns: PatternRegistry, targets: Mapping[str, pa.Table]): ...
    def run(self, spec: CalibrationSpec) -> CalibrationResult
    def loss(self, simulated: Mapping[str, PatternValue]) -> float
    def validate(self, result: CalibrationResult) -> list[PatternResult]   # P4–P6, APRÈS sélection
```

Règles :
1. **Garde-fous au constructeur et dans `run`** : tout `p ∈ spec.patterns` avec `role != "calibration"` → `CalibrationLeakError`. `targets` passé à `loss` est filtré par rôle **à la source** (le moteur ne reçoit jamais les tables P4–P6 avant `validate`). Tout paramètre libre dont `treatment != CALIBRATE` ou dont `treatment_variable_of ∩ planned_experiments ≠ ∅` → `TreatmentCalibrationError`. `hash` de `patterns.yaml` vérifié.
2. **Plan** : `grid` si `levels^k ≤ 1 500`, sinon `lhs` (`scipy.stats.qmc.LatinHypercube`, seed fixée).
3. **Perte** : `L(θ) = (1/3) Σ_{p∈{P1,P2,P3}} NRMSE_p(θ)`, chaque NRMSE calculé sur le profil moyen des `n_replications` (seeds communs à tous les candidats — réduction de variance). Un candidat violant un invariant V-2 est rejeté (`loss = +inf`, raison journalisée).
4. **Sélection** : `θ̂ = argmin L` ; on rapporte aussi l'ensemble des candidats à `L ≤ L_min × 1,05` (**ensemble quasi-équivalent**, mesure de sous-détermination, Windrum et al.) et la dispersion des paramètres dans cet ensemble.
5. **Validation** : `validate()` relance θ̂ avec **de nouvelles seeds** (`seed + 10 000`) et calcule P4–P6, plus P1–P3 (contrôle de stabilité) et P7 (exploratoire).
6. **Rapport** `calibration/<id>/report.md` généré : paramètres libres et origine (Morris), plan, θ̂, ensemble quasi-équivalent, table P1–P6 (simulé, cible, distance, tolérance, pass), mention obligatoire §9, durée.
7. Sorties : `calibration_candidates.parquet`, `pattern_results.parquet`, `calibrated_overrides.yaml` (surcharges à appliquer aux expériences finales ; provenance `CALIBRATED`, `source: calibration/<id>`).

CLI : `family-abm calibrate --spec config/calibration.yaml [--twin]` ; `family-abm validate --calibration <id>`.

## 7. Expérience jumelle (twin) — vérifier l'outil avant les données

But : prouver que le `CalibrationEngine` retrouve des paramètres **connus** ; c'est un test de l'outil, **pas** une validation du modèle.

1. Choisir `θ*` (tiré dans les bornes, seed fixée) pour les paramètres libres.
2. Simuler `θ*` avec `n_households = 1000`, seeds `S*` → cibles jumelles P1–P6 (`data/processed/targets/twin_<id>/`).
3. Calibrer avec seeds **différentes** de `S*`.
4. Critères : `|θ̂_j − θ*_j| / (borne_max − borne_min) ≤ 0,10` pour les paramètres à μ*_norm ≥ 0,3 ; les autres peuvent ne pas être identifiés → rapporté comme résultat d'identifiabilité. P4–P6 de θ̂ passent leurs tolérances.
5. Test automatisé réduit : `tests/integration/test_calibration_twin.py` (2 paramètres, grille 5×5, 50 foyers, 60 pas, 3 réplications).

## 8. Règle : on ne calibre jamais une variable de traitement

Application dans le code : (i) `parameters_registry.yaml` porte `treatment_variable_of` ; (ii) `CalibrationSpec.planned_experiments` = liste des expériences du plan courant (par défaut : toutes celles de `config/experiments/`) ; (iii) `TreatmentCalibrationError` (§6) ; (iv) `ExperimentRunner` refuse d'appliquer `calibrated_overrides.yaml` si une surcharge porte sur un facteur de l'expérience (`50_SPEC_EXPERIMENTS.md` §1.4) ; (v) test `tests/unit/test_calibration_guards.py`.

Concrètement : `planning_horizon`, `max_alternatives` (E2, E9), `discounting.beta` (E3), `risk.lambda` (E5), `allocation.mode` (E6), `model.version` et `affect.enabled` (E4, E9), `population.n_households` (E7) ne sont **jamais** libres en calibration.

## 9. Réserve méthodologique — à écrire telle quelle

> Dans ce contexte, il n'y a probablement pas de véritable hors-échantillon temporel : on ne dispose pas de deux périodes NTA sénégalaises indépendantes. Ce qui est réellement fait est une **validation sur patterns retenus** — des patterns différents, issus des mêmes données, mais non utilisés pour la calibration. C'est plus faible qu'une validation hors-échantillon, et le mémoire l'écrit ainsi. Il n'annonce pas une validation hors-échantillon qu'il ne fait pas.

Le rapport de calibration (§6.6) et la vue UI « Validation » (`70_SPEC_UX_UI.md`) reproduisent cette mention. Si les deux vagues EHCVM (2018-19, 2021-22) sont toutes deux accessibles, une validation **inter-vagues** sur P5–P6 est possible et doit être nommée comme telle (validation sur une autre vague, mêmes structures), sans être qualifiée de hors-échantillon temporel du modèle NTA.

## 10. Question de recherche n°5 — formulation C (Q7)

Objectif méthodologique du Chapitre 6, formulé :

> *« Dans quelle mesure les profils NTA nationaux et les enquêtes ménages disponibles permettent-ils d'initialiser et de calibrer un modèle multi-agents de foyer, et quelles limites cette démarche rencontre-t-elle ? »*

Les livrables qui y répondent : couverture des paramètres par provenance (table §11, T6-4), identifiabilité (expérience jumelle, ensemble quasi-équivalent), écarts de validation P4–P6. Une réponse négative ou nuancée est un résultat valide. Bascule en sous-question officielle (B) seulement si la porte V2 est verte dans les temps.

## 11. Tests

| Fichier | Vérifie |
|---|---|
| `tests/invariants/test_nta_identities.py` | identité par personne, Σ intra = 0, désépargne du foyer, conservation globale — 100 seeds × 240 pas (marqueur `slow`) ; 5 seeds en CI rapide |
| `tests/invariants/test_imputation_closure.py` | la règle ONU boucle indépendamment (Fiche 3) |
| `tests/invariants/test_caches_match_ledger.py` | caches d'état = soldes du Ledger |
| `tests/regression/test_reproducibility.py` | même seed → tables identiques (hash des Parquet) |
| `tests/unit/test_household_independence.py` | un foyer seul ≡ le même dans une population |
| `tests/unit/test_patterns.py` | NRMSE, KS, concordance de signe, âge de bascule sur profils construits à la main |
| `tests/unit/test_patterns_frozen.py` | hash de l'affectation |
| `tests/unit/test_calibration_guards.py` | `CalibrationLeakError`, `TreatmentCalibrationError` |
| `tests/unit/test_sensitivity_space.py` | construction du `problem` SALib depuis le registre, multiplicateurs `*`, arrondis d'entiers |
| `tests/unit/test_sources_fallback.py` | repli `synthetic` et champ `data_fallback` |
| `tests/integration/test_calibration_twin.py` | §7 réduit |
| `tests/integration/test_behavioral_signs.py` | table §2.1 sur 20 réplications (marqueur `slow`) |

## 12. Livrables du Chapitre 6 (validation)

| Code | Livrable | Fichier généré par `analysis/figures.py` |
|---|---|---|
| T6-1 | Table des patterns : rôle, niveau, métrique, cible, tolérance | `tab_patterns.md` |
| T6-2 | Indices de Morris (toutes sorties) | `tab_sa_morris.md` |
| T6-3 | Indices de Sobol (S1, ST, IC) | `tab_sa_sobol.md` |
| T6-4 | Paramètres par provenance (DIRECT / CALIBRATED / FIX_LIT / EXPLORED / FIX / PLACEHOLDER) | `tab_parameter_provenance.md` |
| T6-5 | Résultats de calibration et de validation P1–P6 (simulé, cible, distance, pass) | `tab_pom_results.md` |
| T6-6 | Statut des six niveaux V-1…V-6 | `tab_validation_levels.md` |
| F6-1 | Observé vs simulé, un panneau par pattern ; **set calibration et set validation visuellement distingués** (badge + trait) ; observé en trait discontinu ; bande 5–95 % des réplications | `fig_pom_observed_vs_simulated.svg` |
| F6-2 | Morris μ* × σ | `fig_sa_morris_<metric>.svg` |
| F6-3 | Sobol barres horizontales triées | `fig_sa_sobol_<metric>.svg` |
| F6-4 | Expérience jumelle : θ* vs θ̂ par paramètre (points + intervalle de l'ensemble quasi-équivalent) | `fig_twin_recovery.svg` |
| F6-5 | Profil de LCD agrégé simulé vs cible (V-6) | `fig_lcd_age_profile_population.svg` |

---

## Détails tranchés dans ce document

- Normalisation des profils par ȳl₃₀₋₄₉ côté simulation **et** cible ; NRMSE normalisée par l'étendue de la cible ; âges avec `person_years ≥ 30`.
- Tolérances de rapport : P1–P3 NRMSE ≤ 0,15 ; P4 concordance ≥ 80 %, |Δa*| ≤ 5 ans, ratio ∈ [0,67 ; 1,5] ; P5–P6 KS ≤ 0,20, écarts ≤ 10 / 5 points.
- Table de signes V-3 (§2.1) et intervalle « ordre de grandeur » [0,1 × ; 10 ×].
- Seuil `no_applicable_plan_rate ≤ 5 %` (traduction de « quelques pour cent », Fiche 2 ; aligné sur 20 §7.4 et 90 G2.8).
- Sélection Morris : score μ*_norm ≥ 0,1 sur P1–P3, 4 ≤ k ≤ 8 ; `n_rep = 10` ; Phase 6 sur 1 foyer, Phase 9 sur 100 foyers.
- Sobol : N = 512, sans second ordre, θ̂ ± 20 % ; critère de robustesse 90 %.
- Calibration : grille si ≤ 1 500 candidats sinon LHS 300 ; perte = moyenne des trois NRMSE ; ensemble quasi-équivalent à +5 % ; validation avec seeds décalées de 10 000.
- Expérience jumelle : critère de récupération 10 % de l'étendue pour paramètres à μ*_norm ≥ 0,3.
- Format du hash d'affectation (`P1:calibration|…`) et test de journalisation des changements.
- Schémas `data/processed/` et `MANIFEST.json` ; champ `data_fallback` dans `run.json` (à ajouter à `04_DATA_MODEL.md` §2.1).
- Métriques utilisées ici absentes du catalogue 04 §3, à y ajouter : `savings_rate_mean`, `education_years_mean`, `no_applicable_plan_rate` (définitions dans `50_SPEC_EXPERIMENTS.md` §2).
