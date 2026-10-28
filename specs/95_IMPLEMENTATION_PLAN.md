# 95 — Plan d'implémentation par tickets (pour Claude Code)

> Chaque ticket est une unité de travail livrable en une session, avec ses références de spec, ses fichiers et ses critères d'acceptation. Exécuter dans l'ordre ; un ticket ne commence que lorsque ses dépendances sont **mergées et vertes**. Commande : `/implement-ticket T-xxx`.
>
> Piste A = moteur scientifique (V1 → V2 → V3). Piste B = plateforme (API + interface) : démarre après la porte V1 (schémas de sortie stables) et avance en parallèle ; les écrans cognitifs et affectifs s'activent quand V2/V3 produisent leurs colonnes.

**Règle de chaque ticket :** (1) lire les sections de spec citées ; (2) vérifier que l'ODD de la version décrit le sous-modèle — sinon s'arrêter et le signaler ; (3) écrire les tests d'abord quand le critère est vérifiable ; (4) implémenter ; (5) `uv run pytest -q && uv run lint-imports && uv run mypy src/` ; (6) mettre à jour `docs/MATRICE_QUESTION_MODELE.md` si le ticket crée un composant.

---

## Piste A — Moteur scientifique

### Version V1 — baseline économique (Phases 3–4)

| ID | Titre | Dépend | Spec | Fichiers principaux | Critères d'acceptation |
|---|---|---|---|---|---|
| T-001 | Ossature du dépôt | — | 01 §2, 90 §1, CLAUDE.md | `pyproject.toml`, `Makefile`, arborescence, `.github/workflows/fast.yml`, contrats import-linter | dispositif Claude installé (`.claude/agents`, `.claude/skills`, `.claude/commands`, `docs/REGLES_VALIDATION.md`) ; `uv sync` OK ; `pytest` (0 test) OK ; `lint-imports` OK avec contrats C1–C5 déclarés ; ruff + mypy configurés |
| T-002 | Noyau : types, erreurs, RNG | T-001 | 02 §2–3, 01 §7 | `core/types.py`, `core/errors.py`, `core/rng.py` | tests : sous-flux nommés stables ; même seed ⇒ mêmes tirages ; ajout d'un flux ne perturbe pas les autres |
| T-003 | Configuration validée | T-002 | 03 (tout) | `config/schemas.py`, `config/loader.py`, `config/*.yaml` (V1) | chargement des YAML de 03 ; bornes refusées avec message clair ; surcharges par chemin pointé ; `ConfigHash` stable ; détection `PLACEHOLDER` ⇒ `illustrative=True` ; profils V2/V3 lus sans effet |
| T-004 | ODD dans le dépôt | T-001 | odd/ | `odd/ODD_v0_conceptual.md`, `odd/ODD_v1_economic.md`, `docs/*` | fichiers copiés depuis `specs/odd` ; **l'auteur relit et valide** (attestation) avant T-007 |
| T-005 | Ledger double entrée | T-002 | 02 §8 | `economy/accounts.py`, `economy/ledger.py` | refus : montant ≤ 0, consommation sans bénéficiaire, découvert d'un actif interne, couple (src,dst) incompatible avec la catégorie ; somme globale des soldes = 0 ; tests de propriété |
| T-006 | États, agents, modèle à 3 temps (squelette) | T-003, T-005 | 01 §4, 02 §1, §4 | `agents/states.py`, `agents/person.py`, `agents/household.py`, `model/family_model.py`, `model/scheduler.py`, `tests/conftest.py` (`ScriptedEngine`) | un run de 240 pas avec moteur scripté s'exécute ; l'ordre des 3 temps est tracé et testé ; vieillissement et transitions de profil par la config |
| T-007 | Revenu, emploi, impôts, mise en commun, prix | T-006 | 10 §2–§3 | `economy/labor.py`, `economy/prices.py`, `economy/actions.py` | écritures LABOR_INCOME → TAX → POOLING ; transitions d'emploi seedées ; chocs informels log-normaux ; tests unitaires |
| T-008 | Besoins, santé, scolarité | T-006 | 10 §4–§6, 03 §5–§6 | `agents/states.py` (NeedsState), `health/health.py`, `economy/actions.py` | formules de niveau lissé ; épisodes de santé ; machine à états scolarité (02 §10.4) ; tests |
| T-009 | Moteur satisficing V1 | T-008 | 10 §7, 02 §5, §7 | `decision/engine.py`, `decision/alternatives.py`, `decision/satisficing.py` | `DemandSet` + `DecisionTrace` complets ; règles `first_acceptable` / `fallback_top_need` / `reactive` testées ; ≤ `max_alternatives` évaluées ; impulsivité via `rng["decision_ties"]` |
| T-010 | Allocation, crédit, épargne | T-009, T-005 | 10 §8 | `agents/allocation.py`, `agents/household.py`, `economy/credit.py` | `allocate()` pure ; propriétés 90 §2.5 ; engagements d'abord ; emprunt essentiel borné par le plafond ; arriérés ; intérêts mensuels |
| T-011 | Exécution des actions (Temps 3) | T-010 | 10 §9 | `economy/actions.py`, `economy/public.py` | consommation en nature payée par le pot avec bénéficiaire ; complément depuis le portefeuille ; PUBLIC_INKIND ; argent de poche |
| T-012 | Couche NTA | T-011 | 02 §9, 10 §NTA | `nta/attribution.py`, `nta/accounts.py`, `nta/imputation.py`, `nta/profiles.py` | identité de flux par personne à ε ; Σ τ intra = 0 par foyer ; imputation ONU séparée ; profils par âge |
| T-013 | Invariants (échec dur) | T-012 | 10 §12, 90 §2.4 | `nta/invariants.py`, `tests/invariants/` | chaque INV a un test d'injection qui le fait échouer ; vérification à chaque pas ; échantillonnage configurable |
| T-014 | Collecte et stockage | T-012 | 04 §1–2 | `model/collectors.py`, `io/parquet.py`, `io/catalog.py` | toutes les tables V1 aux schémas exacts ; `run.json` ; catalogue DuckDB interrogeable ; écriture par blocs |
| T-015 | Scénarios et événements | T-011 | 03 §10 | `model/events.py`, `config/scenarios/*.yaml` | 6 scénarios ; événements datés ; table `events` |
| T-016 | CLI et point d'entrée | T-014 | 01 §2, CLAUDE.md, 40 §2, 60 §1 | `__main__.py` (Typer, script console `family-abm`), `api_entry.py` | commandes `run`, `experiment`, `figures`, `gate`, `verify`, `validate`, `sa`, `calibrate` (stubs pour les trois derniers jusqu'aux tickets concernés) ; `api_entry.run_simulation(config, out_dir, on_year_end=None)` testé sans dépendance web |
| T-017 | Indicateurs | T-014 | 04 §3 | `analysis/indicators.py` | chaque indicateur testé sur un jeu de tables construit à la main |
| T-018 | ExperimentRunner + E1 | T-016, T-017 | 50 (runner, E1) | `analysis/experiments.py`, `config/experiments/E1.yaml`, `analysis/figures.py` | E1 sur 100 seeds ; `summary.parquet` ; figures E1 reproductibles par `figures --all` |
| T-019 | Tests transverses + porte V1 | T-013, T-018 | 90 §2–3.1 | `tests/architecture/`, `tests/regression/`, `tests/performance/`, `scripts/gate.py` | **`make gate-v1` tout vert** ; `docs/GATES.md` généré ; empreinte golden V1 enregistrée |

### Version V2 — cognitive (Phases 5–6)

| ID | Titre | Dépend | Spec | Fichiers | Critères |
|---|---|---|---|---|---|
| T-020 | ODD-V2 dans le dépôt | G-V1 | odd/ODD_v2 | `odd/ODD_v2_cognitive.md` | relu et attesté par l'auteur |
| T-021 | MemoryService | T-020 | 20 §3 | `cognition/memory.py` | activation de niveau de base ; capacité ; éviction ; propriétés 90 §2.5 |
| T-022 | Croyances et désirs | T-021 | 20 §4–§5 | `cognition/beliefs.py` | table des croyances implémentée intégralement ; tests par croyance |
| T-023 | Mini-DSL et bibliothèque de plans | T-022 | 20 §7.1–§7.3 | `decision/plans.py`, `config/plans.yaml` | parser sans `eval` ; erreurs de syntaxe au chargement ; tous les plans de la bibliothèque chargés et testés |
| T-024 | Intentions, replanification, intégration au satisficing | T-023 | 20 §6, §7.4, §8 | `decision/satisficing.py`, `decision/plans.py` | persistance / reconsidération ; replanification ; repli + événement `no_applicable_plan` ; règle `plan_step` |
| T-025 | Aspiration adaptative | T-021 | 20 §9 | `cognition/aspiration.py` | bornes ; montée/descente ; boucle B2 désactivable |
| T-026 | β-δ (optionnel, priorité haute) | T-024 | 20 §10 | `decision/discounting.py` | naïf ≠ sophistiqué sur un cas jouet documenté ; `beta=1` ⇒ exponentiel |
| T-027 | Poids variables et mode unitaire | T-010 | 20 §11 | `agents/allocation.py` | `VARIABLE_WEIGHTS` et `UNITARY` = paramètres de la même fonction |
| T-028 | Départ du jeune adulte (D13) | T-024 | 20 §12 | `agents/household.py`, `model/family_model.py` | `young_adult_can_leave=false` ⇒ aucun effet ; `true` ⇒ nouveau foyer d'une personne, transferts inter-ménages, identités préservées |
| T-029 | NTTA (optionnel) | T-012 | 20 §11 | `nta/ntta.py` | comptes temps séparés ; jamais mélangés aux NTA monétaires |
| T-030 | Non-régression V2 = V1 | T-024..T-028 | 90 §2.3 | `tests/regression/` | bascules off ⇒ empreinte V1 identique |
| T-031 | Patterns POM et cibles | T-018 | 40 §3, §4 | `analysis/patterns.py`, `population/sources.py` (synthetic), `data/processed/` | P1–P7 calculés ; `test_patterns_frozen` ; cibles synthétiques documentées |
| T-032 | Analyse de sensibilité | T-031 | 40 §5 | `analysis/sensitivity.py` | Morris sur le registre ; Sobol sur les survivants ; table `sensitivity_indices` ; figure barres triées |
| T-033 | E2, E3, E6, E-SA + porte V2 | T-030, T-032 | 50 (E2, E3, E6, E-SA), 90 §3.2 | `config/experiments/`, `analysis/figures.py` | **`make gate-v2` tout vert** ; rapports d'expériences, y compris résultats nuls |

### Version V3 — affective et population (Phases 7–10), par priorité décroissante

| ID | Titre | Dépend | Spec | Fichiers | Critères |
|---|---|---|---|---|---|
| T-040 | ODD-V3 dans le dépôt | G-V2 | odd/ODD_v3 | `odd/ODD_v3_affective_population.md` | relu et attesté |
| T-041 | Appraisal, émotions, stress (prio 1) | T-040 | 30 §1, §2.1–§2.2, §2.6–§2.7 | `cognition/appraisal.py`, `config/affect.yaml` | équations ; décroissances ; tests ; B3 désactivable |
| T-042 | Modulation → EffectiveCognitiveProfile (prio 1) | T-041 | 30 §2.3–§2.5 | `cognition/modulation.py` | stress 0 ⇒ profil de base ; formes linéaire/sigmoïde ; le moteur ne lit que le profil effectif (test d'import C4) |
| T-043 | Population de foyers (prio 2) | T-042 | 30 §3, §11 | `population/generator.py`, `config/population.yaml`, runner parallèle | 1 000 foyers × 240 pas dans le budget ; indépendance des foyers |
| T-044 | Données réelles : adaptateurs (prio 3) | T-043 | 40 §4 | `population/sources.py` (nta_profiles, ehcvm), `data/README.md` | repli `synthetic` avec avertissement si données absentes ; aucun fichier brut commité |
| T-045 | CalibrationEngine + expérience jumelle (prio 3) | T-044, T-032 | 40 §6–§8 | `analysis/calibration.py` | `CalibrationLeakError` testée ; la jumelle retrouve les paramètres connus dans la tolérance déclarée ; refus de calibrer une variable de traitement |
| T-046 | Sphères séparées (prio 4) | T-042 | 30 §5 | `agents/household.py`, `agents/allocation.py` | transitions avec hystérésis ; même fonction `allocate()` sur sous-budgets ; identités préservées |
| T-047 | Repère d'efficacité collective (prio 5) | T-043 | 30 §6 | `analysis/efficiency.py` | repère ex post uniquement (D7) ; distance testée sur cas jouet |
| T-048 | CPT sur 4 décisions (prio 6) | T-042 | 30 §7 | `decision/risk.py`, `config/risk.yaml` | λ=1 ⇒ neutre aux pertes ; valeurs T&K reproduites sur exemples publiés |
| T-049 | Rétroaction santé–stress (prio 7) | T-041 | 30 §8 | `health/health.py` | désactivable ; tests |
| T-050 | Dégradation cognitive contrôlée (prio 8) | T-043 | 30 §9 | runner E9 | plan v1/v2/v3 × N ; TOST |
| T-051 | Non-régression V3 = V2 | T-041..T-049 | 90 §2.3 | `tests/regression/` | bascules off ⇒ empreinte V2 |
| T-052 | E4, E5, E7, E8, E9, contrefactuels + porte V3 | T-045..T-051 | 50, 90 §3.3 | `config/experiments/` | **`make gate-v3`** ; E4 rapportée quel que soit le résultat |

**Ordre d'abandon si un jalon glisse** (feuille de route §22) : T-048/E5 → T-047/E8 → T-050/E9 → données EHCVM (T-044 restreint à `nta_profiles`) → V3 entière en prototype.

## Piste B — Plateforme (démarre après G-V1, en parallèle de V2/V3)

| ID | Titre | Dépend | Spec | Critères |
|---|---|---|---|---|
| T-060 | API : ossature, SimulationService, file de jobs, SQLite | G-V1 | 60 | `POST /simulations` renvoie 202 + `job_id` sans bloquer ; machine à états du job ; reprise au redémarrage |
| T-061 | API : endpoints de lecture via DuckDB | T-060 | 60 | contrats testés (httpx) ; pagination ; aucune logique de modèle ni calcul d'indicateur dans l'API |
| T-062 | Contrat OpenAPI → types TS | T-061 | 60, 70 | `web/src/api/types.ts` généré ; CI échoue si désynchronisé |
| T-070 | Frontend : ossature, tokens, navigation | T-062 | 70 | 6 sections routées ; tokens CSS ; thème clair ; état dans l'URL |
| T-071 | Bibliothèque de composants | T-070 | 70 §7 | chaque composant avec histoire/test ; export SVG/PNG des graphiques |
| T-072 | Dashboard | T-071 | 70 §6.A | critères d'acceptation de l'écran |
| T-073 | Scénarios (configurer, lancer, file) | T-071 | 70 §6.B | idem |
| T-074 | Foyers : liste et vue foyer | T-071 | 70 §6.C1–C2 | graphe des transferts ; bandeau des demandes |
| T-075 | Vue agent | T-074 | 70 §6.C3 | frise de décisions dépliable (alternatives + règle) |
| T-076 | Frise de simulation synchronisée | T-074 | 70 §6.D | curseur de pas partagé entre vues |
| T-077 | Analytique NTA | T-071 | 70 §6.E | profils par âge, observé en pointillé, flèches de Lee |
| T-078 | Comparaison de scénarios | T-071 | 70 §6.F | petits multiples à échelles partagées ; table des écarts |
| T-079 | Validation | T-071 | 70 §6.G | calibration/validation visuellement distinguées ; sensibilité ; critères |
| T-080 | Parcours E2E + démonstration hors ligne | T-072..T-079 | 70 §11 | Playwright vert ; démo sans réseau ; le moteur reste exécutable seul |
| T-081 | (Optionnel) Démonstrateur Solara | G-V1 | 70 §12 | alternative légère de soutenance, sans API |
