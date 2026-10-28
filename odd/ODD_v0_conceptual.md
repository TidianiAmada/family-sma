# ODD-V0 — Modèle conceptuel « Famille multi-agents × NTA »

> **Brouillon généré — à réviser et s'approprier par l'auteur ; devient Chap. 3–5.**
> Protocole : ODD (Grimm et al. 2020) + bloc ODD+D « Individual decision-making » (Müller et al. 2013).
> Version : V0 (Phase 2, avant tout code). Couvre la conception d'ensemble V1→V3 ; les sous-modèles ne sont ici qu'annoncés.

---

## 1. Purpose and patterns

**Objectif.** Le modèle sert à (i) tester si une architecture d'agent **unique**, paramétrée par un profil cognitif, peut représenter des membres aussi hétérogènes qu'un bébé et un parent ; (ii) mesurer, avec la comptabilité des National Transfer Accounts (NTA), les conséquences économiques des décisions d'un foyer (déficit du cycle de vie, transferts intra-familiaux, dette) ; (iii) étudier la rétroaction entre contrainte économique, état affectif et capacité de décision (boucle B3) ; (iv) examiner ce qu'il faut conserver de la cognition individuelle pour reproduire des profils NTA agrégés sur une population de foyers.

Le modèle n'est **pas** prédictif. Il est explicatif et exploratoire : il sert à comparer des mécanismes et des scénarios contrefactuels (perte d'emploi, maladie, allocation familiale, gratuité des soins, choc économique).

**Patterns** (Pattern-Oriented Modeling, Grimm et al. 2005). Affectation **figée à ce stade** (`config/patterns.yaml`), avant toute calibration :

| ID | Pattern | Niveau | Rôle |
|---|---|---|---|
| P1 | Signature du LCD par âge (positif aux âges jeunes, négatif aux âges actifs) | population | calibration |
| P2 | Profil du revenu du travail par âge | population | calibration |
| P3 | Profil de consommation par âge | population | calibration |
| P4 | Orientation et volume des transferts (des âges actifs vers les âges dépendants) | population | validation |
| P5 | Distribution du ratio dette/revenu entre foyers | population | validation |
| P6 | Distribution du reste-à-vivre / taux de pauvreté | population | validation |
| P7 | Trajectoires intergénérationnelles (gradient éducation × revenu) | population | exploratoire |

Au niveau d'un foyer unique (V1–V2), seuls les signes de P1 par membre sont vérifiables ; la forme des profils exige une population (V3).

## 2. Entities, state variables and scales

**Entités.**

| Entité | Nombre | Rôle |
|---|---|---|
| `PersonAgent` | 6 par foyer de référence | membre ; une seule classe, hétérogénéité par `CognitiveProfile` |
| `HouseholdAgent` | 1 (V1–V2) ; ~1 000 (V3) | budget commun, allocation sous contrainte, dette collective |
| Environnement | 1 | prix, marché du travail, État (impôts, transferts, consommation publique), banque, scénarios |
| `Ledger` | 1 | journal en double entrée de tout mouvement de valeur (instrument de mesure, pas un agent) |
| Couche NTA | 1 | observateur ex post, lecture seule |

**Variables d'état (synthèse ; liste exhaustive dans ODD-V1 et suivants).**

- Personne : âge, profil, capacités ; état économique (emploi, salaire, offre de travail, portefeuille) ; état physique (santé, maladie, capacité de travail) ; besoins (6 niveaux) ; aspirations ; [V2] croyances, désirs, intention, mémoire ; [V3] émotions, stress, humeur.
- Foyer : membres, pot commun, épargne, dette, plafond de crédit, poids d'allocation, parts de propriété ω, chef de ménage (convention ONU), régime de coordination [V3].
- Environnement : indice des prix, indice des salaires, paramètres de chocs, politiques publiques actives.

**Échelles.** Temps discret, **pas mensuel** (D11) ; horizon par défaut **240 mois** (D12 ; variantes 120 mois et cycle de vie). Pas d'espace explicite. Unité monétaire : **FCFA** (Q9). Démographie : **cohorte fixe** (Q5) — vieillissement sans naissance ni décès ; à 20 ans d'horizon, le bébé devient jeune adulte et les enfants changent de position NTA, la retraite n'est pas atteinte (limite assumée).

## 3. Process overview and scheduling

Chaque pas mensuel comporte une phase exogène et **trois temps** (correction n°4 de l'audit) :

0. **Environnement** : horloge, chocs exogènes du scénario.
1. **Temps 1 — perception et demande** (chaque personne, ordre aléatoire sans effet) : remise à zéro des dépenses du pas, santé, perception ; [V2] croyances et désirs révisés à partir de la mémoire ; [V3] appraisal → affect → profil cognitif effectif ; [V2] délibération (intentions) ; [V3] décisions binaires sous risque ; le moteur de décision produit des **demandes priorisées** et une trace de décision.
2. **Temps 2 — arbitrage du foyer** : versement des revenus du travail, impôts ; transferts publics ; intérêts ; [V3] test de régime ; mise en commun ; engagements (logement, échéance de dette) ; **allocation sous contrainte budgétaire** selon une règle paramétrée ; financement (épargne, emprunt) ; notification.
3. **Temps 3 — action et comptabilité** : consommation, soins, scolarité, épargne dans la limite des allocations, complément depuis le portefeuille personnel ; consommation publique en nature ; lissage des niveaux de besoins ; [V2] évaluation des résultats (mémoire, aspiration, intention) ; **couche NTA** calculée depuis le Ledger ; **invariants** vérifiés (échec dur) ; observation ; puis vieillissement.

Mises à jour : synchrones au sein d'un temps (demandes collectées puis arbitrées simultanément). Population (V3) : foyers indépendants, traités successivement ou en parallèle sans effet.

**Boucles de rétroaction nommées :** B1 économique (V1), B2 cognitive (V2), B3 affective (V3).

## 4. Design concepts

1. **Basic principles.** Rationalité limitée (Simon 1955) : les agents « satisfont » plutôt qu'ils n'optimisent, avec un seuil d'aspiration ; continuum réactif → délibératif obtenu par deux paramètres continus (`max_alternatives`, `planning_horizon`) plutôt que par des types d'agents. Raisonnement pratique BDI dégradé (Bratman ; Rao & Georgeff) [V2]. Appraisal (Lazarus ; EMA, Marsella & Gratch 2009) et charge cognitive de la rareté (Mani et al. 2013) [V3] : l'affect **module les paramètres** du processus de décision, il ne produit pas d'utilité (D6). Comptabilité NTA (UN 2013) comme instrument de mesure, non comme théorie du transfert (D2). Modèles de ménage collectifs (Chiappori) comme repère théorique, non comme mécanisme (D7).
2. **Emergence.** Émergent : trajectoires de dette et d'épargne du foyer ; volumes et orientation des transferts intra-familiaux ; signature du LCD par âge ; [V3] enfermement endogène éventuel après un choc ; distributions entre foyers (dette/revenu, pauvreté, Gini). Imposé : identités comptables, prix, probabilités de chocs, ordre des paliers d'allocation.
3. **Adaptation.** V1 : aucune adaptation hors rationnement passif (le taux d'allocation passé et l'enveloppe attendue orientent le choix). V2 : seuils d'aspiration adaptatifs, révision d'intentions, replanification sur échec. V3 : modulation des paramètres cognitifs par le stress et les émotions ; bascule du foyer en régime « sphères séparées ».
4. **Objectives.** Pas de fonction objectif scalaire. Critère d'acceptabilité non compensatoire : chaque besoin attendu doit atteindre son seuil d'aspiration sur l'horizon projeté, dans l'ordre de priorité du profil.
5. **Learning.** Aucun apprentissage au sens strict (pas de modification des règles). [V2] L'adaptation des aspirations et le rappel mémoriel modifient les entrées des règles, pas les règles. L'apprentissage par renforcement est une perspective (Chap. 9).
6. **Prediction.** Projection explicite des niveaux de besoin sur `planning_horizon` mois, sous hypothèse de taux d'allocation attendu (V1 : dernier taux observé ; V2 : moyenne pondérée par l'activation mémorielle) ; [V2] actualisation exponentielle ou quasi-hyperbolique β-δ (naïve / sophistiquée).
7. **Sensing.** Chaque personne perçoit ses propres états, ses allocations passées, le solde de l'épargne du foyer et son enveloppe attendue ; elle ne perçoit pas les demandes des autres membres. Le foyer perçoit toutes les demandes et tous les soldes. Perception bornée par `max_alternatives` (nombre d'alternatives examinées).
8. **Interaction.** Indirecte et médiée par le foyer : demandes → allocation (compétition pour un budget commun) ; mise en commun des revenus ; [V3] contagion affective éventuelle via le stress parental et la rupture de coordination. Pas d'interaction entre foyers (perspective).
9. **Stochasticity.** Chocs d'emploi, revenu informel, épisodes de santé et leur gravité, raccourci d'impulsivité, ordre de perception (sans effet). Tous les tirages proviennent de sous-flux nommés d'un générateur seedé ; même seed ⇒ même trajectoire.
10. **Collectives.** Le foyer est un collectif explicite (un agent) ; [V3] régime de coordination du foyer (normal / sphères séparées).
11. **Observation.** Tables Parquet par pas (personnes, foyers, Ledger, demandes, décisions, événements, NTA) ; indicateurs du tableau de bord ; profils par âge ; patterns P1–P7 ; agrégation sur réplications avec dispersion.

### ODD+D — Individual decision-making (moteur de décision)

| Question ODD+D | Réponse |
|---|---|
| Sujets et objets de décision ? | Les personnes décident de leurs **demandes** (montants par besoin, épargne, recours aux soins) et, en V2, de leur offre de travail et de leurs plans ; le foyer décide de l'**allocation**. [V3] Les parents décident de quatre choix binaires sous risque. |
| Niveaux de décision ? | Individu (Temps 1, Temps 3) et foyer (Temps 2). |
| Rationalité de base ? | Rationalité limitée, satisficing à seuil d'aspiration, règles non compensatoires (lexicographiques). |
| Comment les agents décident-ils ? | Génération d'alternatives selon les capacités, ordonnées par saillance (habitude, plans en V2), tronquées à `max_alternatives` ; projection sur l'horizon ; choix de la première alternative acceptable ; repli lexicographique sinon. |
| Adaptation des décisions ? | V2 : seuils d'aspiration et intentions ; V3 : modulation par l'affect. |
| Normes sociales / valeurs ? | Implicites dans les poids d'allocation, les parts de propriété ω, la règle de mise en commun et l'ordre des paliers ; [V3] régime des sphères séparées (normes de rôle). |
| Aspects spatiaux ? | Aucun. |
| Aspects temporels ? | Horizon de planification, persistance des besoins, actualisation [V2], persistance des intentions [V2]. |
| Incertitude ? | Taux d'allocation et revenus attendus incertains (attentes adaptatives) ; [V3] traitement explicite du risque (CPT) sur quatre décisions. |

## 5. Initialization (esquisse)

Foyer de référence : père 45 ans (salarié formel), mère 40 ans (informelle), jeune adulte 20 ans (étudiant), adolescent 15 ans, enfant 9 ans, bébé 1 an ; actifs initiaux (pot, épargne, dette) issus de la configuration. Besoins initialement satisfaits sauf la sécurité financière. [V3] Population synthétique générée à partir de gabarits et de distributions (source `synthetic`, `nta_profiles` ou `ehcvm`). Toute valeur non tirée de données est marquée `PLACEHOLDER` et le run est qualifié d'**illustratif**.

## 6. Input data

Aucune série temporelle exogène obligatoire. Les scénarios fournissent des événements datés. Données d'entrée envisagées (Q6) : profils NTA Sénégal (CREFAT) pour le paramétrage direct des profils de consommation et de revenu par âge ; EHCVM 2018-19 / 2021-22 (ANSD, Banque mondiale) pour la population synthétique et les probabilités de transition.

## 7. Submodels (annoncés)

| Sous-modèle | Version | Intention |
|---|---|---|
| Vieillissement et transitions de profil | V1 | le profil cognitif suit l'âge (donnée, pas code) |
| Travail, emploi, chocs de revenu, impôts | V1 | revenu du travail Yl et sa volatilité |
| Besoins à seuils | V1 | moteur de l'autonomie de l'agent |
| Santé et scolarité | V1 | chocs et investissement en capital humain |
| Moteur de décision satisficing | V1 (→V3) | un seul mécanisme paramétré, réactif → délibératif |
| Allocation du foyer | V1 (→V3) | une seule fonction paramétrée (poids fixes, unitaire, poids variables, sphères séparées) |
| Crédit, dette, épargne | V1 | désépargne et endettement |
| Transferts publics et consommation publique | V1 | Cg, scénarios de politique |
| Ledger et couche NTA (mesure, attribution, imputation ONU, invariants) | V1 | comptabilité vérifiable ; écart comportemental vs imputé |
| Mémoire, croyances, désirs, intentions, plans | V2 | délibération et persistance |
| Aspiration adaptative, actualisation β-δ | V2 | boucle B2 ; présent-biais |
| Appraisal, émotions, stress, modulation | V3 | boucle B3 |
| Décisions sous risque (CPT) | V3 | aversion aux pertes |
| Régime « sphères séparées » | V3 | rupture de coordination |
| Population de foyers, calibration, repère d'efficacité | V3 | validation P1–P6, E7–E9 |
