---
name: implementer-sous-modele
description: Procédure pour implémenter ou modifier un sous-modèle de family_abm (besoins, revenu, allocation, décision, mémoire, appraisal…) de bout en bout — ODD, tests, code, invariants, configuration, traçabilité. À utiliser pour tout ticket de la piste A qui touche à src/family_abm/.
---
# Implémenter un sous-modèle

Suis les étapes dans l'ordre. Chaque étape a une sortie vérifiable ; ne passe pas à la suivante sans elle.

## 1. Cadrer (sortie : 5 lignes dans la réponse)
- Ticket, version (V1/V2/V3), spec et section exactes, sous-modèle ODD concerné (`odd/ODD_vX_*.md` §7.y).
- Entrées / sorties / variables d'état touchées (noms de `specs/02_DOMAIN_MODEL.md`).
- Paramètres utilisés (chemins de `specs/03_CONFIG_SCHEMAS.md`).
- Temps d'exécution dans le pas (1, 2 ou 3, `specs/01_ARCHITECTURE.md` §4).
- Écritures Ledger produites (catégories de 02 §8.3), le cas échéant.

## 2. Vérifier l'ODD (sortie : « ODD conforme » ou paragraphe proposé)
Si l'ODD ne décrit pas le sous-modèle avec ses équations, **arrête-toi** et propose le paragraphe manquant (persona `redacteur-odd`). On ne code pas un mécanisme qu'on ne sait pas écrire en prose.

## 3. Configuration (sortie : YAML + schéma Pydantic)
- Tout nombre → clé YAML avec bornes Pydantic et `provenance`.
- Valeur neutre documentée qui reproduit la version précédente (non-régression).
- Paramètre incertain → entrée dans `config/parameters_registry.yaml` (bornes, traitement).

## 4. Tests d'abord (sortie : tests rouges pour la bonne raison)
- Un test par critère d'acceptation du ticket.
- Propriétés hypothesis si la règle est universelle (bornes, conservation, monotonie).
- Cas limites : zéro, budget nul, horizon 0, `max_alternatives = 1`, personne sans la capacité, population de 1.
- Si le sous-modèle écrit au Ledger : invariants concernés (skill `ecrire-invariant-nta`).

## 5. Code (sortie : tests verts)
- Fonctions pures dès que possible (allocation, projection, appraisal, modulation) ; les états restent passifs.
- Aléa uniquement via `rng["<flux>"]` (flux de `01 §7`) ; jamais `random`, `np.random` global ni `model.random`.
- Mouvement de valeur uniquement via `ledger.post(...)`.
- Docstring française format NumPy avec unités et `Référence : ODD-Vx §7.y`.
- Pas de branchement sur le rôle ; uniquement sur capacités et paramètres.

## 6. Intégration (sortie : commandes vertes)
```bash
uv run pytest -q && uv run lint-imports && uv run mypy src/ && uv run ruff check .
uv run python -m family_abm run --scenario baseline --seed 42   # run complet sans InvariantViolation
```
Si une empreinte golden change : c'est voulu ? → commit `GOLDEN:` justifié ; sinon c'est une régression.

## 7. Traçabilité (sortie : diff de documentation dans le même commit)
- ODD mis à jour si le code a précisé quoi que ce soit.
- `docs/MATRICE_QUESTION_MODELE.md` si un composant apparaît.
- `docs/DECISIONS.md` si un détail a été tranché (date, contexte, choix, alternative écartée).

## 8. Revue (sortie : rapports)
Demande `architecte-gardien` puis `relecteur-code` ; traite les ⛔ et ⚠️ avant de clore.
