# ODD-V2 — Modèle cognitif de foyer multi-agents (Famille × NTA)

> **Brouillon généré — à réviser et s'approprier par l'auteur.**
> Protocole : ODD (Grimm et al. 2020), complété du bloc ODD+D (Müller et al. 2013) pour la prise de décision.
> Version du modèle : **V2** (`model.version: v2`). Ce document décrit le modèle V2 de façon autoportante ; les sous-modèles économiques **inchangés** depuis la V1 sont cités par renvoi explicite à `ODD_v1_economic.md` (section 7, sous-modèle nommé), sans être recopiés.
> Correspondance mémoire : §1 → Chap. 1 ; §2–§4 → Chap. 3 ; §7.B → Chap. 5 (section cognitive) ; §1.2 → Chap. 6.
> Règle de cohérence : ce document est modifié **dans le même commit** que le code qu'il décrit.

---

## 1. Purpose and patterns

### 1.1 Objectif

Le modèle simule, au pas mensuel, un foyer de six personnes (père, mère, jeune adulte, adolescent, enfant, bébé) représentées par **un seul type d'agent générique** dont l'hétérogénéité provient d'un profil cognitif paramétré. Il mesure les conséquences économiques de leurs décisions par les identités des National Transfer Accounts (NTA), appliquées ex post comme couche de mesure.

L'objectif propre à la V2 est d'**établir si, et de combien, une architecture cognitive (croyances, désirs, intentions persistantes, mémoire, aspirations adaptatives) modifie les trajectoires économiques** du foyer par rapport au baseline économique V1, à paramètres économiques et graine aléatoire identiques.

Questions servies (matrice §18 de la feuille de route) :
- La persistance des intentions change-t-elle les trajectoires économiques ? (E2)
- Le présent-biais explique-t-il la trajectoire de dette ? (E3, optionnel)
- Un foyer non unitaire produit-il des allocations différentes ? (E6)
- Quels paramètres gouvernent réellement les résultats ? (E-SA)

Le modèle ne prétend pas reproduire un processus psychologique réel : la cognition est un **mécanisme de décision à rationalité limitée** dont on étudie l'effet sur des grandeurs comptables.

### 1.2 Patterns

Les patterns servant à juger le modèle et leur rôle sont **figés** dans `config/patterns.yaml` (empreinte vérifiée par test) :

| Pattern | Niveau | Rôle |
|---|---|---|
| P1 signature du LCD par âge | population | calibration |
| P2 revenu du travail par âge | population | calibration |
| P3 consommation par âge | population | calibration |
| P4 orientation et volume des transferts | population | validation |
| P5 distribution dette/revenu | population | validation |
| P6 reste-à-vivre / pauvreté | population | validation |
| P7 trajectoires intergénérationnelles | population | exploratoire |

À l'échelle d'un foyer unique (V2), seuls des **patterns qualitatifs individuels** sont exigibles : signe du LCD par membre, signe et ordre de grandeur des réponses aux chocs, et la reproduction simultanée d'au moins deux patterns avec un seul jeu de paramètres (critère de sortie V2). La confrontation aux profils agrégés relève de la V3.

## 2. Entities, state variables and scales

### 2.1 Entités

| Entité | Nombre | Rôle |
|---|---|---|
| `PersonAgent` | 6 (7+ si départ du jeune adulte crée un foyer) | membre du foyer ; perçoit, révise ses croyances, forme des désirs et une intention, décide de ses demandes, agit |
| `HouseholdAgent` | 1 (2 si départ) | collecte les demandes, met en commun les revenus, alloue sous contrainte budgétaire, porte la dette et l'épargne collectives |
| Environnement | 1 | horloge, prix, marché du travail (probabilités de perte et de retour à l'emploi), État (impôts, transferts, consommation publique), banque |
| `Ledger` | 1 | journal en double entrée de tout mouvement de valeur ; source unique des mesures NTA |

Il n'existe **qu'un seul type d'agent individuel**. Les « rôles » (père, bébé…) sont des étiquettes descriptives sans effet sur la logique ; seuls les **capacités** et **paramètres** du profil diffèrent.

### 2.2 Variables d'état de la personne

**Économiques et physiques** (inchangées depuis V1 — voir `ODD_v1_economic.md` §2) : statut d'emploi, salaire de plein temps, offre de travail, taux de mise en commun, solde du portefeuille, dépenses par besoin, santé ∈ [0,1], épisode de maladie, coût des soins requis, capacité de travail, niveaux et satisfactions des six besoins (alimentation, santé, éducation, logement, repos, sécurité), statut scolaire, âge (mois).

**Nouvelle variable physique V2 :** `fatigue` ∈ [0,1], accrue par une offre de travail > 1, résorbée par le repos.

**Cognitives (actives en V2) :**

| Variable | Domaine | Description |
|---|---|---|
| Croyances | dict clé → (valeur, confiance ∈ [0,1], pas de mise à jour) | ~14 prédicats et grandeurs (revenu attendu, stabilité du revenu, emploi menacé, dette gérable/critique, coussin suffisant, enfant malade, scolarité menacée, taux d'allocation attendu par besoin, possibilité de quitter le foyer) |
| Désirs | liste de buts priorisés | déficits de besoins + buts de long terme |
| Intention | but + plan + étape + statut | une seule active, au plus une suspendue |
| Aspirations θ_k | [θ_min, θ_max] par besoin | seuils de satisfaction, adaptatifs |
| Mémoire épisodique | ≤ `memory.capacity` épisodes | épisodes datés (revenu, choc, allocation, refus, consommation, résultat de plan, satisfaction), avec instants de présentation |

**Affectives :** présentes mais neutres (0) en V2.

### 2.3 Profil cognitif (paramètres individuels)

| Paramètre | Bébé | Enfant | Adolescent | Jeune adulte | Mère | Père |
|---|---|---|---|---|---|---|
| `max_alternatives` | 1 | 2 | 3 | 5 | 8 | 8 |
| `planning_horizon` (mois) | 0 | 1 | 3 | 12 | 24 | 24 |
| `aspiration_init` | 0,60 | 0,60 | 0,65 | 0,65 | 0,70 | 0,70 |
| adaptation up / down | 0 / 0 | 0,05 / 0,10 | 0,10 / 0,15 | 0,10 / 0,15 | 0,10 / 0,15 | 0,10 / 0,15 |
| mémoire : capacité / décroissance d | 0 / 0,5 | 10 / 0,5 | 20 / 0,5 | 40 / 0,5 | 60 / 0,5 | 60 / 0,5 |
| `intention_commitment` | 0 | 0,2 | 0,3 | 0,6 | 0,8 | 0,8 |
| `impulsivity` | 1,0 | 0,7 | 0,6 | 0,3 | 0,2 | 0,2 |
| actualisation (mode, β, δ) | none | exponentielle, 1, 0,99 | naïf, 0,7, 0,995 | naïf, 0,85, 0,995 | sophistiqué, 0,95, 0,995 | sophistiqué, 0,95, 0,995 |
| capacités cognitives | — | remember | remember, plan | remember, plan | remember, plan | remember, plan |

Valeurs illustratives (`PLACEHOLDER`) ; le profil suit l'âge par transitions déclarées en configuration (bébé → enfant à 5 ans, enfant → adolescent à 13 ans, adolescent → jeune adulte à 18 ans).

### 2.4 Variables d'état du foyer

Inchangées depuis V1 (`ODD_v1_economic.md` §2) : pot commun, épargne, prêt (dette), plafond de crédit, mois d'arriérés, poids d'allocation, parts de propriété ω, chef de ménage (imputation ONU seulement). En V2, les **poids d'allocation** peuvent varier (mode `variable_weights`).

### 2.5 Échelles

- **Temps :** pas mensuel (D11) ; horizon 240 mois par défaut (D12), 120 ou cycle de vie en option. L'âge avance d'un an tous les 12 pas.
- **Espace :** non représenté.
- **Monnaie :** FCFA (XOF), montants mensuels, précision 0,01 FCFA dans le journal comptable.
- **Population :** un foyer (deux si le jeune adulte part, D13).

## 3. Process overview and scheduling

Chaque pas mensuel comporte trois temps, dans cet ordre. Les éléments **en gras** sont propres à la V2.

**0. Environnement.** Avance de l'horloge ; application des événements exogènes du scénario (perte d'emploi, épisode de maladie, chocs de prix ou de revenu, changement de politique).

**Temps 1 — perception et demande** (chaque personne, ordre aléatoire seedé, sans effet sur le résultat car les demandes sont arbitrées simultanément) :
1. Remise à zéro des dépenses du pas, transitions de santé, **fatigue**, perception (les niveaux de besoins sont lissés au Temps 3, après les actions).
2. **Encodage en mémoire** des épisodes perçus (revenu et chocs du pas précédent).
3. **Révision des croyances** à partir de la perception et de la mémoire.
4. **Dérivation des désirs.**
5. **Délibération** : adoption, persistance, suspension ou abandon de l'intention (le seuil d'engagement est lu dans le profil effectif).
6. Génération des alternatives, **l'étape de plan courante étant placée en tête**.
7. Décision par satisficing (**avec taux d'allocation attendus tirés de la mémoire et pondération temporelle β-δ si activée**) → demandes priorisées et trace de décision.

**Temps 2 — arbitrage du foyer :** transitions d'emploi, versement des salaires et impôt à la source ; transferts publics en espèces ; intérêts (épargne et dette) ; mise en commun ; engagements (logement, échéance) ; allocation par paliers sous contrainte budgétaire avec emprunt pour l'essentiel ; notification. **Poids variables recalculés si le mode l'exige.**

**Temps 3 — action et comptabilité :**
1. Exécution des allocations ; complément personnel depuis le portefeuille ; consommation publique en nature ; lissage des niveaux de besoins.
2. **Évaluation du résultat** du pas (satisfactions réalisées, refus, réussite de l'étape de plan).
3. **Encodage en mémoire** (allocations, refus, consommation, résultat de plan, satisfactions).
4. **Mise à jour des aspirations** (boucle B2).
5. **Avancement de l'intention** : étape suivante, replanification, succès ou échec.
6. Calcul NTA depuis le journal ; vérification des identités (échec dur) ; collecte des sorties.
7. **Départ éventuel du jeune adulte**, appliqué après la comptabilité (D13).
8. Vieillissement (un mois d'âge à chaque pas, après la collecte) et transitions de profil.

Aucune étape cognitive n'écrit dans le journal comptable : la cognition n'agit sur l'économie que par les demandes.

```
Boucles de rétroaction :
  B1 économique : action → état économique → besoins → décision                     (V1)
  B2 cognitive  : résultat → mémoire → aspiration / croyances → décision            (V2)
```

## 4. Design concepts

**Basic principles.** Rationalité limitée (Simon 1955) : les agents ne maximisent pas, ils retiennent la première option jugée satisfaisante au regard de seuils d'aspiration, parmi un nombre borné d'options, sur un horizon borné. Raisonnement pratique BDI (Bratman ; Rao & Georgeff) dans une forme dégradée : croyances comme prédicats, désirs comme buts priorisés, intentions persistantes adossées à une bibliothèque de plans pré-écrits (pas de synthèse de plans : D4). Les NTA (ONU 2013) sont une comptabilité appliquée ex post (D2). Le foyer est modélisé comme un arbitre à règle d'allocation paramétrée ; les modèles collectifs (Chiappori) servent de repère théorique, non de mécanisme (D7).

**Emergence.** Les trajectoires de dette, d'épargne, de scolarisation et la signature du LCD par membre émergent de l'interaction entre demandes individuelles et rationnement du foyer. En V2, la **persistance des intentions** et l'**adaptation des aspirations** peuvent produire des régularités non imposées : lissage de la consommation, résistance aux chocs, abaissement durable des aspirations après des échecs répétés.

**Adaptation.** Trois mécanismes adaptatifs, tous paramétrés :
(i) choix d'une alternative par satisficing ; (ii) **adaptation des seuils d'aspiration** : θ monte vers la satisfaction réalisée après un succès (vitesse `up`), descend après un échec (vitesse `down`), dans [θ_min, θ_max] ; (iii) **sélection et révision d'intention** : un plan est abandonné pour un autre en cas d'échec, une intention n'est reconsidérée que si un désir concurrent la dépasse d'un facteur (1 + `intention_commitment`).

**Objectives.** Les agents n'ont pas de fonction objectif unique. Le critère est non compensatoire : chaque besoin attendu doit atteindre son seuil sur l'horizon projeté, dans l'ordre de priorité du profil. Les buts de long terme (rembourser, constituer un coussin, scolariser, retrouver un emploi, faire face à une perte de revenu, quitter le foyer) entrent comme désirs priorisés.

**Learning.** Pas d'apprentissage au sens d'une modification de la stratégie de décision. Ce qui change avec l'expérience : les seuils d'aspiration et les croyances (via la mémoire). Absence d'apprentissage par renforcement : choix assumé (Chap. 9, perspective).

**Prediction.** Chaque agent projette, sur `planning_horizon` mois, l'évolution de ses niveaux de besoins sous chaque alternative, en supposant que le foyer lui accordera la part qu'il a reçue en moyenne dans ses souvenirs (taux attendu ê_k, moyenne pondérée par l'activation mémorielle). Avec l'actualisation β-δ (optionnelle), les pas futurs sont pondérés par β·δ^t ; un agent **naïf** croit que ses choix futurs ne seront pas biaisés, un agent **sophistiqué** l'anticipe et privilégie les plans à engagement.

**Sensing.** Chaque personne perçoit son propre état, une vue agrégée du foyer (dette, arriérés, ratio dette/revenu, emploi et santé des membres, refus récents) et les événements qui la concernent. Elle ne perçoit ni le budget futur, ni les paramètres des autres. La perception est exacte (pas de bruit) ; l'imperfection de l'information vient de la mémoire bornée et décroissante.

**Interaction.** Indirecte, médiée par le foyer : les demandes individuelles entrent en concurrence pour un budget commun. Les plans peuvent porter sur un autre membre (payer les frais de scolarité ou les soins d'un enfant). Pas de communication directe entre agents. Interaction inter-foyers limitée aux transferts du jeune adulte parti (D13).

**Stochasticity.** Perte et retour à l'emploi, volatilité du revenu informel, épisodes de maladie et leur sévérité, ordre de traitement des personnes (sans effet), raccourci d'impulsivité (avec probabilité `impulsivity`, seul le premier besoin attendu est vérifié), bruit d'activation mémorielle (désactivé par défaut). Chaque usage tire dans un sous-flux nommé dérivé de la graine ; même graine ⇒ même trajectoire.

**Collectives.** Le foyer est un collectif représenté explicitement par un agent (`HouseholdAgent`) qui détient le pot commun, l'épargne et la dette, et applique la règle d'allocation. Un départ du jeune adulte crée un nouveau collectif d'une personne.

**Observation.** Tables par personne et par pas, par foyer et par pas, journal comptable, demandes et allocations, traces de décision (alternatives considérées, raison du choix, intention, plan), événements, comptes NTA par personne, matrice des transferts intra-ménage, profils par âge, indicateurs scalaires. En V2 s'ajoutent : statut d'intention, étape de plan, poids d'allocation par pas, croyances (échantillonnées), taux de situations sans plan applicable.

### 4.1 Bloc ODD+D — prise de décision individuelle

| Question ODD+D | Réponse V2 |
|---|---|
| Sujets et objets de la décision | Chaque personne décide de ses **demandes** au foyer (montants par besoin), de son **offre de travail**, de son **épargne demandée**, de la recherche d'emploi, et — via les plans — d'actions portant sur un autre membre (frais de scolarité, soins). Le foyer décide de l'**allocation**. |
| Niveau de décision | Individuel (demandes) puis collectif (allocation) ; deux niveaux séquentiels dans le même pas. |
| Rationalité / fondement | Rationalité limitée : satisficing non compensatoire (Simon) ; BDI dégradé (Bratman) ; actualisation quasi-hyperbolique optionnelle (Laibson). |
| Comment les agents décident | Énumération ordonnée de `max_alternatives` options (plan courant en tête, puis option habituelle, puis par couverture du besoin prioritaire) ; projection sur `planning_horizon` ; acceptation de la première option dont tous les besoins attendus atteignent leur seuil ; à défaut, option maximisant le besoin prioritaire. |
| Adaptation de la décision | Seuils d'aspiration adaptatifs ; révision d'intention ; replanification sur échec ; taux d'allocation attendus mis à jour par la mémoire. |
| Normes sociales, valeurs | Représentées seulement par l'ordre de priorité des besoins (profil) et, au niveau du foyer, par les poids d'allocation et l'ordre des paliers (essentiel avant éducation avant le reste). Aucune norme explicite. |
| Aspects spatiaux | Aucun. |
| Aspects temporels | Horizon de projection propre à chaque profil ; persistance des intentions sur plusieurs mois ; pondération temporelle β-δ optionnelle ; mémoire à oubli décroissant. |
| Incertitude | Les agents ne connaissent pas l'allocation future ; ils l'estiment par la mémoire. Les risques (chômage, maladie) ne sont pas évalués comme des loteries en V2 (CPT en V3). |

## 5. Initialization

- Composition et âges à t₀ : père 45 ans (emploi formel), mère 40 ans (emploi informel), jeune adulte 20 ans (étudiant), adolescent 15 ans, enfant 9 ans (scolarisés), bébé 1 an.
- Actifs initiaux : pot 50 000 FCFA, épargne 150 000 FCFA, dette nulle ; propriété du pot : père 0,5, mère 0,5 ; chef de ménage pour l'imputation : père.
- Besoins à 1, santé à 1, fatigue à 0.
- **Cognition à t₀ :** mémoire vide ; croyances à leurs valeurs par défaut (revenu attendu = salaire × offre × capacité, taux d'allocation attendu = 1) ; aucun désir ni intention ; θ_k = `aspiration_init`.
- Graine explicite ; initialisation déterministe.
- Source des données : `synthetic` par défaut (valeurs illustratives) ; `nta_profiles` ou `ehcvm` remplacent les valeurs monétaires quand elles sont disponibles. Un run contenant des valeurs illustratives est marqué comme tel.

## 6. Input data

Aucune série temporelle externe ne pilote le modèle en V2. Les entrées sont des **paramètres** (`config/*.yaml`) : profils cognitifs, besoins, paramètres économiques (salaires, coûts par âge, probabilités de chocs, taux), règles du foyer, **bibliothèque de plans (`plans.yaml`)** et scénarios (événements datés). Chaque paramètre porte une provenance (`PLACEHOLDER`, `DIRECT`, `FIX_LIT`, `EXPLORED`, `CALIBRATED`).

## 7. Submodels

### 7.A Sous-modèles inchangés depuis la V1

Repris à l'identique ; voir `ODD_v1_economic.md`, section 7, sous-modèles de même nom :
- Besoins (niveau lissé, satisfaction monétaire, besoins non monétaires repos et sécurité) — **à une modification près** : la satisfaction du repos intègre désormais la fatigue (7.B.9).
- Revenu du travail, impôt, mise en commun ; emploi et chocs de revenu.
- Santé et soins ; scolarité.
- Logement et échelle d'équivalence ; consommation publique en nature.
- Dette, intérêts, plafond de crédit, épargne.
- Allocation du foyer `allocate()` (paliers, rationnement pondéré, emprunt pour l'essentiel, modes unitaire / poids fixes) — le mode poids variables est décrit en 7.B.10.
- Exécution des actions, complément personnel.
- Couche NTA : attribution du pot commun, identités de flux, imputation ONU, invariants.
- Moteur de décision par satisficing : génération et ordre de saillance des alternatives, projection, score, acceptabilité lexicographique, raccourci d'impulsivité, repli — **avec les entrées V2 décrites en 7.B.6 et 7.B.8**.

### 7.B Sous-modèles cognitifs (nouveaux en V2)

**7.B.1 Mémoire épisodique.** Chaque personne dotée de la capacité `remember` conserve au plus `capacity` épisodes. L'activation d'un épisode présenté aux instants t_j vaut A(t) = ln Σ_j (t − t_j)^(−d), avec t − t_j ≥ 1 mois et d = 0,5. Un épisode est rappelable si A ≥ seuil de rappel ; il est renforcé (nouvel instant de présentation) lorsqu'il est utilisé dans une décision. À saturation, l'épisode d'activation minimale est oublié (égalité : le plus ancien). Les épisodes encodés sont : revenu perçu, chocs, taux d'allocation par besoin, refus, consommation, résultat d'étape de plan, satisfaction par besoin. Les estimations tirées de la mémoire sont des moyennes pondérées par exp(A) normalisé.

**7.B.2 Révision des croyances.** Règles déterministes recalculées à chaque pas : revenu attendu (moyenne mémorielle des revenus), stabilité du revenu (coefficient de variation < 0,10 sur ≥ 3 souvenirs), emploi, perte d'emploi récente, emploi menacé, perte d'emploi d'un pourvoyeur, dette gérable (dette/revenu < 1), dette critique (≥ 2 mois d'arriérés), coussin suffisant, enfant malade, scolarité menacée ou interrompue (par enfant), taux d'allocation attendu par besoin, possibilité de quitter le foyer. La confiance des croyances mémorielles croît avec le nombre de souvenirs (min(1, n/6)).

**7.B.3 Désirs.** Un désir « satisfaire k » pour chaque besoin attendu sous son seuil, de priorité (θ_k − niveau_k) × poids de rang ; plus des buts de long terme déclenchés par les croyances et conditionnés aux capacités : faire face à une perte de revenu (0,9), crise de santé (0,85), trouver un emploi (0,7), scolariser un enfant (0,6), rembourser (0,5 ; 0,8 si dette critique), constituer un coussin (0,4), quitter le foyer (0,3).

**7.B.4 Intentions.** Une intention active au plus. Elle est adoptée pour le désir le plus prioritaire disposant d'un plan applicable. Elle persiste tant qu'aucun désir concurrent n'excède sa priorité d'un facteur (1 + `intention_commitment`) ; sinon elle est suspendue (une au plus) et une nouvelle est adoptée. Elle se termine par succès (condition de succès du plan), échec (aucun plan alternatif), ou abandon (désir disparu ou durée maximale dépassée).

**7.B.5 Bibliothèque de plans et replanification.** Une vingtaine de plans pré-écrits couvrent : faire face à la perte d'emploi (chercher et réduire, puiser dans l'épargne, emprunter, autre apporteur, relever sa contribution), rembourser la dette (réduire et rembourser, travailler plus, utiliser l'épargne), constituer un coussin (épargne régulière, réduction des loisirs), scolariser un enfant (payer les frais, réinscrire), crise de santé (payer les soins, emprunter pour les soins), maintenir l'alimentation (protéger, minimum), chercher un emploi (recherche, entrée dans l'informel), quitter le foyer, réduction générale de la consommation. Chaque plan a une condition d'applicabilité, une suite d'étapes (actions ou sous-buts, profondeur ≤ 2), une condition de succès, une condition d'échec et une durée maximale. Un échec d'étape est consigné en mémoire ; si la condition d'échec du plan est atteinte, le plan suivant applicable est essayé (en évitant les plans récemment échoués) ; à défaut, l'intention échoue. En l'absence de tout plan applicable, l'agent décide par satisficing pur et l'événement est compté (taux visé ≤ 5 %).

**7.B.6 Intégration plan → décision.** L'étape de plan courante produit une alternative placée en tête de l'ordre de saillance et jamais tronquée. Le satisficing l'évalue comme les autres ; si elle est acceptable, elle est choisie ; sinon l'étape échoue et le choix se poursuit sur les alternatives suivantes. Le plan oriente donc la décision sans constituer un second mécanisme de choix.

**7.B.7 Adaptation de l'aspiration (boucle B2).** Après exécution : si s_k ≥ θ_k, θ_k ← θ_k + up·(s_k − θ_k) ; sinon θ_k ← θ_k − down·(θ_k − s_k) ; puis θ_k borné dans [θ_min, θ_max]. Hypothèse implicite (HYP) : l'ajustement est monotone et linéaire en l'écart.

**7.B.8 Taux d'allocation attendus et actualisation.** Dans la projection du satisficing, la satisfaction attendue d'un besoin utilise ê_k (moyenne mémorielle des taux accordés). Si l'actualisation est activée, le score projeté pondère le pas t par D(t) = β·δ^t (D(0) = 1) en mode quasi-hyperbolique, δ^t en mode exponentiel. À l'adoption d'une intention, les plans applicables sont alors comparés par leur valeur projetée : l'agent naïf les évalue avec δ seul, l'agent sophistiqué avec β·δ^t en supposant abandonnées les étapes que son « moi » futur rejetterait ; seul l'agent sophistiqué privilégie donc les plans à engagement (épargne prélevée comme engagement du foyer).

**7.B.9 Fatigue et offre de travail.** Une offre de travail portée au-delà de 1 (≤ 1,25) accroît la fatigue de 0,5 × l'excès ; la fatigue se résorbe de 0,2 par mois quand l'offre est ≤ 1 ; la satisfaction du repos vaut clip(1 − 0,6·max(0, offre − 0,8) − fatigue, 0, 1). La recherche d'emploi double la probabilité mensuelle de retour à l'emploi.

**7.B.10 Poids de négociation variables (optionnel).** En mode `variable_weights`, les poids d'allocation valent w_i = w0_i·(1 + γ·Yl_i/ΣYl), normalisés, recalculés chaque mois ; γ = 0 redonne les poids fixes.

**7.B.11 NTTA (optionnel).** Temps domestique produit (heures par membre, réduites par l'offre de travail marchand), valorisé à un salaire horaire fictif, consommé par les membres selon l'échelle d'équivalence ; comptes de temps séparés des NTA monétaires, avec identité production = consommation par foyer.

**7.B.12 Départ du jeune adulte (D13, paramétrable).** Si autorisé, et lorsque le plan de départ aboutit, la personne quitte le foyer en fin de pas et constitue un foyer d'une personne (même type d'agent foyer), dont elle est seule propriétaire ; elle conserve son portefeuille, supporte un coût de logement propre et envoie chaque mois une part de son revenu au foyer d'origine (transfert privé inter-ménages, comptabilisé des deux côtés).

## 8. Limites propres à la V2 (pour le Chapitre 9)

- Les écarts V1/V2 dépendent du contenu de la bibliothèque de plans, qui est un choix de conception (ablation à rapporter).
- Formes fonctionnelles de l'adaptation des aspirations et des priorités de désirs : hypothèses, non observées.
- Pas de synthèse de plans nouveaux (D4) ; pas d'apprentissage par renforcement.
- Perception exacte de l'état du foyer : hypothèse forte pour les enfants.
