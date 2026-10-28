---
description: Bilan de fin de session de travail (code + documentation)
---
Produis le bilan de la session et ajoute-le en tête de `docs/JOURNAL.md` (crée le fichier s'il n'existe pas) :

```
## <date> — <tickets travaillés>
Fait : (tickets clos, critères d'acceptation cochés)
Tests : (commande lancée, résultat, couverture des modules touchés)
Documentation : (sections d'ODD, fiches, matrice, DECISIONS mises à jour — ou « aucune », avec raison)
Décisions tranchées : (renvoi à docs/DECISIONS.md)
Écarts code ↔ ODD ouverts : (liste ou « aucun » — vérifie avec /odd-sync si du code a changé)
Règles en alerte : (RV-xx en ⚠️/⛔ détectées pendant la session)
Prochaine étape : (ticket suivant et premier geste concret)
```

Base-toi sur `git log` et `git diff` de la session, pas sur la mémoire de la conversation. Sois factuel : aucune estimation de « pourcentage d'avancement ».
