---
name: revue-qualite
description: Grille de revue de qualité pour le code (Python moteur, FastAPI, React/TS) et la documentation de family_abm, avec format de rapport normalisé. À utiliser en fin de ticket, avant un commit significatif, ou quand on demande une relecture de code ou de documentation.
---
# Revue de qualité

Examine `git diff main...HEAD` (ou les fichiers indiqués). Pour chaque ligne de la grille : ✅, ⚠️ ou ⛔ avec fichier:ligne.

## A. Exactitude et modèle
- [ ] Le comportement correspond à la section de spec citée (équations, ordre, cas limites).
- [ ] Les valeurs neutres reproduisent la version précédente (non-régression).
- [ ] Aucun mouvement de valeur hors `Ledger` ; aucun `float` dans le Ledger.
- [ ] Aucun aléa hors `RngStreams` ; flux nommé correct.
- [ ] Aucun branchement sur le rôle ; aucune nouvelle hiérarchie polymorphe.

## B. Code Python
- [ ] `mypy --strict` sans `Any` implicite ; `type: ignore` justifiés en commentaire.
- [ ] Fonctions ≤ ~40 lignes, une responsabilité ; noms du domaine (`specs/02`).
- [ ] Aucun nombre magique (paramètre de config ou constante nommée justifiée).
- [ ] Exceptions spécifiques avec contexte ; pas d'`except` large ; pas d'échec silencieux.
- [ ] Objets-valeurs `frozen=True, slots=True` ; états sans méthode métier.
- [ ] Pas de pandas ni d'allocation coûteuse dans la boucle de pas ; complexité par pas raisonnable.
- [ ] Pas de code mort, de `print`, de TODO sans ticket.

## C. Tests
- [ ] Chaque critère d'acceptation a son test ; cas limites couverts.
- [ ] Propriétés hypothesis là où la règle est universelle.
- [ ] Invariants nouveaux : test sain + test d'injection.
- [ ] Aucun seuil, ε, budget ou empreinte modifié pour faire passer un test.

## D. Documentation
- [ ] Docstrings françaises (NumPy) : rôle, paramètres avec unités, retours, exceptions, `Référence : ODD-Vx §7.y`.
- [ ] Commentaires = pourquoi, pas quoi.
- [ ] ODD, matrice, `DECISIONS.md` mis à jour dans le même commit si nécessaire.
- [ ] Aucune affirmation d'originalité ni de résultat non exécuté ; références non vérifiées marquées.

## E. Plateforme (si `family_abm_api/` ou `web/` touchés)
- [ ] Aucune logique de modèle, aucun calcul d'indicateur (tout vient de `analysis/`).
- [ ] Types TS générés depuis OpenAPI, non édités.
- [ ] États chargement / vide / erreur / run illustratif traités ; accessibilité (clavier, contraste AA, texte alternatif des graphiques).
- [ ] Couleurs = jetons (`--member-*`, `--signal-*`), aucune couleur en dur.

## Format du rapport
```
REVUE — <ticket> — <date>
Verdict : PRÊT | PRÊT APRÈS CORRECTIONS | À REPRENDRE
| Gravité | Section | Fichier:ligne | Constat | Correction |
Points forts (≤ 3) :
```
