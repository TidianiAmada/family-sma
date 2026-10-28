# 90 — Stratégie de tests et portes de passage

> Les tests sont un **livrable** du mémoire (niveau de validation V-1 et V-2). Une porte est un script exécutable qui coche ou non chaque critère de sortie ; `docs/GATES.md` est généré par ce script, jamais édité à la main.

---

## 1. Organisation

```
tests/
├── unit/              ← une fonction / une classe ; rapides (< 1 s chacun)
├── properties/        ← hypothesis : propriétés universelles (conservation, bornes, monotonie)
├── invariants/        ← V-1/V-2 : identités comptables sur runs complets, N seeds
├── integration/       ← un run complet par scénario ; tables produites conformes aux schémas
├── regression/        ← trajectoires de référence (golden) et non-régression entre versions
├── architecture/      ← contrats de couches, absence de classes par rôle, absence de nombres en dur
├── performance/       ← budgets de temps (marqueur @pytest.mark.perf, hors CI rapide)
└── api/, web/         ← après porte V1 (60_SPEC_API, 70_SPEC_UX_UI)
```

Marqueurs : `@pytest.mark.slow` (≥ 10 s), `@pytest.mark.perf`, `@pytest.mark.v2`, `@pytest.mark.v3`. La CI rapide exécute tout sauf `slow` et `perf` ; la porte exécute tout.

## 2. Familles de tests transversales

### 2.1 Architecture (`tests/architecture/`)

| Test | Vérifie |
|---|---|
| `test_layers.py` | contrats C1–C5 de `01_ARCHITECTURE §3` via `import-linter` |
| `test_odd_sync.py` | chaque paramètre de `config/` actif dans la version courante et chaque variable d'état collectée est cité dans l'ODD de cette version (`odd/ODD_v{1,2,3}_*.md`) ; sert G1.6, G2.6, G3.7 |
| `test_single_person_class.py` | une seule classe héritant de `mesa.Agent` côté personne ; aucune sous-classe de `PersonAgent` dans `src/` |
| `test_no_role_branching.py` | analyse AST : aucune comparaison avec `Role.*` ou une chaîne de rôle dans `agents/`, `decision/`, `cognition/`, `economy/`, `health/` (seul `collectors.py` lit le rôle, pour l'étiquetage) |
| `test_no_magic_numbers.py` | AST : aucun littéral numérique hors `{0, 1, -1, 0.0, 1.0, 2, 12}` dans `src/family_abm/{agents,decision,cognition,economy,health}` ; exceptions listées explicitement dans le test, chacune justifiée |
| `test_single_polymorphic_point.py` | seul `DecisionEngine` est un `Protocol`/ABC avec plusieurs implémentations (la 2ᵉ étant `ScriptedEngine` des tests) |

### 2.2 Déterminisme (`tests/regression/test_reproducibility.py`)

- Même seed, même config → tables Parquet identiques **octet par octet** (hors `run_id`, `created_at`, `duration_s`) sur 3 scénarios.
- `test_household_independence` : le foyer `h0003` simulé seul (avec la graine dérivée) = le foyer `h0003` dans une population de 50.
- `test_order_invariance` : permuter l'ordre des personnes au Temps 1 ne change pas les allocations (V1–V2).
- `test_stream_stability` : ajouter un tirage dans `rng["health"]` ne change pas la série de chocs de revenu.

### 2.3 Trajectoires de référence (golden)

- `tests/regression/golden/v1_baseline_seed42.json` : empreinte (SHA-256) des tables `household_steps` et `nta_person_steps` de V1, seed 42, 240 pas.
- Régénération **uniquement** par `make golden-update` avec un message de commit `GOLDEN:` expliquant le changement de modèle (et l'ODD mis à jour).
- **Non-régression inter-versions** : `model.version: v2` avec `cognition.bdi.enabled=false`, `cognition.memory.enabled=false`, `loops.b2.enabled=false`, `cognition.discounting.enabled=false` doit reproduire l'empreinte V1. Idem V3 avec `affect.enabled=false`, `risk.cpt.enabled=false`, `household_rules.separate_spheres.enabled=false` → empreinte V2 (tests `test_v2_reduces_to_v1` et `test_v3_off_equals_v2`). C'est la preuve que chaque version **ajoute** sans casser.

### 2.4 Invariants sur campagne (`tests/invariants/`)

- `test_invariants_100_seeds` : 100 seeds × 240 pas × scénarios {baseline, job_loss, illness, family_allowance, free_care, economic_shock} ; zéro `InvariantViolation`. Marqué `slow` ; exécuté par la porte.
- Les identifiants d'invariants (INV-xx) sont définis dans `10_SPEC_V1_ECONOMIC.md` ; chaque INV a au moins un test unitaire qui **fait échouer volontairement** l'invariant (injection d'une écriture fautive) pour prouver qu'il détecte la faute.

### 2.5 Propriétés (`tests/properties/`, hypothesis)

Exemples obligatoires :
- `allocate()` : Σ accordé ≤ budget + emprunt ; jamais d'accord partiel sur indivisible ; monotonie (budget ↑ ⇒ aucun montant accordé ↓) ; invariance par permutation des demandes ; poids égaux + demandes égales ⇒ allocations égales.
- `SatisficingEngine` : `max_alternatives=1, planning_horizon=0` ⇒ règle `reactive` ; aspiration 0 ⇒ première alternative choisie ; nombre d'alternatives évaluées ≤ `max_alternatives`.
- `MemoryService` (V2) : taille ≤ capacité ; activation décroissante avec le temps sans répétition ; répétition ⇒ activation ↑.
- Modulation (V3) : stress = 0 ⇒ profil effectif = profil de base ; stress ↑ ⇒ horizon et alternatives effectifs ↓ (non strictement).
- NTA : pour toute séquence aléatoire d'écritures valides, l'identité de flux par personne tient à ε.

### 2.6 Performance (`tests/performance/`)

Budgets de `01_ARCHITECTURE §8`, mesurés sur 3 exécutions (médiane), machine de référence notée dans `docs/GATES.md`. Échec si > budget ; avertissement si > 0,8 × budget.

## 3. Portes de passage

Le script `scripts/gate.py vX` exécute les commandes ci-dessous, coche chaque case et réécrit `docs/GATES.md`. Une case manuelle (ex. « ODD cohérent ») est cochée par un fichier `docs/attestations/<gate>-<item>.md` signé par l'auteur (date + commit), que le script vérifie.

### 3.1 Porte V1 — baseline économique

| # | Critère (feuille de route §11) | Vérification |
|---|---|---|
| G1.1 | Identités NTA bouclent à ε à chaque pas, 20 ans, 100 seeds | `pytest tests/invariants -m "not v2 and not v3"` |
| G1.2 | Aucune valeur ne disparaît : Σentrées − Σsorties = Δactifs | INV de conservation (dans G1.1) |
| G1.3 | La dette suit exactement l'équation de désépargne | INV dette (dans G1.1) |
| G1.4 | Même seed → trajectoire identique | `pytest tests/regression/test_reproducibility.py` |
| G1.5 | Signe du LCD correct pour les 6 membres sur toute la période (bébé, enfant, adolescent > 0 ; parents < 0) | `pytest tests/integration/test_lcd_signs.py` (sur E1 ; un mois isolé de signe inverse — ex. parent au chômage — est rapporté, le test porte sur la moyenne annuelle et documente les exceptions) |
| G1.6 | ODD-V1 écrit et cohérent avec le code | attestation manuelle + `pytest tests/architecture/test_odd_sync.py` (+ `/odd-sync` sans écart ouvert) |
| G1.7 | Suite de tests passe et couvre les invariants | `pytest` complet + couverture ≥ 90 % sur `economy/`, `nta/`, `agents/allocation.py` |
| G1.8 | Run de 20 ans < 5 s | `pytest tests/performance -k v1` |
| G1.9 | Contrats d'architecture | `lint-imports` + `tests/architecture` |
| G1.10 | E1 exécutée et rapportée | `experiments/results/experiments/E1/summary.parquet` existe + figure `fig_E1_lcd_by_member` |

### 3.2 Porte V2 — cognitive

| # | Critère (§12) | Vérification |
|---|---|---|
| G2.1 | Tous les critères V1 restent verts, **y compris avec tous les blocs V2 activés** | `gate.py v1` + `pytest tests/invariants -m v2` (100 seeds, `model.version=v2`, BDI, mémoire, B2 et β-δ actifs) |
| G2.2 | Non-régression : V2 bascules off = empreinte V1 | `pytest tests/regression -k test_v2_reduces_to_v1` |
| G2.3 | E2 produit une différence mesurable **ou une absence de différence, rapportée** | rapport `E2` présent (le contenu n'est pas jugé par le script) |
| G2.4 | Sensibilité : paramètres influents et hiérarchie identifiés — **Morris puis Sobol** | `sensitivity/morris_v2/indices.parquet` **et** `sensitivity/sobol_v2/indices.parquet` + figures triées |
| G2.5 | ≥ 2 patterns POM reproduits avec un seul jeu de paramètres | `pattern_results` : ≥ 2 `pass=true` pour un même `context_id` |
| G2.6 | ODD-V2 à jour | attestation + `pytest tests/architecture/test_odd_sync.py` |
| G2.7 | Run < 15 s | perf v2 |
| G2.8 | Taux de situations sans plan applicable ≤ 5 % (Fiche 2) | métrique `no_applicable_plan_rate` (= événements `no_applicable_plan` / adoptions tentées, 20 §7.4) sur E2 |

### 3.3 Porte V3 — affective et population

| # | Critère (§14) | Vérification |
|---|---|---|
| G3.1 | V1 et V2 restent verts | `gate.py v2` |
| G3.2 | Non-régression : V3 bascules off = empreinte V2 | `pytest tests/regression -k test_v3_off_equals_v2` |
| G3.3 | E4 exécutée et rapportée, quel que soit le résultat | rapport `E4` présent |
| G3.4 | Profil LCD agrégé sur ≥ 1 000 foyers produit et comparé à une cible | `nta_age_profile` E7 + `pattern_results` P1 |
| G3.5 | ≥ 3 patterns reproduits avec un seul jeu de paramètres, dont ≥ 1 du set validation | `pattern_results` |
| G3.6 | Séparation calibration/validation documentée et respectée | `test_patterns_frozen` + `test_calibration_leak` + attestation |
| G3.7 | ODD-V3 complet | attestation + `pytest tests/architecture/test_odd_sync.py` |
| G3.8 | 1 000 foyers × 240 pas dans le budget | perf v3 |

### 3.4 Porte API (après G2) et porte UI

Définies dans `60_SPEC_API.md` et `70_SPEC_UX_UI.md`. Condition commune : **le moteur reste exécutable sans elles** (`tests/architecture/test_engine_standalone.py` : installation du seul paquet `family_abm` dans un venv propre + run baseline).

## 4. Intégration continue (GitHub Actions)

| Job | Déclencheur | Contenu |
|---|---|---|
| `fast` | chaque push | ruff, mypy, lint-imports, pytest `-m "not slow and not perf"` |
| `invariants` | PR vers `main` | `tests/invariants` (100 seeds) |
| `gate` | manuel / tag | `scripts/gate.py v{1,2,3}` ; publie `docs/GATES.md` en artefact |
| `web` | après porte V1, sur `web/**` | typecheck, Vitest, Playwright |
