---
description: Contrôler le dépôt contre les règles RV-01 à RV-20
argument-hint: "[tout | code | doc]"
---
Contrôle le dépôt contre `docs/REGLES_VALIDATION.md` (portée : $ARGUMENTS, défaut « tout »).

1. Exécute les vérifications automatiques : `uv run lint-imports`, `uv run pytest tests/architecture tests/regression -q`, `uv run pytest tests/unit/test_patterns_frozen.py -q`.
2. Recherche textuelle dans `odd/`, `docs/`, `experiments/reports/` et les docstrings :
   - RV-03 : « premier », « inédit », « personne n'a », « jamais été », « à notre connaissance » (ce dernier n'est admis que si `docs/PROTOCOLE_RECHERCHE.md` existe) ;
   - RV-09 : « devrait montrer », « on s'attend à », « résultat attendu » hors fiches de conception d'expérience ;
   - RV-14 : « hors-échantillon », « out-of-sample » ;
   - RV-17 : références citées absentes de `docs/BIBLIOGRAPHIE.md` ou au statut « à vérifier ».
3. Délègue le jugement : `architecte-gardien` (RV-01, 02, 05, 18, 19), `methodologiste-validation` (RV-07 à 09, 11 à 16, 20), `bibliothecaire` (RV-03, 17).

Rends un tableau `RV · statut ✅/⚠️/⛔ · preuve (commande ou fichier:ligne) · action`. Ne corrige rien sans accord.
