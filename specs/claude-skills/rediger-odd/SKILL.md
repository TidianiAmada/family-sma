---
name: rediger-odd
description: Gabarits et règles de rédaction pour l'ODD (Grimm et al. 2020) et son extension ODD+D, appliqués à family_abm — sept sections, onze design concepts, bloc de décision individuelle, fiche de sous-modèle, style scientifique français, correspondance avec les chapitres du mémoire. À utiliser pour écrire ou mettre à jour odd/ODD_v*.md, une docstring de sous-modèle ou une section des chapitres 3 à 5.
---
# Rédiger l'ODD

## Structure obligatoire (ordre fixe)
1. **Purpose and patterns** — question, pour qui, patterns que le modèle doit reproduire (P1–P7 avec leur rôle calibration/validation/exploratoire).
2. **Entities, state variables and scales** — table par entité : variable, type, domaine, unité, version, statique/dynamique. Échelles : pas (mois), horizon, population.
3. **Process overview and scheduling** — les trois temps, dans l'ordre exact du code, avec qui lit/écrit quoi ; boucles B1–B3.
4. **Design concepts** — les onze, chacun en 2 à 6 phrases (voir ci-dessous).
5. **Initialization** — état à t₀, source de chaque valeur, part aléatoire.
6. **Input data** — données externes (NTA, EHCVM), ou « aucune » ; procédure de repli synthétique.
7. **Submodels** — une fiche par sous-modèle (gabarit ci-dessous).

## Les onze design concepts — question à laquelle chaque paragraphe répond
| Concept | Question |
|---|---|
| Basic principles | Quelles théories et hypothèses générales sous-tendent le modèle ? 【LIT】 |
| Emergence | Quels résultats émergent des comportements individuels, lesquels sont imposés ? |
| Adaptation | Quelles décisions les agents prennent-ils en réponse à leur état ? |
| Objectives | Quels buts les agents poursuivent-ils et comment mesurent-ils leur réussite (aspiration) ? |
| Learning | Les agents changent-ils leurs règles de décision avec l'expérience ? (aspiration, mémoire — pas d'apprentissage de règles) |
| Prediction | Comment les agents anticipent-ils (horizon, projection, β-δ) ? |
| Sensing | Que perçoivent-ils, avec quelle exactitude ? |
| Interaction | Qui interagit avec qui et comment (demandes/allocations, transferts) ? |
| Stochasticity | Quels processus sont aléatoires, avec quel flux RNG ? |
| Collectives | Le foyer comme collectif : comment se forme-t-il, que décide-t-il ? |
| Observation | Quelles sorties sont collectées (tables de 04) et comment ? |

## Bloc ODD+D — décision individuelle (pour le moteur de décision)
Sujets et objets de décision · rationalité sous-jacente (satisficing, Simon) · règle de décision explicite · adaptation (aspiration) · rôle des normes sociales (aucune modélisée — le dire) · dimension spatiale (aucune) · dimension temporelle (horizon, β-δ) · traitement de l'incertitude (attentes issues de la mémoire, CPT en V3).

## Fiche de sous-modèle
```
### 7.y Nom du sous-modèle
Rôle : (une phrase)
Moment : Temps 1|2|3, position dans le pas
Entrées : variables d'état et paramètres (nom de config, valeur par défaut, provenance)
Équations : (notation NTA / spec, numérotées)
Sorties : variables modifiées, écritures Ledger
Hypothèses : 【HYP】 … (forme fonctionnelle, choix non fondé empiriquement)
Justification : 【LIT】 référence (« à vérifier » si non confirmée) / 【RECO】 choix de conception
Code : module.fonction — Tests : fichier
```

## Règles de style
- Phrases déclaratives au présent ; « le modèle suppose », jamais « nous pensons ».
- Mêmes symboles que le manuel NTA et la spec ; aucun symbole non défini.
- Aucune affirmation d'originalité ; aucun résultat annoncé ; références non vérifiées marquées « à vérifier ».
- Les valeurs `PLACEHOLDER` sont dites telles : « valeur provisoire, à remplacer par … ».
- En-tête de chaque fichier : « Brouillon — à réviser par l'auteur ; devient Chap. X ».

## Correspondance avec le mémoire
Purpose → Ch. 1 · Entities/Scales → Ch. 3 §3.2 · Process overview → Ch. 3 §3.3 · Design concepts → Ch. 3 §3.1 · Initialization → Ch. 5 §5.3 · Input data → Ch. 4 §4.6 · Submodels → Ch. 4 (économiques) et Ch. 5 (cognitifs).
