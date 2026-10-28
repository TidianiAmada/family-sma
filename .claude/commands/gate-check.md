---
description: Vérifier une porte de passage (v1, v2, v3)
argument-hint: v1|v2|v3
---
Exécute `make gate-$ARGUMENTS` (ou `uv run python scripts/gate.py $ARGUMENTS`) et rapporte le résultat case par case selon `specs/90_TEST_STRATEGY_AND_GATES.md` §3.

Pour chaque case rouge : cause probable, fichier concerné, ticket de `specs/95_IMPLEMENTATION_PLAN.md` à reprendre. Ne modifie aucun seuil, ε, budget ou pattern pour faire passer une case. Ne coche jamais une attestation manuelle à la place de l'auteur.
