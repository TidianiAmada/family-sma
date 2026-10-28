---
name: concevoir-experience
description: Gabarits pour concevoir, configurer, exécuter et rapporter une expérience de simulation de family_abm (E1–E9, E-SA, scénarios contrefactuels) — fiche de conception, YAML config/experiments, règles statistiques, structure du rapport de résultats sans prédiction. À utiliser pour créer ou modifier une expérience, lancer une campagne, ou rédiger un rapport de résultats.
---
# Concevoir et rapporter une expérience

## 1. Fiche de conception (avant toute exécution)
```
ID / titre :
Question (ligne de docs/MATRICE_QUESTION_MODELE.md) :
Hypothèse 【HYP】 : (formulée pour pouvoir être réfutée)
Version requise :
Facteurs manipulés : chemin de config → niveaux
Contrôles : ce qui est fixé et pourquoi
Réplications : n, seeds communes entre niveaux (justifier n)
Métriques : noms exacts du catalogue (specs/04_DATA_MODEL.md §3)
Analyse : test, taille d'effet, intervalle, correction multiple, TOST si équivalence
Figures : noms de fichiers, type (ligne/barre/aire), échelles partagées
Limites connues : dépendances aux hypothèses 【HYP】
Résultat attendu : AUCUN (ne pas prédire)
```
Contrôle : aucun facteur n'est un paramètre calibré ; aucun pattern de validation n'est utilisé pour régler quoi que ce soit.

## 2. Configuration
`config/experiments/<ID>.yaml` selon `specs/50_SPEC_EXPERIMENTS.md` §1 (base_scenario, factors, fixed, replications, metrics, outputs, requires_version). Lancer : `uv run python -m family_abm experiment <ID>`.

## 3. Règles statistiques
- Comparer des niveaux à **seeds appariées** : différences par seed, puis moyenne et IC 95 % bootstrap (2 000 tirages, seed d'analyse fixée).
- Rapporter la **taille d'effet** (différence moyenne et d standardisé) avant toute p-valeur.
- Plusieurs métriques → correction de Holm.
- « Pas de différence » ⇒ test d'équivalence (TOST) avec marge déclarée **avant** exécution ; sinon écrire « différence non détectée », jamais « pas d'effet ».
- Toujours n, moyenne, écart-type, quantiles 5–95 %.

## 4. Rapport de résultats (`experiments/reports/<ID>.md`)
```
# <ID> — <titre>
Commit / ConfigHash / date / n runs / runs illustratifs : oui|non
## Question et hypothèse (copiées de la fiche, non modifiées)
## Protocole (renvoi au YAML)
## Résultats (faits, chiffres, figures — sans interprétation)
## Interprétation (chaque phrase avec sa condition de validité)
## Ce que l'expérience ne montre pas
## Écarts au protocole (s'il y en a)
```
Un résultat nul ou contraire à l'hypothèse se rapporte avec le même soin. La section Résultats ne contient aucun adjectif évaluatif (« remarquable », « clair », « fort »).
