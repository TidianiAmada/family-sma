---
name: fiche-conception
description: Gabarit et critères pour rédiger une fiche de conception justifiant un choix architectural ou de modélisation de family_abm (docs/FICHES_CONCEPTION.md). À utiliser dès qu'un choix non trivial est tranché — nouveau mécanisme, alternative écartée, hypothèse de forme fonctionnelle, convention de mesure.
---
# Fiche de conception

## Gabarit
```
## Fiche N — <choix en une ligne>
- CHOIX :
- QUESTION : à quelle question de conception ce choix répond-il ?
- ALTERNATIVES : au moins deux, dont l'option « ne rien modéliser »
- LITTÉRATURE : références (statut « à vérifier » si non confirmée)
- JUSTIFICATION : arguments, le décisif en dernier
- HYPOTHÈSE IMPLICITE : 【HYP】 ce que le choix suppose sans le démontrer
- IMPLÉMENTATION : module.fonction, paramètres
- TEST : ce qui prouve que le code fait ce que la fiche dit
- VALIDATION : expérience ou niveau V-x qui éprouve le choix
- LIMITES : ce que le choix empêche d'étudier
- CHAPITRE : où la fiche devient du texte
- STATUT : 【LIT】 / 【RECO】 / 【HYP】 / 【SPEC】
```

## Critères de qualité
- Les alternatives sont réelles et décrites honnêtement, pas des hommes de paille.
- La justification n'invoque pas la facilité d'implémentation comme argument principal.
- L'hypothèse implicite est formulée de façon à pouvoir être contredite par une expérience.
- Chaque fiche est reliée à une ligne de `docs/MATRICE_QUESTION_MODELE.md`.
- Une fiche modifiée garde l'ancienne version en note datée (on ne réécrit pas l'histoire d'une décision).
