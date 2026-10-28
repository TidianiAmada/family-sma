# ODD-V3 — Modèle cognitif-affectif et population de foyers

> **Brouillon généré — à réviser et s'approprier par l'auteur.** Ce document deviendra le Chapitre 5 complet et l'annexe ODD du mémoire ; il doit être réécrit dans la voix de l'auteur.
>
> Protocole : ODD (Grimm et al. 2020), section « Design concepts » complétée par le bloc de décision ODD+D. Version du modèle : `model.version: v3`. Spécification d'implémentation : `specs/30_SPEC_V3_AFFECTIVE_POPULATION.md`.
> **Renvois :** les sous-modèles inchangés depuis la V1 ou la V2 sont décrits dans `ODD_v1_economic.md` et `ODD_v2_cognitive.md` ; ce document indique pour chacun la section de référence (§7 « Submodels » de ces documents, sous-section nommée) au lieu de les recopier. La description de la V3 est complète à la lecture conjointe des trois fichiers.

---

## 1. Purpose and patterns

**But.** Le modèle simule des foyers composés de membres hétérogènes (du bébé au parent) représentés par un agent générique unique paramétré, afin de (i) mesurer, au moyen des National Transfer Accounts, les conséquences économiques du mode de vie du foyer, (ii) étudier si la rétroaction entre contrainte économique, état affectif et capacité de décision (boucle B3) peut produire un enfermement endogène après un choc, et (iii) reproduire, au niveau d'une population de foyers, des profils NTA par âge comparables aux profils nationaux.

**Questions servies en V3** (matrice `docs/MATRICE_QUESTION_MODELE.md`) : articulation « dur / mou » sans conversion en utilité (E4) ; effet de l'aversion aux pertes (E5) ; émergence au passage à la population (E7) ; écart à l'efficacité collective (E8) ; simplification cognitive admissible (E9) ; possibilité d'initialiser et de calibrer avec les données disponibles (Phase 9).

**Patterns (POM).** L'affectation est figée dans `config/patterns.yaml` (hash) depuis la Phase 2 et n'est pas modifiée en V3 :

| Pattern | Niveau | Rôle |
|---|---|---|
| P1 Signature du LCD par âge | population | calibration |
| P2 Revenu du travail par âge | population | calibration |
| P3 Consommation par âge | population | calibration |
| P4 Orientation et volume des transferts | population | **validation** |
| P5 Distribution dette/revenu | population | **validation** |
| P6 Reste-à-vivre / pauvreté | population | **validation** |
| P7 Trajectoires intergénérationnelles | population | exploratoire |

Critère de vraisemblance du modèle : reproduction simultanée d'au moins trois patterns avec un seul jeu de paramètres, dont au moins un du set de validation. La validation porte sur des **patterns réservés** issus des mêmes sources que les cibles de calibration ; il ne s'agit pas d'une validation hors échantillon et elle ne doit pas être présentée comme telle.

## 2. Entities, state variables and scales

**Entités.** `PersonAgent` (une seule classe), `HouseholdAgent`, l'environnement (prix, marché du travail, État, banque — comptes externes), le `Ledger`. En V3, la population compte N foyers indépendants (défaut 1 000).

**Variables d'état.** Celles de la V1 (`ODD_v1_economic.md` §2 : `EconomicState`, `PhysicalState`, `NeedsState`, `HouseholdState`) et de la V2 (`ODD_v2_cognitive.md` §2 : `CognitiveState`, mémoire épisodique), plus :

| Entité | Variable | Domaine | Description |
|---|---|---|---|
| Personne | `joy`, `sadness`, `fear`, `anger` | [0, 1] | intensités émotionnelles |
| Personne | `stress` S | [0, 1] | accumulateur de stress |
| Personne | `mood` | [−1, 1] | moyenne mobile de la désirabilité |
| Personne | `in_mutuelle`, `in_tontine` | booléen | adhésions (si CPT active) |
| Personne (transitoire) | `EffectiveCognitiveProfile` | — | H_eff, M_eff, aspiration_scale, β_eff, λ_eff, commitment_eff ; recalculé à chaque pas, non persistant |
| Foyer | `regime` | NORMAL / SEPARATE_SPHERES | régime de coordination |
| Foyer | `stress_months` | entier ≥ 0 | mois consécutifs au-dessus/au-dessous du seuil |

Toutes les variables, leurs types et leurs valeurs neutres figurent dans `specs/02_DOMAIN_MODEL.md` §4.

**Échelles.** Pas de temps mensuel ; horizon par défaut 240 mois (10 ans, 20 ans ou cycle de vie paramétrables) ; unité monétaire FCFA à prix constants de t₀ indexés par l'inflation. Aucune dimension spatiale.

## 3. Process overview and scheduling

Le pas mensuel suit les trois temps décrits dans `ODD_v1_economic.md` §3, enrichis en V2 (`ODD_v2_cognitive.md` §3). Les ajouts V3 sont en **gras** :

0. Avancer l'horloge ; appliquer les événements de scénario.
1. **Temps 1 — perception et demande**, pour chaque personne (ordre aléatoire seedé, sans effet sur le résultat) :
   1. remise à zéro des dépenses du pas, mise à jour de la santé, perception ; **rétroaction stress → santé avec le stress du pas précédent** ;
   2. encodage mémoire, révision des croyances et dérivation des désirs ;
   3. **appraisal → mise à jour des émotions, du stress et de l'humeur** ;
   4. **modulation → `EffectiveCognitiveProfile`** ;
   5. délibération (intentions), qui lit le seuil d'engagement **effectif** ;
   6. **décisions binaires sous risque (CPT), si une décision est ouverte** ;
   7. décision satisficing (profil effectif) → demandes priorisées + trace.
2. **Temps 2 — arbitrage du foyer** : transitions d'emploi, revenu et impôt ; transferts publics ; intérêts ; **test de transition de régime (sphères séparées), avant la mise en commun car le régime réduit le pooling** ; mise en commun ; engagements ; allocation par la fonction unique `allocate()` — appliquée au budget commun en régime normal, **à des sous-budgets par sphère en régime dégradé** ; emprunt éventuel ; notification.
3. **Temps 3 — action et comptabilité** : exécution, compléments personnels, écritures ; lissage des niveaux de besoins ; évaluation des résultats (mémoire, aspiration, intention) ; calcul NTA depuis le Ledger ; vérification des invariants ; collecte ; puis vieillissement (un mois par pas) et transitions de profil.

Population : les foyers sont simulés indépendamment ; l'ordre des foyers n'a pas d'effet (flux aléatoires propres à chaque foyer).

## 4. Design concepts

**Basic principles.** Rationalité limitée (Simon) par satisficing à seuil d'aspiration ; raisonnement pratique BDI dégradé (Bratman, Rao & Georgeff) ; comptabilité générationnelle NTA (ONU 2013) comme couche de mesure ; théorie de l'appraisal (Lazarus ; EMA, Marsella & Gratch 2009) pour produire l'affect ; hypothèse de charge cognitive sous rareté (Mani et al. 2013) pour justifier que l'affect **module les paramètres du processus de décision** sans produire d'utilité. Modèle collectif du ménage (Chiappori) utilisé comme repère d'efficacité ex post, non comme mécanisme.

**Emergence.** Trajectoires de dette, temps de retour après choc, éventuel enfermement endogène, ruptures de coordination (régime de sphères), profils NTA par âge et distributions entre foyers (Gini, pauvreté) émergent des décisions individuelles, de l'allocation et des chocs. Sont imposés : les identités comptables, les besoins de référence par âge, les probabilités de choc.

**Adaptation.** Choix d'un panier de demandes par satisficing ; adaptation du seuil d'aspiration (V2) ; sélection et révision de plans (V2) ; **en V3, la profondeur de délibération (horizon, nombre d'alternatives), le présent-biais, l'engagement et l'aversion aux pertes varient avec l'état affectif.**

**Objectives.** Pas de fonction objectif scalaire. Critère non compensatoire : chaque besoin attendu doit atteindre son seuil d'aspiration sur l'horizon de planification (ordre lexicographique). Décisions binaires sous risque : valeur prospect (CPT).

**Learning.** Aucun apprentissage au sens strict (pas de modification des règles de décision). L'adaptation des aspirations et la mémoire épisodique sont des ajustements de paramètres d'état. Choix assumé (Chap. 9).

**Prediction.** Projection des niveaux de besoin sur l'horizon H_eff avec la persistance des besoins et un taux d'allocation attendu tiré de la mémoire ; actualisation exponentielle ou β-δ. Le stress raccourcit l'horizon de prédiction.

**Sensing.** Chaque personne perçoit ses besoins, sa santé, son revenu, les décisions d'allocation qui la concernent et des grandeurs agrégées du foyer (coussin d'épargne, marge de crédit). Perception sans bruit ; bornée en ce que seules `max_alternatives` alternatives sont considérées.

**Interaction.** Directe uniquement à l'intérieur du foyer, médiatisée par la demande et l'allocation ; indirecte par le budget commun. Aucune interaction entre foyers dans le périmètre (exceptions : transferts inter-ménages du jeune adulte parti, mutuelle et tontine, représentés comme flux vers un compte externe agrégé).

**Stochasticity.** Chocs d'emploi, revenus informels, épisodes de maladie, tirages d'impulsivité, mois de la cagnotte de tontine, génération de la population. Tous par sous-flux nommés d'un `SeedSequence` racine, par foyer ; même seed ⇒ même trajectoire.

**Collectives.** Le foyer est un collectif explicite doté de sa propre règle d'allocation, de son budget, de sa dette et d'un régime de coordination qui peut se dégrader en sphères séparées.

**Observation.** Tables Parquet par pas (personnes, foyers, demandes, événements, NTA par personne, matrice de transferts annuelle, profils par âge), traces de décision échantillonnées, indicateurs scalaires (`specs/04_DATA_MODEL.md`). Les émotions, le stress et le profil effectif sont observés même lorsque la boucle B3 est coupée.

### Bloc ODD+D — prise de décision individuelle

| Question | Réponse V3 |
|---|---|
| Sujets et objets de décision | Personnes : panier de demandes, offre de travail, adhésions/emprunt (parents) ; foyer : allocation sous contrainte. |
| Rationalité de base | Rationalité limitée ; satisficing non compensatoire ; pas de maximisation d'utilité. |
| Comment les agents décident | Énumération bornée d'alternatives ordonnées par saillance, acceptation de la première au-dessus des seuils ; étape de plan placée en tête ; CPT pour 4 décisions binaires. |
| Adaptation des décisions | Aspirations, intentions, et en V3 paramètres effectifs modulés par l'affect. |
| Normes sociales / valeurs | Poids d'allocation et ordre des besoins (données) ; sphères de responsabilité parentales en régime dégradé (Lundberg & Pollak 1993). |
| Aspects spatiaux | Aucun. |
| Aspects temporels | Horizon de planification, actualisation β-δ, mémoire à activation décroissante. |
| Incertitude | Probabilités subjectives de menace (croyances), pondération des probabilités en CPT ; pas de bruit de perception. |

## 5. Initialization

- **Foyer seul** : composition de référence (`config/household_rules.yaml`, `baseline_household`) : père 45 ans, mère 40, jeune adulte 20, adolescent 15, enfant 9, bébé 1 ; actifs initiaux ; affect nul ; régime NORMAL.
- **Population** : `population/generator.py` tire N gabarits selon leurs poids, applique un jitter d'âge par rôle sous contrainte de cohérence, tire salaires, statuts d'emploi et actifs selon la source de données active, et attribue à chaque foyer un sous-flux aléatoire indexé (`specs/30_SPEC_V3_AFFECTIVE_POPULATION.md` §3).
- Les profils cognitifs sont déduits de l'âge (`profile_transitions`).
- L'initialisation est variable entre réplications (seed) mais identique entre conditions expérimentales d'une même réplication.

## 6. Input data

| Donnée | Source | Usage | Statut |
|---|---|---|---|
| Profils NTA du Sénégal (Yl, C, LCD par âge) | CREFAT, Université de Thiès | paramétrage direct des profils de consommation et de revenu par âge ; cibles P1–P3 ; forme des cibles P4 | demande à confirmer |
| EHCVM 2018-2019 et 2021-2022 | ANSD (catalogue ANADS), microdonnées Banque mondiale | population synthétique (compositions, revenus, actifs, emploi), chocs de revenu, transitions de santé, cibles P5–P6 | demande à confirmer |
| Seuil de pauvreté | ANSD / EHCVM | `poverty_line_per_eq` | placeholder |
| Paramètres CPT | Tversky & Kahneman (1992) | α, λ, γ | littérature |

**Préparation.** Scripts `data/` (non commités pour les microdonnées brutes) produisant `data/processed/*.parquet` : distributions par rôle, cibles par âge, avec un fichier de provenance (`data/README.md`).

**Procédure de repli.** Si une source est indisponible, `population/sources.py` revient à la source `synthetic` (`config/population.yaml`), émet un avertissement et consigne la source demandée et la source effective dans les métadonnées du run ; tout run dont la configuration contient une valeur `PLACEHOLDER` est marqué `illustrative: true`. Le mémoire doit alors parler de « modèle illustratif » ou de « population paramétrée sur les profils NTA publiés », selon le cas.

## 7. Submodels

### 7.1 Sous-modèles inchangés (renvois)

| Sous-modèle | Référence |
|---|---|
| Besoins, satisfaction, persistance | `ODD_v1_economic.md` §7.5 « Besoins » |
| Revenu du travail, emploi, chocs, impôt | `ODD_v1_economic.md` §7.2 « Revenu et emploi » |
| Santé (épisodes, soins, capacité de travail) | `ODD_v1_economic.md` §7.4 « Santé » — complété par §7.5 ci-dessous |
| Scolarité | `ODD_v1_economic.md` §7.6 « Scolarité » |
| Crédit, intérêts, arriérés | `ODD_v1_economic.md` §7.9 « Dette et crédit » |
| Allocation du foyer (fonction unique) | `ODD_v1_economic.md` §7.8 « Allocation » ; poids variables : `ODD_v2_cognitive.md` §7, « Poids de négociation » — complété par §7.4 |
| Ledger, NTA, attribution, imputation ONU, invariants | `ODD_v1_economic.md` §7.10 « Comptabilité NTA » |
| Moteur satisficing | `ODD_v1_economic.md` §7.7 « Décision » ; actualisation et intégration des plans : `ODD_v2_cognitive.md` §7 |
| Mémoire, croyances, désirs, intentions, plans, aspiration, β-δ, départ du jeune adulte | `ODD_v2_cognitive.md` §7 |

### 7.2 Appraisal

Pour une personne disposant de la capacité d'appraisal, à chaque pas, pour chaque besoin attendu k de rang ρ_k (poids π_k = 1/(1+ρ_k)) : congruence g_k = sat_k − θ_k ; pertinence r = Σπ_k|g_k|/Σπ_k ; désirabilité d = Σπ_k g_k/Σπ_k ; contrôlabilité c = clip(w_buf·min(1, coussin/cible) + w_cred·marge de crédit relative + w_sup·taux d'allocation récent, 0, 1) ; menace p = confiance maximale des croyances « emploi menacé » et « dette critique » (et maladie d'un enfant, pondérée). Les personnes sans cette capacité (bébé, enfant) n'ont pas d'état affectif. 【HYP】 sur la forme linéaire.

### 7.3 Émotions, stress, humeur

Avec décroissance λ_e : joy ← (1−λ_e)joy + λ_e·max(0,d)·r ; sadness ← … + λ_e·max(0,−d)·r·(1−c) ; fear ← … + λ_e·p·(1−c) ; anger ← … + λ_e·taux de refus du foyer·max(0,−d). Stress S ← clip((1−δ_S)S + κ_i·max(0,−d)(1−c), 0, 1), κ_i = sensibilité au stress du profil. Humeur ← (1−μ)humeur + μ·d. L'affect ne produit aucune utilité et n'entre pas dans le critère de décision.

### 7.4 Modulation — profil cognitif effectif

H_eff = ⌊H(1 − m_H·S)⌋ ; M_eff = max(1, round(M(1 − m_M·S))) ; seuils d'acceptation multipliés par 1 − m_θ·sadness ; β_eff = β(1 − m_β·S) ; engagement × (1 − m_c·anger) ; λ_eff = λ(1 + m_λ·fear). Variante sigmoïde pour le test de robustesse. Si la boucle B3 est coupée, le profil effectif est le profil de base. 【HYP】

### 7.5 Rétroaction santé

Santé ← clip(santé − h_s·max(0, S_{t−1} − S0), 0, 1), puis capacité de travail inchangée dans sa forme (V1). Fermeture de boucle : stress → santé → capacité → revenu → contrainte.

### 7.6 Régime de sphères séparées

Si le stress moyen des propriétaires du budget commun dépasse s* pendant k_enter mois, le foyer passe en sphères séparées : la mise en commun est réduite, chaque parent finance un ensemble de besoins attribué par donnée (père : logement, sécurité ; mère : alimentation, santé, éducation) à partir de sa part du pot et de son portefeuille ; la même fonction d'allocation est appliquée par sphère. Retour au régime normal sous s* − hystérésis pendant k_exit mois. Les paiements d'un parent au bénéfice d'un autre membre sont comptés comme transferts intra-ménage en nature.

### 7.7 Décisions sous risque (CPT)

Quatre décisions binaires (contracter un prêt, adhérer à une mutuelle de santé, maintenir un adolescent à l'école, adhérer à une tontine), prises par le parent de poids maximal ; fonction de valeur v(x) = x^α / −λ_eff(−x)^α, pondération w(p) de Tversky & Kahneman (γ⁺ = 0,61, γ⁻ = 0,69) ; point de référence = niveau de consommation de référence tiré de la mémoire ; flux futurs actualisés par δ. Si la CPT est désactivée, la même décision est prise à valeur espérée neutre au risque. Détails et paramètres : `specs/30_SPEC_V3_AFFECTIVE_POPULATION.md` §7.

### 7.8 Génération de population

Voir §5 et `specs/30_SPEC_V3_AFFECTIVE_POPULATION.md` §3 (gabarits, jitter, distributions, sources, repli).

### 7.9 Protocole de calibration (résumé)

1. Initialisation (population synthétique) et paramétrage direct (paramètres observables) depuis les données. 2. Criblage de Morris sur le registre des paramètres → environ huit paramètres libres de traitement « calibrer » (jamais une variable de traitement d'une expérience). 3. Recherche en grille / LHS sur ces paramètres, perte = moyenne des NRMSE de P1–P3 sur la population (N = 1 000, 10 réplications par candidat). 4. Validation sur P4–P6, jamais utilisés dans la perte (garde-fou logiciel). 5. Sobol autour du point calibré pour la robustesse. Une expérience jumelle (cibles générées par un jeu de paramètres connu) vérifie préalablement que la procédure retrouve des paramètres connus. Détails : `specs/40_SPEC_VALIDATION_CALIBRATION.md`.

### 7.10 Repère d'efficacité (analyse ex post)

Hors simulation : pour chaque foyer et pas, l'allocation maximisant Σ_i w_i Σ_k π_ik log(ε + n̂_ik) sous le même budget sert de repère ; l'écart relatif de bien-être entre cette allocation et celle du modèle est rapporté (E8). Ce repère n'agit jamais sur la dynamique.

## 8. Expériences associées à la V3

E4 (boucle affective ; enfermement défini opérationnellement avant exécution, aucun résultat prédit), E5 (aversion aux pertes), E7 (population, validation principale), E8 (efficacité), E9 (dégradation cognitive contrôlée). Plans détaillés : `specs/50_SPEC_EXPERIMENTS.md`.

## 9. Limites propres à la V3 (à reprendre au Chap. 9)

- Les formes de l'appraisal, de la modulation et de la rétroaction santé sont des hypothèses ; l'expérience émotionnelle simulée n'est pas validable.
- Les foyers n'interagissent pas : pas d'effets de réseau ni de quartier.
- Cohorte fixe : ni naissances, ni décès, ni formation de ménages (hors départ optionnel du jeune adulte).
- La validation porte sur des patterns réservés et non sur un hors-échantillon temporel.
- La règle d'imputation NTA suppose un chef de ménage unique, hypothèse discutable dans le contexte sénégalais.
