# 00 — Décisions d'architecture et de modélisation

> **Statut :** référence normative. Toute spécification de ce dossier en découle.
> Une décision n'est rouverte que si une expérience la contredit ; dans ce cas, on la modifie ICI, dans le même commit que le code et l'ODD.
>
> Légende de provenance (reprise de la feuille de route) : 【DOC】 proposition de sujet · 【LIT】 littérature · 【RECO】 recommandation de conception · 【HYP】 hypothèse à tester · 【SPEC】 tranché dans ce dossier de spécifications.

---

## 1. Décisions fermées (D1–D13)

| # | Décision | Conséquence directe pour l'implémentation |
|---|---|---|
| D1 | **Un seul `PersonAgent` générique** ; l'hétérogénéité vient d'un `CognitiveProfile` chargé depuis `config/cognitive_profiles.yaml` | Interdit : `BabyAgent`, `ParentAgent`, `if role == "baby"` dans la logique. Les capacités (`capabilities`) et les paramètres décident. |
| D2 | **Les NTA sont une couche de mesure ex post**, en lecture seule | `nta/` ne lit que le `Ledger` et les états ; aucun module de `agents/`, `decision/`, `economy/` n'importe `nta/`. Vérifié par un test d'architecture (import-linter). |
| D3 | **Satisficing à seuil d'aspiration adaptatif** (Simon 1955), non compensatoire | `decision/satisficing.py`. Aucune fonction d'utilité scalaire agrégeant des besoins hétérogènes. |
| D4 | **Pas de HTN, pas de GOAP** | Bibliothèque de plans BDI (V2) dans `decision/plans.py`. |
| D5 | ACT-R/SOAR/CLARION en état de l'art ; **emprunt unique : activation décroissante de la mémoire** | `cognition/memory.py` implémente l'activation de niveau de base `A = ln Σ (t − tⱼ)^(−d)`. |
| D6 | **L'affect ne produit pas d'utilité** : il module les paramètres du processus de décision | `cognition/modulation.py` produit un `EffectiveCognitiveProfile` ; le moteur de décision ne lit jamais une émotion directement. |
| D7 | Modèles collectifs du ménage (Chiappori) = **cadre théorique et repère**, pas mécanisme | Le repère d'efficacité (E8) est calculé ex post dans `analysis/efficiency.py`. |
| D8 | **Python 3.12 + Mesa 3** pour tout le moteur | Agents.jl = perspective (Chap. 9). |
| D9 | **ODD construit en parallèle du code**, version par version | `odd/ODD_v{0..3}_*.md`. Règle dure : aucun sous-modèle codé avant d'être décrit dans l'ODD. |
| D10 | **Validation par Pattern-Oriented Modeling**, séparation stricte calibration / validation | `config/patterns.yaml` avec rôle figé + empreinte (hash) ; le `CalibrationEngine` refuse un pattern de rôle `validation` dans sa fonction de perte. |
| D11 | **Pas de temps mensuel** | `step` = 1 mois ; l'âge avance d'1 an tous les 12 pas. |
| D12 | **Horizon simulé variable** : 10 ans / 20 ans (défaut) / cycle de vie | `simulation.horizon_months` ∈ {120, 240, N}. Défaut 240. La retraite n'est pas couverte à 20 ans — à assumer. |
| D13 | **Départ du jeune adulte : paramétrable** (oui / non) | `household_rules.young_adult_can_leave: bool` (défaut `false`). Si `true`, voir V2 §« Départ du foyer » : l'agent quitte le foyer et devient un foyer d'une personne (pas de nouveau type). |

## 2. Questions ouvertes de la feuille de route — tranchées pour l'implémentation 【SPEC】

| # | Question | Choix retenu | Paramètre / bascule |
|---|---|---|---|
| Q5 | Démographie | **Cohorte fixe, vieillissement seul.** Pas de naissances ni de décès. | `demography.mode: fixed_cohort` (seule valeur implémentée ; l'enum existe pour la perspective) |
| Q6 | Source de calibration | **Trois sources interchangeables derrière une même interface** : `synthetic` (défaut, toujours disponible), `nta_profiles` (profils NTA Sénégal, CREFAT), `ehcvm` (microdonnées). | `data.source: synthetic \| nta_profiles \| ehcvm`. Le code n'échoue jamais faute de données réelles : repli sur `synthetic` avec avertissement explicite dans les métadonnées du run. |
| Q7 | Question de recherche n°5 | **Option C** : objectif méthodologique du chapitre Validation. | Aucun impact code ; impacte `40_SPEC_VALIDATION_CALIBRATION.md`. |
| Q8 | Application web | **FastAPI + React (TypeScript, Vite)** pour la plateforme complète. **Solara (visualisation native de Mesa 3)** autorisé comme démonstrateur léger de soutenance, sans API. | Voir `60_SPEC_API.md`, `70_SPEC_UX_UI.md`. |
| Q9 | Unité monétaire | **FCFA** mensuels (entiers en centimes interdits : FCFA n'a pas de subdivision usuelle). Montants stockés en `Decimal` côté `Ledger`, convertis en `float64` pour l'analyse. | `economic_params.currency: XOF`. Si `data.source = synthetic`, les valeurs par défaut sont des **placeholders** marqués `provenance: PLACEHOLDER`. |

### Pourquoi `Decimal` dans le Ledger
La conservation des flux est un critère binaire (V-2). Les flottants accumulent des erreurs d'arrondi qui produisent des « fuites » fantômes de l'ordre de 1e-9 × montant × pas. Le `Ledger` stocke donc des `Decimal` quantifiés à 0,01 FCFA ; ε de bouclage = 0,01 FCFA par compte et par pas. Les tables d'analyse (Parquet) utilisent `float64`.

## 3. Décisions logicielles complémentaires 【SPEC】

| # | Décision | Justification |
|---|---|---|
| S1 | **Un seul point polymorphe : `DecisionEngine`**. Tout le reste (allocation du foyer, profils, plans, scénarios) est de la donnée ou une fonction paramétrée. | Traduction logicielle de D1. L'allocation du foyer (unitaire / poids fixes / poids variables / sphères séparées) est **une seule fonction paramétrée**, pas une hiérarchie de stratégies. |
| S2 | **`Ledger` en double entrée, source unique de vérité** | Les identités NTA deviennent des agrégations ; les invariants deviennent triviaux. |
| S3 | **Configuration YAML validée par Pydantic v2** (modèles `frozen=True`) | Reproductibilité, bornes vérifiées au chargement, analyse de sensibilité sans toucher au code. |
| S4 | **Toute aléa passe par `numpy.random.Generator`** issu d'un `SeedSequence` racine ; un sous-flux nommé par usage (`rng.income_shocks`, `rng.health`, …) | Déterminisme par seed **et** stabilité des flux quand on ajoute un usage aléatoire (ajouter un tirage dans la santé ne décale pas les chocs de revenu). |
| S5 | **Sorties Parquet**, catalogue **DuckDB** ; métadonnées des runs en **SQLite** (API uniquement) | Données analytiques, pas transactionnelles. |
| S6 | **Le moteur reste exécutable sans API, sans frontend, sans base** (`python -m family_abm run …`) | Règle de survie du mémoire : le jury doit pouvoir reproduire. |
| S7 | **Le service de simulation (API) ne contient aucune logique de modélisation** ; React ne calcule aucun indicateur | Un seul endroit où corriger un bug ; le mémoire décrit le modèle qui tourne. |
| S8 | **Bascules de version par configuration** : `model.version: v1 \| v2 \| v3` + drapeaux fins (`cognition.bdi.enabled`, `affect.enabled`, …) | Permet E2 (V1 vs V2), E4 (appraisal on/off), E9 (dégradation contrôlée) sans brancher le code. |
| S9 | **Gestion de paquets : `uv`** ; lint `ruff` ; typage `mypy --strict` sur `src/` ; tests `pytest` + `hypothesis` | Outillage standard, rapide. |
| S10 | **Frontend : React 18 + TypeScript + Vite, TanStack Query, Zustand, Observable Plot (+ D3 pour graphes sur mesure), Tailwind CSS** | Observable Plot gère nativement petits multiples à échelles partagées et export SVG — exigences UX §17. |

## 4. Ordre de construction et portes (rappel normatif)

```
V1 (baseline économique) ──[porte V1]──► V2 (cognitive) ──[porte V2]──► V3 (affective + population)
                                                          │
     └──[porte V1]──► API (FastAPI) ──► UI (React)   (en parallèle de V2/V3 ; les vues s'enrichissent avec les colonnes produites)
```

- Une case non cochée d'une porte **bloque** la suite (feuille de route §24).
- La plateforme (piste B) dépend uniquement des tables de sortie du moteur (`04_DATA_MODEL.md`) : elle peut démarrer dès que la porte V1 est verte et progresser en parallèle de V2/V3. Elle ne modifie jamais le moteur (S6, S7).
