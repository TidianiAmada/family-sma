---
description: Implémenter un ticket du plan specs/95_IMPLEMENTATION_PLAN.md
argument-hint: T-xxx
---
Implémente le ticket $ARGUMENTS de `specs/95_IMPLEMENTATION_PLAN.md`.

1. Lis la ligne du ticket, puis chaque section de spec citée. Relis `CLAUDE.md` (règles dures).
2. Vérifie que les dépendances du ticket sont présentes et que `uv run pytest -q` est vert avant de commencer. Sinon, arrête-toi et dis lequel manque.
3. Vérifie que l'ODD de la version courante (`odd/`) décrit le sous-modèle concerné. S'il ne le décrit pas, arrête-toi : propose le paragraphe ODD manquant à l'auteur au lieu de coder.
4. Écris d'abord les tests correspondant aux critères d'acceptation, puis le code.
5. Exécute `uv run pytest -q && uv run lint-imports && uv run mypy src/`.
6. Mets à jour `docs/MATRICE_QUESTION_MODELE.md` si un composant est créé, et l'ODD si le code s'en écarte (même commit).
7. Rapporte : critères d'acceptation cochés un par un, fichiers modifiés, écarts ou détails tranchés, prochaine étape.

N'implémente rien qui dépasse le périmètre du ticket.
