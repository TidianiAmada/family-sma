# ROADMAP — Mémoire SMA Famille × NTA
## Feuille de route architecturale et technique

**Mémoire :** « La cellule familiale comme système multi-agents : architecture cognitive hétérogène et mesure des conséquences socio-économiques via les National Transfer Accounts »
**Auteur :** Cheikh Ahmadou Tidiani TOP — Master Data Science & IA, Université Iba Der Thiam de Thiès
**Date :** 11 septembre 2026 — **révisé le 17 septembre 2026** (v2)


---

# 2. CE QUE NOUS RETENONS DÉFINITIVEMENT

Ces décisions sont fermées. Elles ne seront rouvertes que si une expérience les contredit.

| # | Décision | Provenance | Fondement |
|---|---|---|---|
| D1 | **Un seul `PersonAgent` générique**, l'hétérogénéité vient d'un `CognitiveProfile` chargé depuis une configuration externe | 【DOC】 confirmé 【LIT】 | C'est le cœur intellectuel de ton sujet ; pratique établie en simulation sociale (LARA, Consumat) |
| D2 | **Les NTA sont une couche de mesure ex post**, en lecture seule sur l'état des agents. Ils ne fournissent aucun mécanisme comportemental | 【LIT】 | Le manuel ONU impute les transferts privés comme résidu comptable, pas comme décision ✅ |
| D3 | **Le moteur de décision est du satisficing à seuil d'aspiration adaptatif**, pas une fonction d'utilité multicritère scalaire | 【RECO】 fondé 【LIT】 | Simon (1955) ; et une utilité scalaire annulerait le rôle de l'hétérogénéité cognitive |
| D4 | **Pas de HTN, pas de GOAP** | 【RECO】 | Redondance avec la bibliothèque de plans BDI ; GOAP n'a pas de source évaluée par les pairs |
| D5 | **ACT-R, SOAR, CLARION restent en état de l'art** ; emprunt unique de l'activation décroissante de la mémoire | 【RECO】 | Décalage d'échelle temporelle (ms vs mois) et coût prohibitif |
| D6 | **L'affect ne produit pas d'utilité** : il module les paramètres du processus de décision | 【RECO】 fondé 【LIT】 | C'est la réponse à ta sous-question « dur vs mou » ; appuyée par EMA et Mani et al. (2013) |
| D7 | **Les modèles collectifs du ménage ne sont pas implémentés comme mécanisme** : ils servent de cadre théorique et de repère de comparaison | 【RECO】 | Ils supposent l'efficacité Pareto, incompatible avec des agents à rationalité limitée |
| D8 | **Python + Mesa 3**, une seule plateforme pour tout le mémoire | 【DOC】 confirmé | Agents.jl reste une perspective documentée par benchmarks publiés, pas une réimplémentation |
| D9 | **ODD construit en parallèle du code, version par version** | 【LIT】 | Grimm et al. (2020) ✅ |
| D10 | **La stratégie de validation est le Pattern-Oriented Modeling**, avec séparation stricte entre patterns de calibration et patterns de validation | 【RECO】 fondé 【LIT】 | Grimm et al. (2005) ; la séparation est une exigence méthodologique, pas un raffinement |

| D11 | **Pas de temps de la simulation** |  mensuel  【RECO】 mensuel — la plupart des flux NTA sont annuels ou mensuels, et un pas hebdo multiplie par 4 le coût sans gain comptable |
| D12 | **Horizon simulé** | variables : 10 ans / 20 ans / cycle de vie complet | 20 ans (par défaut) : suffisant pour voir les enfants changer de position NTA, insuffisant pour la retraite (à assumer) |
| D13 | **Le jeune adulte peut-il quitter le foyer ?** | Variables: Oui / non | Change la structure de l'Agent-Foyer. 
| Q5 | **Démographie** | Cohorte fixe / naissances-décès | Phase 2 | 【RECO】 cohorte fixe, vieillissement seul. Introduire la fécondité fait basculer dans la microsimulation démographique, autre métier |
| Q6 | **Source de calibration** | EHCVM Sénégal / profils NTA / synthétique | Phase 1 | Dépend de l'accès aux données. Voir §13 |
| Q7 | **Question de recherche n°5 (calibration)** | Perspective / sous-question / objectif méthodo / contribution | Phase 1 | Mon verdict argumenté en §13.3 — mais tu décides |
| Q8 | **Application web** | FastAPI + React/ ou autres meilleur framework | 
| Q9 | **Unité monétaire et prix** | FCFA calibrés  | 【RECO】 FCFA si EHCVM accessible, sinon unités normalisées avec conversion explicite |


# 7. AUDIT DE L'ARCHITECTURE PROPOSÉE

Tu m'as demandé d'auditer ton pipeline plutôt que de l'accepter. Voici les cinq problèmes que j'y vois.

### Ton pipeline actuel

```
ENVIRONMENT → PERCEPTION → OBJECTIVE STATE → COGNITIVE APPRAISAL → AFFECTIVE STATE
→ COGNITIVE STATE (Beliefs, Desires, Intentions, Memory) → COGNITIVE MODE / DECISION
→ PLAN / PLAN LIBRARY → ACTION → HOUSEHOLD COORDINATION → NTA ACCOUNTING
→ OUTPUTS → FEEDBACK
```

### Problème 1 — l'appraisal est placé avant les croyances et les buts. C'est circulaire. 【LIT】

**Le fait :** en théorie de l'appraisal (Lazarus, OCC), évaluer un événement, c'est l'évaluer **relativement à des buts**. L'appraisal a besoin des désirs et des croyances pour s'exécuter. Dans ton pipeline, il s'exécute avant qu'ils n'existent.

**Conséquence pratique :** tu ne pourras pas coder `appraisal()` — il lui manquera ses entrées, et tu finiras par aller chercher les buts « ailleurs », ce qui cassera la lisibilité de l'architecture.

**Correction 【RECO】 :** l'état cognitif (croyances, désirs, mémoire) est **persistant** et se met à jour *avant* l'appraisal. L'appraisal lit le nouvel état objectif et les buts existants, et produit de l'affect. L'affect agit ensuite sur la **décision**, pas sur les croyances.

### Problème 2 — quatre « modes cognitifs » dont deux sont le même. 【RECO】

Tu listes : *Reactive, Satisficing, Deliberative, Risk-sensitive*.

Or « réactif » = satisficing avec `max_alternatives = 1` et `planning_horizon = 0`. Et « risk-sensitive » n'est pas un mode de décision : c'est un **traitement particulier appliqué à certaines décisions** (celles qui sont des loteries), quel que soit le mode.

**Correction 【RECO】 :** deux paramètres continus (`max_alternatives`, `planning_horizon`) produisent le continuum réactif→délibératif sans branchement. Le traitement du risque est une **sous-routine appelée sur quatre décisions identifiées**, pas un mode. Tu passes de 4 branches à 1 fonction paramétrée — et c'est aussi l'expression la plus pure de ton principe « hétérogénéité par paramétrage, pas par duplication ».

### Problème 3 — la mémoire n'est pas une étape du pipeline. 【RECO】

Tu la places dans `COGNITIVE STATE`, mais elle est lue par la perception (qu'est-ce que je reconnais ?), par le point de référence (à quoi je compare ?), et par l'évaluation des plans (qu'est-ce qui a marché ?). Elle est écrite par l'action et par l'appraisal.

**Correction :** la mémoire est un **service transversal**, pas une étape séquentielle. Représente-la à côté du pipeline, avec des flèches de lecture/écriture. Ce détail de représentation t'évitera une mauvaise décomposition en modules.

### Problème 4 — l'ordonnancement foyer/individu est inversé. 【RECO】 **C'est le problème le plus sérieux.**

Dans ton pipeline, `ACTION` précède `HOUSEHOLD COORDINATION`. Mais un membre ne peut pas consommer avant que le foyer ait alloué le budget. Si les agents agissent d'abord et que le foyer arbitre ensuite, soit tu autorises des dépenses non financées, soit tu dois annuler des actions déjà exécutées.

**Correction 【RECO】 — le pas de temps doit avoir trois temps :**

```
TEMPS 1  — chaque membre perçoit, met à jour son état, forme ses demandes (priorisées)
TEMPS 2  — le foyer collecte les demandes, applique sa règle d'allocation
           sous contrainte de budget, notifie les allocations
TEMPS 3  — chaque membre agit dans la limite de son allocation ; puis la couche NTA
           enregistre l'ensemble des flux du pas
```

C'est exactement ce que la section « process overview and scheduling » de l'ODD sert à expliciter. **Traite cela en Phase 2, pas en Phase 3 :** un ordonnancement mal choisi est très coûteux à corriger une fois le code écrit.

### Problème 5 — « FEEDBACK » n'est pas une étape, et le nommer ainsi masque ce qui compte. 【RECO】

Un pipeline qui se termine par « FEEDBACK » ne dit rien. **Nomme les boucles.** Il y en a trois dans ton système, et chacune correspond à une question scientifique :

| Boucle | Chemin | Question qu'elle permet de poser | Version |
|---|---|---|---|
| **B1 — économique** | action → état économique → besoins → décision | La contrainte budgétaire suffit-elle à produire les trajectoires de dette observées ? | V1 |
| **B2 — cognitive** | résultat d'action → mémoire → seuil d'aspiration → décision | L'adaptation des aspirations produit-elle un ajustement réaliste au choc ? | V2 |
| **B3 — affective** | contrainte → appraisal → affect → paramètres cognitifs → décision → contrainte | Cette boucle peut-elle produire un enfermement endogène ? 【HYP】 | V3 |

**B3 est la boucle qui porte ta sous-question « dur vs mou ».** Elle mérite d'être nommée, schématisée et testée explicitement (expérience E4).

### Pipeline corrigé 【RECO】

```
                              ┌─────────────┐
                              │ ENVIRONMENT │
                              └──────┬──────┘
      ╔═══════════════════ TEMPS 1 : perception & demande ═══════════════════╗
      ║        ┌──────────────┐                                              ║
      ║        │  PERCEPTION  │◄─── filtre borné par max_alternatives        ║
      ║        └──────┬───────┘                                    ┌───────┐ ║
      ║               ▼                                     ┌─────►│MÉMOIRE│ ║
      ║   ┌────────────────────────┐                        │      │(service│║
      ║   │ ÉTAT OBJECTIF          │                        │      │transv.)│║
      ║   │ Economic · Physical    │                        │      └───┬───┘ ║
      ║   └──────────┬─────────────┘                        │          │     ║
      ║              ▼                                      │          │     ║
      ║   ┌────────────────────────┐                        │          │     ║
      ║   │ ÉTAT COGNITIF          │◄───────────────────────┴──────────┘     ║
      ║   │ Beliefs · Desires      │  (persistant, mis à jour AVANT          ║
      ║   │ Intentions en cours    │   l'appraisal — correction n°1)         ║
      ║   └──────────┬─────────────┘                                         ║
      ║              ▼                                                       ║
      ║   ┌────────────────────────┐   [V3]                                  ║
      ║   │ APPRAISAL              │   primaire : pertinence, désirabilité   ║
      ║   │ (évalue vs. desires)   │   secondaire : contrôlabilité =         ║
      ║   └──────────┬─────────────┘     f(épargne, actifs, soutien foyer)   ║
      ║              ▼                                                       ║
      ║   ┌────────────────────────┐   [V3]                                  ║
      ║   │ ÉTAT AFFECTIF          │   4–5 émotions + humeur                 ║
      ║   └──────────┬─────────────┘                                         ║
      ║              ▼   ⚠ ne produit AUCUNE utilité                        ║
      ║   ┌──────────────────────────────────────┐                           ║
      ║   │ PROFIL COGNITIF EFFECTIF (transitoire)│                          ║
      ║   │ = CognitiveProfile × modulation       │                          ║
      ║   │   (horizon, alternatives, aspiration) │                          ║
      ║   └──────────┬───────────────────────────┘                           ║
      ║              ▼                                                       ║
      ║   ┌────────────────────────┐                                         ║
      ║   │ MOTEUR DE DÉCISION     │  un seul mécanisme paramétré            ║
      ║   │ satisficing paramétré  │  + sous-routine risque [V3]             ║
      ║   └──────────┬─────────────┘  (correction n°2)                       ║
      ║              ▼                                                       ║
      ║   ┌────────────────────────┐                                         ║
      ║   │ DEMANDES PRIORISÉES    │──────────┐                              ║
      ║   └────────────────────────┘          │                              ║
      ╚═══════════════════════════════════════│══════════════════════════════╝
                                              ▼
      ╔═══════════════════ TEMPS 2 : arbitrage du foyer ═════════════════════╗
      ║   ┌──────────────────────────────────────────────────────┐           ║
      ║   │ HOUSEHOLD AGENT                                      │           ║
      ║   │  collecte des demandes → règle d'allocation sous     │           ║
      ║   │  contrainte de budget → poids de négociation [V2]    │           ║
      ║   │  → dette collective → notification des allocations   │           ║
      ║   │  → régime dégradé « sphères séparées » [V3]          │           ║
      ║   └──────────────────────────┬───────────────────────────┘           ║
      ╚══════════════════════════════│═══════════════════════════════════════╝
                                     ▼
      ╔═══════════════════ TEMPS 3 : action & comptabilité ══════════════════╗
      ║   ┌────────────────────────┐                                         ║
      ║   │ PLAN LIBRARY [V2]      │  sélection de plan + replanification    ║
      ║   └──────────┬─────────────┘                                         ║
      ║              ▼                                                       ║
      ║   ┌────────────────────────┐                                         ║
      ║   │ ACTION ENGINE          │  travailler, consommer, épargner,       ║
      ║   └──────────┬─────────────┘  se soigner, étudier, se reposer        ║
      ║              ▼                                                       ║
      ║   ┌──────────────────────────────────────────────────────┐           ║
      ║   │ COUCHE NTA (lecture seule, ex post)                   │          ║
      ║   │  LCD(a) = C(a) − Yl(a)                                │          ║
      ║   │  C−Yl = τ⁺−τ⁻ + (Ya − S)                              │          ║
      ║   │  transferts_comportementaux | transferts_NTA_imputés  │          ║
      ║   │  tests de bouclage comptable                          │          ║
      ║   └──────────────────────────┬───────────────────────────┘           ║
      ║                              ▼                                       ║
      ║                     ┌─────────────────┐                              ║
      ║                     │ OBSERVATIONS    │ DataCollector                ║
      ║                     └─────────────────┘                              ║
      ╚══════════════════════════════════════════════════════════════════════╝

   Boucles explicites :  B1 économique (V1) · B2 cognitive (V2) · B3 affective (V3)
```

---

# 8. CLASSIFICATION DE TOUS LES COMPOSANTS

Tu as demandé quatre catégories. Les voici, appliquées à l'intégralité des composants évoqués dans tes documents.

### CORE — indispensable, sans quoi le mémoire ne répond pas à sa question

| Composant | Version | Pourquoi il est core |
|---|---|---|
| `PersonAgent` générique + `CognitiveProfile` externe | V1 | C'est le sujet du mémoire |
| `EconomicState` (Yl, C, actifs, dette, épargne) | V1 | Sans lui, pas de NTA |
| `PhysicalState` minimal (santé, capacité de travail) | V1 | Nécessaire aux chocs et aux arbitrages |
| Besoins à seuils de satisfaction | V1 | Moteur de l'autonomie de l'agent |
| Moteur de décision satisficing paramétré | V1 | Le mécanisme qui donne un sens à l'hétérogénéité |
| `HouseholdAgent` avec règle d'allocation | V1 | Le lieu des transferts privés |
| Couche NTA complète + tests de bouclage | V1 | La moitié économique du sujet |
| `DataCollector` + reproductibilité par seed | V1 | Sans quoi aucun résultat n'est vérifiable |
| ODD (V0 → V3) | toutes | Documentation et conception |
| Croyances / désirs / intentions persistantes | V2 | Ce qui distingue « délibératif » de « réactif » |
| Mémoire bornée à activation décroissante | V2 | Sert le seuil d'aspiration et le point de référence |
| Bibliothèque de plans + replanification | V2 | Remplace HTN |
| Analyse de sensibilité globale | V2 | Rempart contre l'arbitraire des paramètres |
| POM sur ≥ 2 patterns | V2 | Stratégie de validation |
| Population de foyers | V3 | **Condition de la validation contre un profil NTA** |

### OPTIONNEL — améliore le mémoire, entre seulement si une question l'exige et si le temps le permet

| Composant | Version | Question qu'il permet de trancher | Coût |
|---|---|---|---|
| Actualisation quasi-hyperbolique β-δ | V2 | Le présent-biais explique-t-il la trajectoire de dette ? | **Très faible** — à retenir en priorité |
| Poids de négociation variables | V2 | Le pouvoir de négociation modifie-t-il l'allocation ? | Faible |
| NTTA (travail domestique valorisé) | V2 | Le travail non rémunéré change-t-il le profil NTA du foyer ? | Moyen |
| Appraisal simplifié + 4–5 émotions | V3 | La boucle B3 produit-elle un enfermement endogène ? | Moyen — **c'est ta sous-question centrale** |
| Régime « sphères séparées » | V3 | Le stress peut-il rompre la coordination du foyer ? | Faible |
| CPT sur 4 décisions binaires | V3 | L'aversion aux pertes modifie-t-elle la décision de crédit ? | Faible |
| Repère d'efficacité collective | V3 | De combien la rationalité limitée éloigne-t-elle de l'optimum ? | Moyen |
| Calibration sur données EHCVM | V3 | (voir §13) | Élevé |

### ÉTAT DE L'ART — cité, comparé, jamais implémenté

ACT-R · SOAR · CLARION · HTN (SHOP2 et suivants) · GOAP · OCC dans ses 22 types · MAUT / utilité multi-attributs · modèle collectif de Chiappori comme mécanisme d'optimisation · Nash bargaining résolu formellement · EURACE et les modèles macro agent-based · microsimulation dynamique complète.

**Chacun d'eux doit apparaître dans le Chapitre 2 avec une phrase disant pourquoi il n'est pas retenu.** Les justifications négatives valent autant que les positives.

### EXTENSION FUTURE — Chapitre 9, perspectives

Apprentissage par renforcement des agents · HTN de premier principe pour les plans conditionnels longs · réseaux sociaux inter-foyers · spatialité et effets de quartier · démographie endogène (fécondité, mortalité, formation des ménages) · réimplémentation Agents.jl · calibration bayésienne / ABC · migration · politique publique optimale.

---

# 9. ARCHITECTURE LOGICIELLE

### Principe directeur 【RECO】

**Un seul point de variation polymorphe. Tout le reste est de la donnée.**

C'est la traduction logicielle de ton principe scientifique. Si tu as trois hiérarchies de classes, tu as trahi le principe « hétérogénéité par paramétrage ». Si tu en as une seule — le moteur de décision — et que tout le reste varie par configuration, tu peux le défendre en soutenance en une phrase.

### Structure de projet proposée

Ta proposition est bonne. J'y apporte trois modifications : séparer `config/` (les profils cognitifs ne sont pas du code), séparer `tests/` (ils sont un livrable, pas un accessoire), et ajouter `odd/` (le document ODD vit avec le code et se versionne avec lui).

```
family_abm/
├── config/                  ← les profils, pas du code
│   ├── cognitive_profiles.yaml      (6 profils : bébé → parent)
│   ├── economic_params.yaml         (prix, taux, revenus)
│   ├── household_rules.yaml         (règles d'allocation, poids)
│   └── scenarios/                   (baseline, chômage, maladie, allocation)
├── src/family_abm/
│   ├── agents/
│   │   ├── person.py                PersonAgent — coquille mince
│   │   ├── household.py             HouseholdAgent
│   │   └── states.py                Economic / Physical / Cognitive / Affective
│   ├── decision/                    ← LE point de variation
│   │   ├── engine.py                interface unique decide(percept) -> Action
│   │   ├── satisficing.py           moteur paramétré (couvre réactif→délibératif)
│   │   ├── risk.py                  sous-routine CPT [V3]
│   │   └── plans.py                 bibliothèque de plans + replanification [V2]
│   ├── cognition/
│   │   ├── memory.py                service transversal
│   │   ├── appraisal.py             [V3]
│   │   └── modulation.py            CognitiveProfile → EffectiveCognitiveProfile [V3]
│   ├── economy/
│   │   ├── actions.py               travailler, consommer, épargner, se soigner…
│   │   └── ledger.py                journal de flux — source unique de vérité
│   ├── nta/
│   │   ├── accounts.py              LCD, transferts, réallocations
│   │   ├── imputation.py            la règle du manuel ONU (pour comparaison)
│   │   └── invariants.py            tests de bouclage comptable
│   ├── model/
│   │   ├── family_model.py          le modèle Mesa, ordonnancement en 3 temps
│   │   └── collectors.py            DataCollector
│   └── analysis/
│       ├── patterns.py              calcul des patterns POM
│       ├── sensitivity.py           interface SALib
│       └── figures.py
├── odd/                     ← le document ODD, versionné avec le code
│   ├── ODD_v0_conceptual.md
│   ├── ODD_v1_economic.md
│   └── ODD_v2_cognitive.md
├── tests/
│   ├── test_invariants.py           conservation des flux
│   ├── test_nta_identities.py       identités comptables
│   ├── test_reproducibility.py      même seed → même trajectoire
│   └── test_decision.py
├── experiments/
│   ├── E1_baseline.py … E9_scale.py
│   └── results/                     Parquet, jamais commités
└── notebooks/                       exploration uniquement, jamais de logique
```

### Responsabilités — et le moment où chaque composant devient nécessaire

| Composant | Responsabilité unique | Devient nécessaire en |
|---|---|---|
| `PersonAgent` | Porter l'identité et orchestrer son propre pas. **Ne contient aucune logique métier** | V1 |
| `EconomicState` | Détenir les grandeurs monétaires. Structure de données passive | V1 |
| `PhysicalState` | Santé et capacité de travail | V1 |
| `Ledger` | **Enregistrer tout mouvement de valeur.** Source unique de vérité pour les NTA | V1 |
| `DecisionEngine` | Transformer une perception en action. Seul point polymorphe | V1 |
| `HouseholdAgent` | Collecter les demandes, allouer sous contrainte, porter la dette collective | V1 |
| `NTACalculator` | Calculer LCD, transferts, réallocations à partir du `Ledger` | V1 |
| `Invariants` | Vérifier les identités à chaque pas. **Doit pouvoir faire échouer une simulation** | V1 |
| `CognitiveState` | Croyances, désirs, intentions en cours | V2 |
| `Memory` | Service de rappel avec activation décroissante et capacité bornée | V2 |
| `PlanLibrary` | Sélectionner un plan, détecter l'échec, replanifier | V2 |
| `AffectiveState` | Porter 4–5 émotions et une humeur | V3 |
| `AppraisalEngine` | Produire l'affect à partir de l'écart buts/état | V3 |
| `ModulationEngine` | Produire l'`EffectiveCognitiveProfile` | V3 |
| `CalibrationEngine` | Piloter les runs, comparer aux cibles, ajuster | V3 |

### Trois décisions techniques qui comptent 【RECO】

**1. Le `Ledger` comme source unique de vérité.** Ne calcule jamais les NTA à partir des états d'agents à un instant donné : calcule-les à partir d'un journal de mouvements. Chaque action qui déplace de la valeur écrit une ligne (source, destination, montant, catégorie, pas de temps). Les identités NTA deviennent alors des agrégations sur ce journal, et les tests de bouclage deviennent triviaux. **Sans journal, tu passeras des jours à chercher pourquoi le foyer perd 300 FCFA au pas 47.**

**2. Configuration externe, validée au chargement.** Les profils cognitifs vivent en YAML, chargés dans des structures immuables validées (type, bornes). Cela te donne gratuitement : la reproductibilité, la traçabilité des expériences, et la capacité de lancer une analyse de sensibilité sans toucher au code.

**3. Sorties en Parquet, pas en CSV.** Une analyse de sensibilité globale sur 25 paramètres produit des centaines de runs. Le format colonnaire divise par cinq à dix le volume et le temps de lecture, et se lit directement avec pandas ou DuckDB.

---

# 10. FEUILLE DE ROUTE ODD

### Pourquoi l'ODD ne peut pas être écrit à la fin 【LIT】

L'ODD (Grimm et al. 2020) impose sept sections dans un ordre fixe : Purpose · Entities, state variables and scales · Process overview and scheduling · Design concepts · Initialization · Input data · Submodels.

Remplir ces sections **avant** de coder t'oblige à répondre à des questions que le code te forcerait à trancher au pire moment. Trois exemples concrets tirés de ton propre projet :

- *« Process overview and scheduling »* t'aurait fait découvrir le problème d'ordonnancement foyer/individu (§7, problème 4) **avant** d'écrire une ligne.
- *« Entities, state variables and scales »* te force à fixer Q2 (pas de temps) et Q3 (horizon) explicitement.
- *« Design concepts »* te demande si tes agents apprennent, ce qu'ils perçoivent, ce qui est stochastique — des questions que tu aurais tranchées implicitement et mal.

### Les quatre versions de l'ODD

| Version | Moment | Contenu | Devient |
|---|---|---|---|
| **ODD-V0** | Phase 2, avant tout code | Purpose · Entities (les 7 agents) · Scales (Q2, Q3) · Process overview (les 3 temps) · **Design concepts complets** · Initialization (esquisse) | Le brouillon du **Chapitre 3** |
| **ODD-V1** | Phase 3, en parallèle du code | + State variables exhaustives · Input data · **Submodels économiques** (revenu, consommation, épargne, dette, allocation, NTA) | Le **Chapitre 5** section économique |
| **ODD-V2** | Phase 5 | + Submodels cognitifs (satisficing, mémoire, plans) · mise à jour des design concepts (adaptation, objectifs, prédiction) | Le **Chapitre 5** section cognitive |
| **ODD-V3** | Phase 7–9 | + Submodels affectifs · protocole de calibration · données d'entrée réelles | Le **Chapitre 5** complet + annexe |

### Comment l'ODD devient directement de la rédaction

| Section ODD | Devient |
|---|---|
| Purpose | Chapitre 1, §problématique (reformulée) |
| Entities, state variables, scales | **Chapitre 3, §3.2** — presque sans réécriture |
| Process overview and scheduling | **Chapitre 3, §3.3** + le schéma du pipeline |
| Design concepts | **Chapitre 3, §3.1** — c'est la justification conceptuelle |
| Initialization | Chapitre 5, §5.3 et Chapitre 6, §6.1 |
| Input data | Chapitre 4, §4.6 et Chapitre 6, §6.3 |
| Submodels | **Chapitre 4 (économiques) + Chapitre 5 (cognitifs)** |

**Effet attendu 【RECO】 :** en écrivant sérieusement l'ODD à chaque version, tu arrives en Phase 12 avec environ 60 % des Chapitres 3, 4 et 5 déjà écrits. C'est l'économie la plus importante de toute cette roadmap — de l'ordre de trois à quatre semaines de rédaction.

### Discipline 【RECO】

- L'ODD est un fichier Markdown dans le dépôt, versionné avec le code.
- **Règle dure : aucun sous-modèle n'est codé avant d'être décrit dans l'ODD.** Si tu ne peux pas l'écrire en prose, tu ne l'as pas compris.
- Quand le code diverge de l'ODD, c'est l'ODD qu'on corrige **dans le même commit**.

---

# 11. VERSION V1 — BASELINE ÉCONOMIQUE

**Objectif scientifique :** établir qu'un modèle multi-agents de foyer peut produire des flux économiquement cohérents et reproduire la signature du déficit du cycle de vie. **Rien de plus.**

### Périmètre

**Inclus** 【DOC】 confirmé :

| Élément | Spécification |
|---|---|
| 6 `PersonAgent` | Père, mère, jeune adulte, adolescent, enfant, bébé |
| `CognitiveProfile` | Chargé depuis YAML — **même si en V1 seuls 2 paramètres agissent** (`max_alternatives`, `planning_horizon`) |
| `EconomicState` | Revenu du travail, consommation, actifs, dette, épargne |
| `PhysicalState` | Santé (0–1), capacité de travail |
| Besoins | 4 à 6 besoins avec seuil de satisfaction |
| Règles de décision | Satisficing paramétré, sans croyances ni plans |
| Actions | Travailler, consommer, épargner, se soigner, étudier |
| `HouseholdAgent` | Règle d'allocation à poids fixes, budget commun, dette collective |
| Couche NTA | LCD, transferts, réallocations, imputation selon la règle ONU |
| `Ledger` + invariants | Conservation des flux, testée à chaque pas |
| `DataCollector` | Séries individuelles et foyer |
| Reproductibilité | Seed explicite, même seed → même trajectoire |

**Exclus explicitement :** croyances, désirs, intentions · mémoire · planification · appraisal, émotions · Prospect Theory · apprentissage · poids de négociation variables · population de foyers.

### Références nécessaires pour la V1 — **trois seulement**

1. **UN NTA Manual (2013)** — la couche NTA
2. **Dossier méthodologique 1a + 1b** (ODD et checklists) — la méthode
3. **Simon (1955)** — le moteur de décision

*(Balke & Gilbert et Chiappori & Mazzocco servent la rédaction, pas la V1.)*

### Expérience E1

**Hypothèse :** un foyer à six membres, avec des règles économiques simples et une allocation à poids fixes, produit un profil de LCD dont le signe est correct par membre et dont les identités NTA bouclent.

- **Variables manipulées :** aucune (run de référence)
- **Variables contrôlées :** revenus parentaux, prix, seuils de besoin, poids d'allocation
- **Métriques :** LCD par membre, ratio dette/revenu du foyer, taux d'épargne, reste-à-vivre
- **Baseline :** elle-même — c'est la référence de tout le mémoire
- **Résultat attendu :** LCD > 0 pour bébé, enfant, adolescent ; LCD < 0 pour les parents ; bouclage comptable exact
- **Limites :** aucune prétention comportementale à ce stade

### Critères de sortie de la V1 — **contraignants**

Tous doivent être verts avant la Phase 5.

- [ ] Les identités NTA bouclent à ε près à chaque pas, sur 20 ans, pour 100 seeds différentes
- [ ] Aucune valeur monétaire ne disparaît : `somme(entrées) − somme(sorties) = Δactifs`
- [ ] La dette du foyer suit exactement l'équation de désépargne, sans divergence inexpliquée
- [ ] Même seed → trajectoire strictement identique
- [ ] Le signe du LCD est correct pour les six membres sur toute la période
- [ ] **L'ODD-V1 est écrit et cohérent avec le code**
- [ ] La suite de tests passe et couvre les invariants
- [ ] Un run de 20 ans s'exécute en moins de 5 secondes *(c'est le budget qui rend possible les 10 000 runs de l'analyse de sensibilité ultérieure — mesure-le dès maintenant)*

### Livrable mémoire

Chapitre 4 (§4.1–4.4) + Chapitre 5 (§5.1–5.3) + l'expérience E1 du Chapitre 6.

### Risques de la V1

| Risque | Signe précurseur | Parade |
|---|---|---|
| Sur-ingénierie prématurée | Tu écris une `Factory` avant d'avoir deux types à fabriquer | Un seul point polymorphe, tout le reste en données |
| Fuite comptable | Les invariants échouent « parfois » | Le `Ledger` en source unique ; échec dur, pas un avertissement |
| Paramètres implicites | Des nombres dans le code | Tout dans `config/`, rien en dur |
| Glissement de périmètre | Tu ajoutes « juste la mémoire » | Les critères de sortie ci-dessus sont une porte fermée |

---

# 12. VERSION V2 — COGNITIVE

**Objectif scientifique :** établir que l'architecture cognitive change les trajectoires économiques — et de combien.

### Périmètre ajouté

| Élément | Spécification | Statut |
|---|---|---|
| Croyances / désirs / intentions | BDI dégradé : croyances comme prédicats, désirs comme buts priorisés, **intentions persistantes** | CORE |
| Mémoire | Buffer borné, activation décroissante, alimente le seuil d'aspiration | CORE |
| Seuil d'aspiration adaptatif | Monte si succès facile, descend si échec répété | CORE |
| Bibliothèque de plans | Plans avec conditions de contexte + sous-buts + détection d'échec + replanification | CORE |
| `CognitiveProfile` pleinement actif | Les 6–8 paramètres agissent réellement | CORE |
| Actualisation β-δ | Naïf pour l'adolescent, sophistiqué pour les parents | **Optionnel, forte priorité** |
| Poids de négociation variables | Fonction du revenu relatif | Optionnel |
| NTTA | Valorisation du travail domestique | Optionnel |
| Analyse de sensibilité globale | Morris puis Sobol via SALib | CORE |

### Références supplémentaires pour la V2 — **quatre**

4. **Balke & Gilbert (2014)** — justification du choix d'architecture
5. **Adam & Gaudou (2016)** — BDI en simulation sociale
6. **Jager & Janssen, Consumat II (2012)** — commutation de mode
7. **ten Broeke et al. (2016)** — protocole de sensibilité

*(+ Laibson 1997 en consultation ponctuelle si tu actives β-δ.)*

### Expériences

**E2 — Réactif vs. délibératif**
- *Hypothèse* 【HYP】 : la persistance des intentions réduit la volatilité de la consommation et augmente le taux d'épargne, à revenus identiques.
- *Manipulé* : mode de décision (V1 vs V2). *Contrôlé* : tous les paramètres économiques, même seed.
- *Métriques* : écart-type de la consommation mensuelle, taux d'épargne moyen, ratio dette/revenu terminal.
- *Limites* : l'écart mesuré dépend de la bibliothèque de plans, qui est un choix de conception — à discuter honnêtement.

**E3 — Présent-biais** *(si β-δ activé)*
- *Hypothèse* 【HYP】 : β < 1 augmente le ratio dette/revenu et réduit le niveau d'éducation atteint par les enfants.
- *Manipulé* : β ∈ {1,0 ; 0,9 ; 0,7 ; 0,5}. *Contrôlé* : δ, revenus, prix.

**E6 — Foyer unitaire vs. non unitaire**
- *Design repris de Beal Cohen et al. (2021)* 【LIT】.
- *Hypothèse* 【HYP】 : sous contrainte budgétaire forte, l'allocation issue d'un foyer non unitaire diffère qualitativement de celle d'un foyer unitaire.
- *Manipulé* : mécanisme du foyer (unitaire / poids fixes / poids variables).
- *Métriques* : part de consommation par membre, scolarisation atteinte, écart au repère d'efficacité.

**E-SA — Analyse de sensibilité globale**
- Morris d'abord (criblage, peu coûteux) pour éliminer les paramètres sans influence, puis Sobol sur les 8–10 survivants.
- *Livrable* : le tableau des indices de sensibilité — **c'est une figure obligatoire du Chapitre 6.**

### Critères de sortie de la V2

- [ ] Tous les critères de la V1 restent verts (test de non-régression)
- [ ] E2 produit une différence mesurable et explicable — **ou une absence de différence, également rapportée**
- [ ] L'analyse de sensibilité identifie les paramètres influents et leur hiérarchie
- [ ] **Au moins deux patterns POM sont reproduits avec un seul jeu de paramètres**
- [ ] L'ODD-V2 est à jour
- [ ] Un run reste sous 15 secondes

### Livrable mémoire

Chapitre 3 complet · Chapitre 5 (§5.4–5.6) · Chapitre 6 (E2, E3, E6, E-SA) · première version du Chapitre 8.

**Point de bascule du calendrier.** La V2 validée est le socle du jalon de novembre. Si elle n'est pas verte à J27, le plan de repli du §22 s'applique : le mémoire s'arrête à la V2, avec les chapitres 7 et 9 traités en conception et en perspective plutôt qu'en expérimentation. Ce serait un mémoire complet et honnête — mais ce n'est pas la cible.

---

# 13. CALIBRATION, PATTERN-ORIENTED MODELING, VALIDATION

C'est la partie de ta demande où il y a le plus à clarifier. Je la traite en quatre temps.

## 13.1 Examen critique de ton schéma à trois niveaux

Ton intuition est **globalement correcte et bien construite**, mais elle confond trois opérations qui ont des statuts épistémiques différents. Voici la correction, point par point.

### A. « Est-ce bien de la calibration ? » — Non, pas entièrement. Ton niveau 1 n'en est pas.

| Ton niveau | Nom exact | Statut |
|---|---|---|
| Niveau 1 — initialisation (âge, composition, revenus, emploi) | **Génération de population synthétique** | Ce n'est **pas** de la calibration. C'est la construction de l'état initial |
| Niveau 2 — paramétrage (probabilités de transition, paramètres économiques) | **Paramétrage direct** (pour ce qui est observable) **+ calibration** (pour ce qui ne l'est pas) | **Deux choses distinctes que tu as fusionnées** |
| Niveau 3 — comparaison des sorties, ajustement | **Calibration indirecte** — et tu y as inclus la validation, ce qui est le point à corriger | Correct comme calibration, incorrect comme validation |

### B–E. Le découpage correct

| Opération | Définition | Sur quoi elle porte | Exemple dans ton modèle |
|---|---|---|---|
| **Initialisation** | Fixer l'état du système à t = 0 | Variables d'état | Âges, composition du foyer, revenu de départ, actifs initiaux |
| **Paramétrage direct** | Fixer des paramètres à partir d'une source externe, **sans faire tourner le modèle** | Paramètres observables | Prix, taux d'intérêt, profils de consommation par âge issus des NTA, probabilités de transition de santé issues d'enquêtes |
| **Calibration** | Ajuster des paramètres **non observables** pour que les sorties du modèle approchent des cibles | Paramètres comportementaux | Seuil d'aspiration, poids d'allocation, sensibilité au stress |
| **Validation** | Confronter le modèle à des cibles **qui n'ont pas servi à la calibration** | Le modèle entier | Comparer le profil de dette simulé à une cible non utilisée pour caler les seuils |
| **Analyse de sensibilité** | Mesurer l'influence de chaque paramètre sur les sorties | Paramètres | Indices de Sobol sur les 25 paramètres |
| **POM** | Stratégie consistant à exiger la reproduction simultanée de plusieurs patterns à des niveaux d'organisation différents | La structure **et** les paramètres | Signature du LCD + distribution dette/revenu + gradient de scolarisation |

### ⚠️ La correction la plus importante

**Tu ne peux pas calibrer et valider sur les mêmes cibles.** Si tu ajustes tes paramètres pour que le profil de LCD colle, puis que tu annonces « le modèle reproduit le profil de LCD », tu n'as rien validé : tu as constaté que l'optimisation a fonctionné. C'est le problème classique de sur-ajustement, et un jury informé le relèvera immédiatement.

**La parade 【RECO】 :** décide **avant** de calibrer quels patterns servent de cibles de calibration et lesquels sont mis de côté pour la validation. Écris cette répartition dans l'ODD et n'y touche plus.

Proposition :

| Pattern | Rôle |
|---|---|
| P1 — signature du LCD par âge | **Calibration** |
| P2 — profil du revenu du travail par âge | **Calibration** |
| P3 — profil de consommation par âge | **Calibration** |
| P4 — orientation et volume des transferts | **Validation** (non utilisé pour caler) |
| P5 — distribution dette/revenu entre foyers | **Validation** |
| P6 — distribution du reste-à-vivre / pauvreté | **Validation** |
| P7 — trajectoires intergénérationnelles | Exploratoire — ne pas en faire une cible |

### F–I. Réponses aux questions restantes

**F. Où intervient POM ?** À deux moments, et c'est ce qui le distingue d'une simple calibration :
1. **À la conception** (Phase 2) : les patterns que tu veux reproduire déterminent ce que le modèle doit contenir. Si tu veux reproduire un gradient de scolarisation par revenu, il faut une décision de scolarisation. POM est donc un **filtre de complexité** — il justifie ce que tu inclus *et* ce que tu exclus.
2. **À la validation** (Phase 9) : les patterns servent de cibles multiples et simultanées.

**G. Où intervient l'analyse de sensibilité ?** **Deux fois, et la première est celle qu'on oublie :**
- **Avant la calibration** : pour réduire la dimension. Avec 25 paramètres, une calibration directe est vouée à l'échec. Un criblage de Morris te dira que 8 comptent vraiment — tu ne calibres que ceux-là. **C'est ce qui rend la calibration réalisable.**
- **Après la calibration** : pour la robustesse. Les conclusions tiennent-elles quand on fait varier les paramètres autour de la valeur calibrée ?

**H. Où intervient l'ajustement / optimisation de paramètres ?** C'est le mécanisme *interne* de la calibration. Trois niveaux de sophistication, par coût croissant :
1. **Recherche en grille sur peu de paramètres** — suffisant pour un Master 【RECO】
2. Minimisation d'une distance simulée (simulated minimum distance)
3. Calibration bayésienne / ABC / méta-modèle — **hors périmètre, à mettre en perspective**

**I. Faut-il plusieurs patterns simultanément ?** **Oui, et c'est l'argument central de POM.** Un modèle à 25 paramètres reproduit n'importe quel pattern unique — cela ne démontre rien. Trois ou quatre patterns simultanés, à des niveaux d'organisation différents (individu, foyer, population), contraignent fortement la structure. 【LIT】 Grimm et al. (2005). **Trois à quatre suffisent ; sept serait de l'affichage.**

## 13.2 Ton schéma conceptuel — corrigé

Ton schéma est **scientifiquement correct dans son ossature.** Il lui manque trois éléments.

```
                    DONNÉES OBSERVÉES
              (EHCVM, profils NTA, ANSD)
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
  INITIALISATION    PARAMÉTRAGE DIRECT   CHOIX DES PATTERNS   ◄── AJOUT 1
  (population       (paramètres           │                        POM intervient
   synthétique)      observables)         ├── set CALIBRATION      dès la conception,
        │                  │              └── set VALIDATION       et les deux sets
        │                  │                       │               sont séparés ICI
        └──────────┬───────┘                       │               ◄── AJOUT 2
                   ▼                               │
        ┌──────────────────────┐                   │
        │ ANALYSE DE SENSIBILITÉ│ ◄── AJOUT 3 : réduit 25 paramètres
        │ (criblage de Morris)  │     à ~8 calibrables. Sans cette étape,
        └──────────┬───────────┘     la calibration est infaisable
                   ▼
        ┌──────────────────────┐
        │ PARAMÈTRES LIBRES    │
        │ (~8 seulement)       │
        └──────────┬───────────┘
                   ▼
             ┌───────────┐
        ┌───►│ SIMULATION│
        │    └─────┬─────┘
        │          ▼
        │   ┌──────────────┐
        │   │ PATTERNS     │
        │   │ SIMULÉS      │
        │   └──────┬───────┘
        │          ▼
        │   ┌──────────────────────────┐
        │   │ COMPARAISON au set        │
        │   │ CALIBRATION (P1,P2,P3)    │
        │   └──────┬───────────────────┘
        │          ▼
        │   ┌──────────────┐
        └───┤ AJUSTEMENT   │  recherche en grille
            └──────────────┘
                   │ (convergence)
                   ▼
        ┌──────────────────────────────────┐
        │ VALIDATION sur le set VALIDATION  │
        │ (P4, P5, P6) — JAMAIS utilisé     │
        │ pour l'ajustement                 │
        └──────────────┬───────────────────┘
                       ▼
        ┌──────────────────────────────────┐
        │ ANALYSE DE SENSIBILITÉ POST-CALIB.│
        │ les conclusions sont-elles robustes│
        │ autour du point calibré ?         │
        └──────────────────────────────────┘
```

**Une réserve honnête sur « validation out-of-sample » 【RECO】 :** dans ton contexte, tu n'auras probablement pas de véritable hors-échantillon temporel (tu n'as pas deux périodes NTA sénégalaises indépendantes). Ce que tu peux réellement faire, c'est une **validation sur patterns retenus** — des patterns différents, issus des mêmes données, mais non utilisés pour la calibration. **C'est plus faible qu'un hors-échantillon, et tu dois l'écrire ainsi.** N'annonce pas une validation hors-échantillon que tu ne fais pas.

## 13.3 Ta cinquième question de recherche — verdict

> « Comment concevoir un mécanisme de calibration des paramètres d'un système multi-agents à partir des profils NTA, des statistiques officielles et d'autres sources de données ouvertes afin d'améliorer le réalisme des simulations socio-économiques ? »

### Verdict : **C — objectif méthodologique du chapitre Validation**, avec possibilité de passer en **B (sous-question officielle)** si et seulement si la V2 est validée dans les temps. **Pas D.** 【RECO】

**Pourquoi pas D (contribution expérimentale) :**
- Faire de la calibration une *contribution* suppose un apport méthodologique — un schéma d'estimation, un méta-modèle, une procédure nouvelle. C'est un domaine de recherche difficile, avec une littérature technique dense.
- Cela entre en concurrence directe, pour le même temps, avec ta contribution architecturale — qui est le cœur du sujet tel que tu l'as posé.
- **Risque de dilution :** un mémoire qui promet une architecture cognitive *et* une méthode de calibration risque de ne réussir ni l'une ni l'autre.

**Pourquoi pas A (simple perspective) :**
- Ce serait sous-vendre. Tu vas réellement faire de l'initialisation empirique et un calibrage simple ; il faut le revendiquer au niveau où tu le fais.

**Pourquoi C :** le chapitre Validation a besoin d'un objectif méthodologique explicite. Formulé ainsi, c'est exact, tenable et défendable :

> *« Dans quelle mesure les profils NTA nationaux et les enquêtes ménages disponibles permettent-ils d'initialiser et de calibrer un modèle multi-agents de foyer, et quelles limites cette démarche rencontre-t-elle ? »*

Remarque la différence : ta version promet de **concevoir un mécanisme** ; celle-ci demande **dans quelle mesure c'est possible et où sont les limites**. La seconde est une vraie question de recherche à laquelle un Master peut répondre — et une réponse négative ou nuancée y est un résultat valide.

### Ton hypothèse V1/V2/V3 — vérification

| Ton hypothèse | Verdict | Correction |
|---|---|---|
| V1 → préparation des données + initialisation réaliste | ✅ **Correct** | Nomme-le « génération de population synthétique » ; commence la préparation dès la Phase 1, c'est plus long qu'il n'y paraît |
| V2 → premier calibrage de paramètres simples | ⚠️ **Partiellement** | Il ne s'agit pas de *calibration* mais de **paramétrage direct** (prix, profils de consommation par âge issus des NTA). La calibration proprement dite exige l'analyse de sensibilité — donc fin de V2 au plus tôt |
| V3 → calibration/validation multi-patterns sur population | ✅ **Correct** | À condition que la séparation calibration/validation soit décidée en Phase 2, pas en Phase 9 |

### Impact sur le mémoire initial

**Faible, si tu adoptes la formulation C.** Elle s'insère dans le Chapitre 6 sans modifier ni la problématique ni le plan. **Elle deviendrait lourde en version D** : il faudrait un chapitre supplémentaire, une revue de littérature sur les méthodes de calibration d'ABM, et des expériences dédiées. Je te le déconseille.

## 13.4 Sources de données — piste confirmée

【LIT】 ✅ Le Sénégal dispose de microdonnées ménages accessibles :

| Source | Contenu | Accès |
|---|---|---|
| **EHCVM 2018-2019** (Enquête Harmonisée sur les Conditions de Vie des Ménages) | Composition des ménages, revenus, consommation, éducation, santé | Catalogue ANADS de l'ANSD ✅ et microdonnées Banque mondiale ✅ |
| **EHCVM 2021-2022** | Idem, plus récent | Catalogue ANADS ✅ et microdonnées Banque mondiale ✅ |
| **Profils NTA Sénégal** | LCD, revenu du travail, consommation par âge | Via le CREFAT, Université de Thiès ✅ |
| ANSD — enquêtes de suivi de la pauvreté | Séries de pauvreté | Site ANSD ✅ |

**Ce que cela change 【RECO】 :** l'initialisation réaliste (niveau 1) devient **immédiatement faisable** avec l'EHCVM. Un extrait de ménages à six membres de composition comparable te donne des distributions réelles d'âges, de revenus et de structures de consommation. C'est le gain le plus rapide de tout ce projet — et cela transforme la phrase « modèle illustratif » en « modèle initialisé sur données d'enquête nationales ».

**Attention 【RECO】 :** l'accès aux microdonnées demande généralement une demande formelle et un délai. **Fais cette démarche en Phase 1, pas en Phase 9.**

## 13.5 Stratégie de validation à six niveaux

Ta proposition en six niveaux est bonne. Je la reprends en précisant, pour chacun, le moment et le critère.

| Niveau | Contenu | Phase | Critère de réussite | Version |
|---|---|---|---|---|
| **V-1 CODE** | Tests unitaires, invariants, conservation des flux, déterminisme par seed | 4 | 100 % des invariants passent sur 100 seeds | V1 |
| **V-2 COMPTABLE** | Identités NTA, cohérence du budget du foyer, cohérence de la dette, conservation des transferts | 4 | Bouclage à ε près à chaque pas | V1 |
| **V-3 COMPORTEMENTALE** | Patterns qualitatifs, réactions aux chocs, trajectoires cohérentes | 6 | Les réponses aux chocs ont le bon signe et un ordre de grandeur plausible | V2 |
| **V-4 EMPIRIQUE** | Comparaison aux données observées (âge, revenu, consommation, emploi, transferts) | 9 | Écart quantifié et discuté, pas nécessairement faible | V3 |
| **V-5 SENSIBILITÉ** | Paramètres cognitifs, stress, aversion au risque, capacité de planification, poids de négociation | 6 puis 9 | Hiérarchie des influences établie ; conclusions robustes | V2/V3 |
| **V-6 POPULATION** | Profils NTA agrégés, distributions, Gini, pauvreté, trajectoires | 9 | Le profil agrégé reproduit la forme en U | V3 |

**Note importante 【RECO】 :** les niveaux V-1 et V-2 sont **les seuls qui soient binaires**. Les autres produisent des écarts à discuter, pas des verdicts. Un mémoire qui rapporte honnêtement « le modèle reproduit P1 et P4, échoue sur P5, voici pourquoi » vaut mieux qu'un mémoire qui affirme tout reproduire.

## 13.6 Paramètres — quoi calibrer, quoi explorer, quoi fixer

| Paramètre | Traitement 【RECO】 | Justification |
|---|---|---|
| `aspiration_threshold` (initial) | **Calibrer** | Non observable, forte influence attendue |
| `memory_capacity` | **Fixer** puis explorer | Peu d'influence attendue au-delà d'un seuil ; à confirmer par Morris |
| `planning_horizon` | **Explorer** (c'est une variable de traitement) | C'est l'objet de ton hétérogénéité — ne le calibre pas, fais-le varier |
| `max_alternatives` | **Explorer** | Idem |
| `impulsivity` | **Fixer** par référence (Steinberg) puis explorer | Ancré sur la littérature développementale |
| `risk_aversion` / λ | **Fixer** aux valeurs publiées (T&K 1992 : λ ≈ 2,25) | Valeurs de référence disponibles — ne réinvente pas |
| `stress_sensitivity` | **Calibrer** | Non observable, au cœur de la boucle B3 |
| `bargaining_weights` | **Calibrer** | Non observable ; informé par les facteurs de distribution |
| Chocs de revenu (fréquence, ampleur) | **Paramétrage direct** depuis l'EHCVM si possible, sinon explorer | Partiellement observable |
| Probabilités de transition de santé | **Paramétrage direct** | Observable dans les enquêtes |
| β (présent-biais) | **Explorer** | C'est une variable de traitement de l'expérience E3 |

**Règle 【RECO】 :** ne calibre jamais un paramètre qui est la variable de traitement d'une de tes expériences. Sinon tu calibres ce que tu prétends étudier.

---

# 14. VERSION V3 — COGNITIVE-AFFECTIVE ET POPULATION

**Retenue au calendrier :** prototype en Phase 7 (J28–J31, jalon de novembre), finalisation en Phases 8–10 (décembre). Les éléments 6 à 8 de la liste ci-dessous sont les premiers à sauter si un jalon glisse (§22).

**Objectif scientifique :** étudier la boucle B3 — la rétroaction entre contrainte économique, état affectif et capacité de décision — et produire un profil NTA agrégé comparable aux profils nationaux.

### Périmètre ajouté, **par ordre de priorité décroissante**

Traite-les dans cet ordre et arrête-toi où le temps s'arrête. 【RECO】

| # | Élément | Pourquoi cette priorité | Coût |
|---|---|---|---|
| 1 | **Appraisal simplifié + 4–5 émotions + `EffectiveCognitiveProfile`** | C'est ta sous-question centrale (« dur vs mou »). Sans cela, la V3 n'a pas de raison d'être | Moyen |
| 2 | **Population de foyers (~1 000)** | **Condition de la validation contre un profil NTA.** Non négociable si tu veux le niveau V-6 | Moyen |
| 3 | **Calibration + POM multi-patterns** | Ce qui fait passer le modèle d'illustratif à calibré | Élevé |
| 4 | **Régime dégradé « sphères séparées »** | Fort intérêt scientifique, coût faible | Faible |
| 5 | **Repère d'efficacité collective** | Transforme une limite théorique en résultat mesuré | Moyen |
| 6 | **CPT sur 4 décisions binaires** | Complète le tableau, mais marginal pour la question centrale | Faible |
| 7 | **Chocs de santé avec rétroaction cognitive** | Enrichit B3 | Moyen |
| 8 | **Extension d'échelle par dégradation cognitive contrôlée** | Résultat scientifique, pas exercice de performance | Moyen |

### Références supplémentaires pour la V3 — **cinq à sept**

8. **Marsella & Gratch (2009), EMA** — mécanisme d'appraisal
9. **Mani et al. (2013)** — justification empirique de la modulation
10. **Grimm et al. (2005), POM** — stratégie de validation
11. **Beal Cohen et al. (2021)** — design de l'expérience foyer
12. **Spielauer et al. (2020), microWELT** — articulation NTA ↔ micro
13. *(optionnel)* **Lundberg & Pollak (1993)** — sphères séparées
14. *(optionnel)* **Tversky & Kahneman (1992)** — formes fonctionnelles CPT

### Expériences

**E4 — La boucle affective** *(l'expérience centrale de la V3)*
- *Hypothèse* 【HYP】 : la boucle contrainte → stress → réduction de l'horizon de planification → décisions plus myopes → aggravation de la contrainte peut produire un enfermement endogène, c'est-à-dire un foyer qui ne remonte pas après un choc dont l'amplitude serait pourtant absorbable par un foyer sans cette boucle.
- *Manipulé* : appraisal activé / désactivé ; amplitude du choc.
- *Contrôlé* : tous les paramètres économiques, même seed.
- *Métriques* : temps de retour au niveau de consommation antérieur, ratio dette/revenu terminal, horizon de planification effectif moyen.
- *Résultat attendu* : **je n'en annonce aucun.** 【RECO】 C'est exactement le genre de résultat qu'il ne faut pas prédire avant exécution. Si l'enfermement n'apparaît pas, c'est un résultat également intéressant, et il faudra en chercher la raison dans les paramètres de modulation.
- *Limites* : l'existence de l'enfermement dépendra fortement de la forme fonctionnelle de la modulation, qui est une hypothèse. À discuter en Chapitre 9.

**E5 — Décision sous risque**
- *Hypothèse* 【HYP】 : l'aversion aux pertes modifie le taux d'acceptation du crédit et retarde la désépargne.
- *Manipulé* : λ ∈ {1 (neutre) ; 2,25 (valeur publiée) ; 3}.

**E7 — Population de foyers**
- *Hypothèse* 【HYP】 : l'agrégation par âge de N foyers hétérogènes produit un profil de LCD de forme comparable aux profils NTA publiés.
- *Manipulé* : N ∈ {100 ; 1 000}, hétérogénéité des dotations initiales.
- *Métriques* : profil de LCD par âge, Gini des revenus, taux de pauvreté.
- **C'est l'expérience de validation principale du mémoire.**

**E8 — Écart à l'efficacité collective**
- *Hypothèse* 【HYP】 : l'allocation produite par un foyer à rationalité limitée s'écarte de l'allocation Pareto-efficace, et l'écart croît avec le stress et la contrainte.
- *Métriques* : distance à la frontière d'efficacité, corrélation avec le niveau de stress.

**E9 — Dégradation cognitive contrôlée**
- *Hypothèse* 【HYP】 : il existe un niveau de simplification cognitive en deçà duquel les indicateurs agrégés (Gini, profil LCD, taux de pauvreté) cessent de différer significativement.
- *Manipulé* : niveau de cognition (V1 / V2 / V3) × taille de population.
- **Intérêt :** c'est une réponse *scientifique* à la question du passage à l'échelle, et non un simple benchmark de performance.

### Critères de sortie de la V3

- [ ] Tous les critères V1 et V2 restent verts
- [ ] E4 est exécutée et rapportée, quel que soit son résultat
- [ ] Le profil de LCD agrégé sur ≥ 1 000 foyers est produit et comparé à une cible
- [ ] Au moins **trois** patterns POM sont reproduits avec un seul jeu de paramètres, dont **au moins un du set validation**
- [ ] La séparation calibration/validation est documentée et respectée
- [ ] L'ODD-V3 est complet

---

# 15. PROTOTYPE FASTAPI — verdict et périmètre

### Verdict pour la V1 : **non.** 【RECO】

Un backend FastAPI en V1 n'apporte rien et coûte du temps. Voici pourquoi, sans détour :

- En V1, l'unique utilisateur c'est toi, et tu lances des simulations depuis un script ou un notebook. Une API ajoute une couche de sérialisation, de gestion d'erreurs et de tests entre toi et ton modèle — sans aucun gain.
- Tes sorties sont analytiques (séries temporelles, agrégations, figures). Parquet + pandas + matplotlib font cela mieux qu'une API JSON.
- **Le risque réel** : tu es ingénieur et dirigeant d'une entreprise tech. L'API et l'interface sont le terrain sur lequel tu es à l'aise, et le modèle scientifique celui sur lequel tu apprends. Il y a une tentation naturelle à construire ce que tu sais faire. **C'est le principal risque de dérive du projet.**

### Quand FastAPI devient justifié

Deux conditions, à réunir toutes les deux :

1. **La V2 est validée** (tous les critères de sortie verts).
2. **Il existe un besoin réel** : lancer et suivre de nombreux scénarios en file d'attente, ou permettre à quelqu'un d'autre que toi (ton encadrant, un chercheur du CREFAT) de déclencher une simulation.

Si la seconde condition n'est jamais remplie, **l'API n'est pas nécessaire au mémoire.** Un notebook de démonstration bien fait suffit largement à une soutenance.

### Si tu le fais quand même — périmètre minimal

Le point non négociable : **une simulation est longue et asynchrone.** Une requête HTTP ne peut pas attendre qu'un run de 1 000 foyers se termine. Il faut donc une file de tâches dès le premier jour, sinon tu réécriras tout.

```
Client (script, notebook, Swagger)
        │
        ▼
   FastAPI  ── POST /simulations  → 202 Accepted + job_id
        │                            (ne bloque jamais)
        ▼
   File de tâches (un simple worker en arrière-plan suffit)
        │
        ▼
   Service de simulation  (orchestration, pas de logique métier)
        │
        ▼
   Moteur Mesa  (inchangé — l'API ne le modifie jamais)
        │
        ▼
   Stockage des résultats (Parquet + index léger)
```

**Endpoints — huit, pas davantage 【RECO】 :**

| Méthode | Route | Rôle |
|---|---|---|
| `POST` | `/simulations` | Créer une simulation à partir d'une configuration ; renvoie `job_id` |
| `GET` | `/simulations/{id}` | Statut : en attente / en cours / terminé / échoué |
| `GET` | `/simulations/{id}/results` | Séries temporelles (paginées) |
| `GET` | `/simulations/{id}/indicators` | Indicateurs agrégés (dette/revenu, épargne, Gini, LCD) |
| `GET` | `/simulations/{id}/households/{hid}` | Détail d'un foyer |
| `GET` | `/simulations/{id}/agents/{aid}` | Détail d'un agent (trajectoire, décisions) |
| `GET` | `/scenarios` | Scénarios disponibles |
| `POST` | `/comparisons` | Comparer deux ou plusieurs simulations sur un jeu d'indicateurs |

**Ce qu'il ne faut pas faire :** une API CRUD complète sur les agents, l'édition de configuration via l'API, l'authentification multi-utilisateurs, WebSocket pour le streaming pas à pas. **Aucun de ces éléments ne sert le mémoire.**

**Interface V1 de l'API : Swagger seul.** L'interface auto-générée de FastAPI suffit pour démontrer que l'API fonctionne.

---

# 16. ARCHITECTURE FINALE FASTAPI + REACT

**Hors périmètre du calendrier — Phase 13, après le dépôt du mémoire.** 【RECO】 RV-19.

### Architecture

Ton intuition de séparation est correcte, et ta règle « React ne parle jamais directement à Mesa » est la bonne. Je l'étends d'un cran : **le service de simulation ne doit contenir aucune logique de modélisation.** S'il en contient, tu auras deux endroits où corriger un bug, et le mémoire décrira un modèle différent de celui qui tourne.

```
┌──────────────────────────────────────────────────────────┐
│ REACT — présentation uniquement                          │
│ Aucune règle métier. Aucun calcul d'indicateur.          │
└───────────────────────┬──────────────────────────────────┘
                        │ HTTP / JSON
┌───────────────────────▼──────────────────────────────────┐
│ FASTAPI — frontière : validation, sérialisation, erreurs │
└───────────────────────┬──────────────────────────────────┘
┌───────────────────────▼──────────────────────────────────┐
│ SERVICE DE SIMULATION — orchestration : file, cycle de   │
│ vie des runs, cache. AUCUNE logique de modélisation      │
└───────────────────────┬──────────────────────────────────┘
┌───────────────────────▼──────────────────────────────────┐
│ MOTEUR MESA — le modèle du mémoire, strictement inchangé │
│ Doit rester exécutable sans API ni base de données       │
└───────────────────────┬──────────────────────────────────┘
┌───────────────────────▼──────────────────────────────────┐
│ NTA / ANALYTICS — calcul des indicateurs et patterns     │
└───────────────────────┬──────────────────────────────────┘
┌───────────────────────▼──────────────────────────────────┐
│ STOCKAGE — Parquet pour les séries + petite base pour    │
│ les métadonnées de runs                                  │
└──────────────────────────────────────────────────────────┘
```

**Une recommandation technique 【RECO】 :** pour le stockage des résultats, préfère **Parquet + DuckDB** à une base relationnelle classique. Tes données sont analytiques (millions de lignes agrégées par requête), pas transactionnelles. DuckDB lit directement du Parquet, ne demande aucun serveur, et se pose sur des fichiers versionnables. Une base relationnelle n'apporterait ici que de la complexité opérationnelle.

**Règle de survie du mémoire 【RECO】 :** le moteur Mesa doit rester exécutable **sans** l'API, **sans** le frontend, **sans** base de données, par un simple script. C'est ce qui garantit que ton jury peut reproduire tes résultats, et que l'application reste un moyen de démonstration et non le projet lui-même.

---

# 17. UX / DESIGN — plateforme scientifique d'expérimentation

Tu l'as bien formulé : l'outil doit ressembler à une plateforme scientifique, pas à une application grand public. Traduction concrète : **densité d'information élevée, hiérarchie visuelle sobre, couleur porteuse de sens et non de décoration, aucune animation gratuite.**

### Architecture de navigation

```
┌─ DASHBOARD ─────────── vue population : où en est la simulation ?
├─ SCÉNARIOS ─────────── configurer, lancer, mettre en file
├─ FOYERS ────────────── liste → vue d'un foyer → vue d'un agent
├─ ANALYTIQUE NTA ────── profils par âge, transferts, cycle de vie
├─ COMPARAISON ───────── scénario A vs B vs C
└─ VALIDATION ────────── observé vs simulé, patterns, sensibilité
```

Six sections, une par question que se pose l'utilisateur. Pas de menu à tiroirs.

### A. Dashboard global

- **Bandeau d'indicateurs** en haut : nombre de foyers, pas de temps courant, dette agrégée, taux d'épargne, LCD agrégé, Gini, taux de pauvreté, stress moyen. Chaque tuile porte **une valeur, une courbe miniature de tendance, et une variation** — pas de jauge circulaire, qui gaspille l'espace sans ajouter d'information.
- **Graphique principal** : profil NTA par âge (consommation, revenu du travail, LCD) — c'est la figure signature du projet, elle doit être au centre.
- **Second graphique** : distribution du ratio dette/revenu entre foyers (histogramme), avec la médiane marquée.
- **Journal d'événements** : chocs, ruptures de coordination, sorties de scolarité.

### B. Vue foyer

- **Schéma du foyer** : six nœuds (un par membre), reliés à un nœud central « foyer ». **L'épaisseur des arêtes code le volume des transferts**, la direction code le sens. C'est la représentation qui rend immédiatement lisible ce que ton mémoire mesure.
- **Panneau financier** : budget commun, dette collective, reste-à-vivre par personne.
- **Bandeau de demandes** : qui a demandé quoi ce mois-ci, qu'est-ce qui a été alloué, qu'est-ce qui a été refusé. **C'est la vue la plus parlante pour une soutenance** — elle rend visible l'arbitrage.
- **Frise d'événements** du foyer.

### C. Vue agent

Trois colonnes : **économique** (revenu, consommation, épargne, dette dans le temps) · **cognitive** (croyances actives, buts, intention en cours, plan, horizon effectif) · **affective** (émotions, stress, santé).

L'élément qui compte : **une frise des décisions récentes, chaque décision étant dépliable pour montrer les alternatives envisagées et la raison du choix.** C'est l'explicabilité que BDI te donne — l'interface doit la rendre visible, sinon l'argument d'explicabilité reste théorique.

### D. Frise de simulation

Une ligne de temps horizontale, une piste par catégorie (chocs · décisions · transferts · changements d'état), avec un curseur qui synchronise toutes les autres vues sur le pas sélectionné.

### E. Analytique NTA

- Profil du LCD par âge, avec la courbe observée superposée en trait discontinu.
- Revenu du travail et consommation par âge, sur le même repère.
- Diagramme de flux des transferts entre classes d'âge (les « flèches de Lee »).
- Épargne / désépargne par âge.

### F. Comparaison de scénarios

Sélecteur multiple de scénarios, puis une grille de petits multiples : **le même graphique répété pour chaque scénario, aux mêmes échelles.** C'est la forme la plus honnête de comparaison visuelle — elle n'exagère aucun écart. Ajoute une table des écarts en pourcentage par rapport au scénario de référence.

### G. Validation

- Observé vs. simulé, un graphique par pattern, avec **le set de calibration et le set de validation visuellement distingués** — c'est un point d'honnêteté scientifique que l'interface doit rendre explicite.
- Le graphique des indices de sensibilité (barres horizontales triées).
- La table des critères de validation, avec leur statut.

### Principes graphiques 【RECO】

| Principe | Application |
|---|---|
| **La couleur porte du sens** | Une couleur par membre du foyer, constante dans toute l'application. Rouge réservé au déficit et aux alertes — jamais décoratif |
| **Une seule famille de graphiques** | Lignes pour les séries temporelles, barres pour les comparaisons, aires empilées pour les décompositions. Pas de camemberts |
| **Échelles fixes en comparaison** | Deux scénarios comparés doivent partager leurs échelles, sans exception |
| **Densité assumée** | Un chercheur préfère dix chiffres lisibles à trois chiffres énormes |
| **Toujours afficher l'incertitude** | Quand un indicateur agrège plusieurs réplications, montrer la dispersion, pas seulement la moyenne |
| **Thème clair par défaut** | Les figures doivent pouvoir être capturées et insérées dans le mémoire |

**Sur l'usage d'un outil de design 【RECO】 :** quand tu arriveras à la Phase 13, je peux produire des maquettes de ces écrans (canevas multi-artboards, navigables et exportables). **Mais pas avant.** Concevoir l'interface avant d'avoir les résultats revient à décider quoi montrer avant de savoir ce qu'on a trouvé — et c'est le chemin le plus court vers une application qui prend le pas sur la recherche.

### MUST / SHOULD / NICE

| Priorité | Éléments |
|---|---|
| **MUST HAVE** | Les figures du mémoire, reproductibles par script. Rien d'autre n'est obligatoire |
| **SHOULD HAVE** | Un notebook de démonstration exécutable pour la soutenance ; le dashboard global ; la vue foyer |
| **NICE TO HAVE** | L'API FastAPI ; le frontend React complet ; la frise interactive ; la comparaison de scénarios en ligne |

**Une application absente ne coûtera pas un point au mémoire. Une validation absente en coûtera beaucoup.**

---

# 18. MATRICE CENTRALE — Question → Modèle → Code → Expérience → Chapitre

C'est la feuille de route principale : chaque ligne est un engagement traçable de bout en bout.

| Question scientifique | Théorie | Modèle computationnel | Module | Paramètre clé | Expérience | Indicateur | Validation | Chap. | V |
|---|---|---|---|---|---|---|---|:--:|:--:|
| Peut-on représenter six membres très différents sans dupliquer le code ? | Taxonomie réactif→délibératif 【LIT】 | Agent générique + profil externe | `PersonAgent` + `config/cognitive_profiles.yaml` | `max_alternatives`, `planning_horizon` | E1, E2 | Nombre de classes d'agents = 1 ; variation comportementale observée | Inspection de code + E2 | 3, 5 | V1 |
| Les flux économiques d'un foyer simulé sont-ils comptablement cohérents ? | Comptabilité NTA 【LIT】 | Identités de flux | `Ledger`, `NTACalculator`, `Invariants` | — | E1 | Résidu de bouclage | V-2, binaire | 4 | V1 |
| Le profil du LCD par âge est-il reproduit ? | Cycle de vie économique 【LIT】 | Agrégation par âge | `nta/accounts.py`, `analysis/patterns.py` | Profils de consommation | E1, E7 | Forme du LCD par âge | V-3 puis V-6 (pattern P1) | 4, 6 | V1→V3 |
| Une règle de décision satisficing suffit-elle à produire des trajectoires plausibles ? | Rationalité limitée 【LIT】 Simon | Seuil d'aspiration adaptatif | `decision/satisficing.py` | `aspiration_threshold` | E1, E2 | Volatilité de la consommation, réactions aux chocs | V-3 | 3, 6 | V1 |
| La persistance des intentions change-t-elle les trajectoires économiques ? | Raisonnement pratique 【LIT】 Bratman | BDI dégradé | `agents/states.py`, `decision/plans.py` | Condition de révision d'intention | **E2** | Écart-type de consommation, taux d'épargne | V-3 | 3, 6 | V2 |
| Le présent-biais explique-t-il la dette ? | Actualisation quasi-hyperbolique 【LIT】 | β-δ | `decision/satisficing.py` | β | **E3** | Ratio dette/revenu, scolarisation | V-3 | 3, 6 | V2 |
| Quels paramètres gouvernent réellement les résultats ? | Analyse de sensibilité 【LIT】 | Morris puis Sobol | `analysis/sensitivity.py` | tous | **E-SA** | Indices de sensibilité | V-5 | 6 | V2 |
| **Comment articuler « dur » et « mou » sans tout convertir en utilité ?** | Appraisal + charge cognitive 【LIT】 EMA, Mani et al. | Modulation des paramètres du processus | `cognition/appraisal.py`, `cognition/modulation.py` | `stress_sensitivity` | **E4** | Horizon effectif, temps de retour après choc | V-3 puis V-5 | **3, 6, 8** | V3 |
| L'aversion aux pertes modifie-t-elle les décisions financières ? | CPT 【LIT】 | Fonction de valeur en S | `decision/risk.py` | λ | **E5** | Taux d'acceptation du crédit | V-3 | 3, 6 | V3 |
| Un foyer non unitaire produit-il des allocations différentes ? | Modèles collectifs / bargaining 【LIT】 | Règle d'allocation à poids | `agents/household.py` | `bargaining_weights` | **E6** | Part de consommation par membre | V-3, comparaison avec repère | 4, 6 | V2/V3 |
| De combien la rationalité limitée éloigne-t-elle de l'efficacité collective ? | Efficacité Pareto 【LIT】 Chiappori | Repère calculé ex post | `analysis/patterns.py` | — | **E8** | Distance à la frontière | Comparaison à un repère théorique | 4, 8 | V3 |
| Quels phénomènes émergent au passage à une population ? | Émergence micro→macro 【LIT】 | Agrégation de N foyers | `model/family_model.py` | N, hétérogénéité initiale | **E7** | Gini, taux de pauvreté, profil LCD | V-6 | 7, 8 | V3 |
| Jusqu'où peut-on simplifier la cognition sans changer les agrégats ? | — 【RECO】 question de conception | Dégradation contrôlée | tous | niveau cognitif | **E9** | Écart sur les indicateurs agrégés | V-5 | 7 | V3 |
| Les données disponibles permettent-elles d'initialiser et de calibrer ce modèle ? | Calibration d'ABM 【LIT】 | Population synthétique + grille | `CalibrationEngine` | 8 paramètres retenus | Phase 9 | Écart aux patterns de validation | V-4 | 6, 9 | V3 |

**Usage 【RECO】 :** garde cette matrice dans le dépôt, en Markdown, et **mets-la à jour à chaque décision.** C'est elle qui t'empêchera d'écrire du code qui ne sert aucune question, et de promettre un chapitre que rien n'alimente.

---

# 19. FICHES DE CONCEPTION

Gabarit à utiliser pour chaque choix architectural important. Trois exemples remplis, à titre de modèle.

### Gabarit

```
CHOIX :
QUESTION : (à quelle question de conception ce choix répond-il ?)
ALTERNATIVES :
LITTÉRATURE :
JUSTIFICATION :
HYPOTHÈSE IMPLICITE :
IMPLÉMENTATION :
TEST :
VALIDATION :
LIMITES :
CHAPITRE DU MÉMOIRE :
STATUT : 【DOC】/【LIT】/【RECO】/【HYP】
```

### Fiche 1 — Satisficing plutôt que MAUT

- **CHOIX** : moteur de décision fondé sur un seuil d'aspiration adaptatif, avec règles non compensatoires, plutôt qu'une fonction d'utilité multi-attributs.
- **QUESTION** : comment un agent choisit-il une action parmi plusieurs, avec des capacités cognitives qui varient selon l'âge ?
- **ALTERNATIVES** : utilité espérée ; MAUT ; heuristiques rapides et frugales ; apprentissage par renforcement.
- **LITTÉRATURE** : Simon (1955, 1956) ; Gigerenzer & Selten (2001) ; Payne, Bettman & Johnson (1993) ; Keeney & Raiffa (1976) pour l'alternative écartée.
- **JUSTIFICATION** : (a) les poids d'une fonction d'utilité multicritère ne sont pas identifiables à partir des données disponibles ; (b) une fonction compensatoire suppose qu'assez d'argent compense n'importe quel déficit de santé, ce que les préférences non compensatoires contredisent ; (c) **argument décisif** — si tous les agents maximisent la même forme fonctionnelle, l'hétérogénéité cognitive se réduit à des poids, et la thèse du mémoire perd son objet.
- **HYPOTHÈSE IMPLICITE** 【HYP】 : le seuil d'aspiration s'ajuste de façon monotone au succès et à l'échec récents. Cette forme d'ajustement est un choix, pas un fait.
- **IMPLÉMENTATION** : `decision/satisficing.py` — énumération bornée par `max_alternatives`, arrêt au premier candidat au-dessus du seuil, ajustement du seuil après résultat.
- **TEST** : un agent avec `max_alternatives = 1` se comporte de façon strictement réactive ; un seuil très bas produit une acceptation immédiate.
- **VALIDATION** : E2 (comparaison avec la V1) et analyse de sensibilité sur `aspiration_threshold`.
- **LIMITES** : la vitesse d'ajustement du seuil est calibrée, non observée ; le modèle ne prétend pas reproduire un processus psychologique réel.
- **CHAPITRE** : 3 (§3.4), 6 (§6.2).
- **STATUT** : 【RECO】 fondé sur 【LIT】.

### Fiche 2 — Pas de HTN

- **CHOIX** : bibliothèque de plans hiérarchique avec replanification sur échec, au lieu d'un planificateur HTN de premier principe.
- **QUESTION** : comment l'agent construit-il une séquence d'actions pour atteindre un but sur plusieurs pas de temps ?
- **ALTERNATIVES** : HTN (SHOP2) ; GOAP ; planification classique ; planification réactive pure.
- **LITTÉRATURE** : Meneguzzi & de Silva (survey KER) sur la correspondance entre bibliothèque de plans BDI et décomposition HTN ; Georgievski & Aiello (2015) pour le panorama HTN ; Sardina & Padgham (2011) pour la gestion d'échec ; Erol, Hendler & Nau (1994) pour l'indécidabilité dans le cas général.
- **JUSTIFICATION** : (a) la bibliothèque de plans BDI constitue déjà une décomposition hiérarchique de tâches ; (b) HTN sert à *synthétiser* des plans quand l'espace est trop grand pour être énuméré — les domaines considérés (budget, santé, éducation, emploi) comportent un nombre de plans plausibles qui se compte en dizaines ; (c) HTN exige un domaine de méthodes écrit à la main, coûteux et pas plus fondé qu'une bibliothèque de plans.
- **HYPOTHÈSE IMPLICITE** 【HYP】 : les plans pertinents pour un foyer peuvent être énumérés a priori. À vérifier en Phase 5 — si des situations apparaissent sans plan applicable, l'hypothèse est fausse et il faudra soit enrichir la bibliothèque, soit reconsidérer.
- **IMPLÉMENTATION** : `decision/plans.py`.
- **TEST** : une situation sans plan applicable déclenche un repli identifiable, jamais une erreur silencieuse.
- **VALIDATION** : mesurer le taux de situations sans plan applicable. S'il dépasse quelques pour cent, la conception est à revoir.
- **LIMITES** : pas de synthèse de plans nouveaux. Assumé et discuté en Chapitre 9.
- **CHAPITRE** : 3 (§3.6), 9.
- **STATUT** : 【RECO】 fondé sur 【LIT】.

### Fiche 3 — Les NTA comme couche de mesure, pas de mécanisme

- **CHOIX** : la couche NTA est en lecture seule sur l'état des agents ; elle ne détermine aucune décision.
- **QUESTION** : les équations NTA doivent-elles piloter les transferts intra-foyer, ou seulement les mesurer ?
- **ALTERNATIVES** : implémenter la règle d'imputation NTA comme mécanisme d'allocation du foyer.
- **LITTÉRATURE** : UN NTA Manual (2013), section sur les transferts privés intra-ménage — les transferts y sont estimés comme solde entre consommation privée et revenu disponible, sous hypothèse de chef de ménage unique détenant les actifs ✅.
- **JUSTIFICATION** : les NTA ne comportent aucune théorie du transfert ; ils comportent une convention d'imputation comptable rendue nécessaire par l'absence d'observation directe. Les utiliser comme mécanisme reviendrait à confondre une convention de mesure avec un comportement.
- **CONSÉQUENCE EXPLOITABLE** 【RECO】 : le modèle produit des transferts comportementaux ; la règle NTA en produit des imputés. **L'écart entre les deux est mesurable et constitue un résultat du mémoire.** Formulation prudente exigée : « cette comparaison est étudiée dans ce mémoire », **pas** « personne ne l'a faite » (voir l'avertissement préalable).
- **HYPOTHÈSE IMPLICITE** 【HYP】 : la règle d'imputation NTA, appliquée au foyer simulé, produit un résultat différent des transferts effectifs. Si l'écart est nul, c'est aussi un résultat.
- **IMPLÉMENTATION** : `nta/accounts.py` (mesure) et `nta/imputation.py` (règle du manuel) — **deux modules distincts, jamais fusionnés**.
- **TEST** : les deux modules bouclent indépendamment.
- **VALIDATION** : V-2 (comptable) puis comparaison en Chapitre 8.
- **LIMITES** : la règle d'imputation NTA suppose un chef de ménage unique, hypothèse discutable dans le contexte sénégalais où la structure des ménages est souvent plus complexe. **À discuter en Chapitre 9.**
- **CHAPITRE** : 4 (§4.3), 8, 9.
- **STATUT** : 【RECO】 fondé sur 【LIT】.

---

# 20. PLAN DE LECTURE

### Gabarit de fiche de lecture

À remplir pour chaque pilier et chaque lecture ciblée. Une page maximum. **Ces fiches deviennent directement des paragraphes du Chapitre 2.**

```
RÉFÉRENCE :
POURQUOI JE LA LIS :
SECTIONS EFFECTIVEMENT LUES :
TEMPS RÉEL PASSÉ :
CONCEPTS RETENUS (3 maximum) :
CE QUE JE DOIS SAVOIR EXPLIQUER :
CITATION UTILE (texte exact + page) :
DÉCISION DE CONCEPTION ASSOCIÉE :
CHAPITRE ET SECTION DU MÉMOIRE :
CE QUE JE N'AI PAS LU ET POURQUOI :
STATUT : [FOUNDATION] / [READ] / [PARTIAL] / [REFERENCE ONLY]
```

### Calendrier de lecture — plan retenu (17 septembre → 31 décembre)

La lecture n'est plus un bloc initial : elle est **répartie sur les phases, juste avant le moment où chaque ressource sert.** C'est ce qui permet de démarrer la Phase 2 en fin de septembre.

| Journée | Phase | Lecture | Heures | Livrable de la journée |
|---|---|---|---|---|
| J1 | 0 | *(aucune)* — cadrage, dépôt, demandes de données | — | Périmètre écrit, environnement Claude installé |
| J2 | 1 | **Balke & Gilbert (2014)** intégral | 3 | Fiche + brouillon du tableau comparatif du Ch. 2 |
| J3 | 1 | **ODD (1a) + checklists (1b)** | 4 | Fiche + gabarit ODD rempli à 30 % |
| J4 | 1 | **NTA Manual** — LCD + transferts privés | 6 | Fiche + notation formalisée du Ch. 4 |
| J5 | 1 | **ODD+D (1c)** + **recherche systématique** | 5 | Fiche + annexe de protocole d'une page |
| J6–J8 | 2 | *(pendant la conception)* relecture ciblée 1b | 1 | **ODD-V0 complet** |
| J14–J15 | 4 | **POM + cycle de modélisation (1d)** | 2,5 | Affectation des patterns figée |
| J16 | 5 | **Adam & Gaudou** + **Consumat II** — ciblé | 4 | Fiches |
| J22–J23 | 6 | **Sensibilité (1e)** + **ten Broeke et al.** | 4 | Protocole de sensibilité |
| J26 | 7 | **EMA** + **Mani et al.** — ciblé | 4 | Fiches |
| J32 | 8 | **Chiappori & Mazzocco** — sections retenues | 7 | Fiche + section 4.5 du mémoire |
| J34 | 9 | **microWELT** + **Beal Cohen et al.** — ciblé | 3 | Fiches |
| | | **Total** | **≈ 44 h** | |

**Deux remarques 【RECO】 :**
- Chiappori & Mazzocco est volontairement repoussé en décembre (J32). C'est la lecture la plus difficile, et elle ne débloque rien avant la Phase 8 — mais elle est indispensable au Chapitre 4. Ne la sacrifie pas.
- Si un jalon glisse, **la variable d'ajustement est le nombre de lectures ciblées, jamais les quatre piliers ni le quota de rédaction.**

---

# 21. PLAN DE RÉDACTION — chapitre par chapitre

Le plan initial de ta proposition est conservé. 【DOC】 Un seul ajustement 【RECO】 : le Chapitre 6 accueille désormais explicitement la question de calibration (§13.3), et le Chapitre 7 est justifié par la validation et non par la performance.

---

**CHAPITRE 1 — Introduction, contexte et problématique**
- *Objectif scientifique* : poser le problème, situer le travail, annoncer la démarche.
- *Questions* : pourquoi la famille comme objet ? pourquoi les SMA ? pourquoi les NTA ? qu'est-ce qui est étudié ici et qui ne l'a pas été de cette façon ?
- *Concepts* : cycle de vie économique, transferts privés, hétérogénéité cognitive.
- *À lire* : NTA Manual (vue d'ensemble), Lee & Mason (2011) introduction.
- *À citer* : Schelling, Epstein & Axtell, Lee & Mason, Silverman et al., Spielauer et al.
- *Artefacts* : la section « Purpose » de l'ODD.
- *Code* : aucun.
- *Expériences* : aucune.
- *Validation* : **la recherche systématique documentée est ce qui autorise les phrases de positionnement.** Sans elle, écrire « à notre connaissance ».
- *Écrire quand* : esquisse en Phase 2, version finale en Phase 12.

---

**CHAPITRE 2 — État de l'art**
- *Objectif* : montrer que les choix architecturaux sont informés et non par défaut.
- *Questions* : quelles architectures d'agent existent ? comment décide un agent ? comment modélise-t-on une décision de ménage ? qu'est-ce que les NTA ?
- *Concepts* : réactif/délibératif/hybride, BDI, architectures cognitives, rationalité limitée, appraisal, modèles unitaires/collectifs, NTA.
- *À lire* : Balke & Gilbert, Adam & Gaudou, Chiappori & Mazzocco, NTA Manual.
- *À citer* : l'ensemble du registre §6 — **y compris les références écartées, avec la raison du rejet.**
- *Artefacts* : les fiches de lecture ; le tableau comparatif des architectures (grille issue de Balke & Gilbert).
- *Code* : aucun.
- *Validation* : chaque approche écartée doit avoir une phrase de rejet argumentée.
- *Écrire quand* : Phases 1–2 pour 60 %, complété au fil de l'eau.

---

**CHAPITRE 3 — Architecture du système**
- *Objectif* : décrire et **justifier** l'architecture générique et l'hétérogénéité paramétrée.
- *Questions* : quelle architecture pour six membres sans duplication ? comment articuler dur et mou ? pourquoi ce moteur de décision ?
- *Concepts* : design concepts (ODD), CognitiveProfile, satisficing, persistance des intentions, modulation affective.
- *À lire* : Railsback & Grimm (design concepts), Simon, Balke & Gilbert.
- *À citer* : Wooldridge & Jennings, Bratman, Rao & Georgeff, Simon, Payne et al., EMA, Mani et al., Steinberg, LARA, Consumat, BEN.
- *Artefacts* : **ODD-V0 sections « Entities », « Process overview », « Design concepts »** ; le schéma du pipeline corrigé ; les fiches de conception.
- *Code* : `agents/`, `decision/`, `cognition/`.
- *Expériences* : E2, E4.
- *Validation* : chaque composant de l'architecture apparaît dans la matrice §18 avec une expérience associée. **Un composant sans expérience associée doit sortir du chapitre.**
- *Écrire quand* : Phase 2 (structure), Phase 5 (contenu cognitif), Phase 7 (contenu affectif).

---

**CHAPITRE 4 — Modélisation économique et sociale / NTA**
- *Objectif* : formaliser la couche économique et son articulation avec les NTA.
- *Questions* : comment les équations NTA se réinterprètent-elles à l'échelle du foyer ? comment le foyer alloue-t-il ?
- *Concepts* : LCD, identité de flux, réallocations, transferts privés, règle d'imputation, poids de négociation.
- *À lire* : NTA Manual (chapitres LCD et transferts privés), Chiappori & Mazzocco.
- *À citer* : UN (2013), Lee & Mason, Lee (1994), Spielauer et al., Vargha et al., Becker, Chiappori, Manser & Brown, McElroy & Horney, Lundberg & Pollak, Dauphin et al., Beal Cohen et al.
- *Artefacts* : les équations formalisées ; **la comparaison explicite transferts comportementaux / transferts imputés** ; ODD sous-modèles économiques.
- *Code* : `economy/`, `nta/`, `agents/household.py`.
- *Expériences* : E1, E6, E8.
- *Validation* : V-2 (bouclage comptable), binaire.
- *Écrire quand* : Phase 3–4.

---

**CHAPITRE 5 — Implémentation Python/Mesa**
- *Objectif* : décrire le modèle de façon reproductible.
- *Questions* : quelles entités, quelles variables, quel ordonnancement, quels sous-modèles ?
- *À lire* : Railsback & Grimm (ODD), documentation Mesa 3.
- *À citer* : Kazil et al. (2020), ter Hoeven et al. (2025), Grimm et al. (2020), Gamma et al. (une fois).
- *Artefacts* : **ODD-V1/V2/V3 — ce chapitre est essentiellement l'ODD mis en prose.**
- *Code* : tout le dépôt.
- *Validation* : V-1 (tests) ; reproductibilité par seed.
- *Écrire quand* : **au fil de l'eau, via l'ODD.** Ne l'écris jamais rétrospectivement.

---

**CHAPITRE 6 — Expérimentations**
- *Objectif* : établir ce que le modèle produit et dans quelles conditions on peut y croire.
- *Questions* : l'architecture cognitive change-t-elle les trajectoires ? quels paramètres gouvernent les résultats ? les données permettent-elles d'initialiser et de calibrer ce modèle ?
- *Concepts* : POM, analyse de sensibilité, séparation calibration/validation, plan d'expérience.
- *À lire* : Grimm et al. (2005), ten Broeke et al. (2016), Railsback & Grimm (chapitres sensibilité).
- *À citer* : Grimm et al. (2005, 2020), Windrum et al. (2007), ten Broeke et al. (2016), Thiele et al. (2014), Beal Cohen et al. (2021).
- *Artefacts* : le protocole expérimental ; le tableau des patterns avec leur affectation calibration/validation ; les figures de sensibilité.
- *Code* : `experiments/`, `analysis/`.
- *Expériences* : E1 à E9.
- *Validation* : V-3, V-4, V-5.
- *Écrire quand* : au fil des Phases 4, 6, 9, 10.

---

**CHAPITRE 7 — Passage à l'échelle**
- *Objectif* : montrer que l'architecture supporte le passage du foyer à la population, **et pourquoi ce passage est nécessaire.**
- *Question centrale* 【RECO】 : reformule l'angle. Pas « le modèle est-il rapide ? » mais **« un profil NTA ne peut être reproduit qu'au niveau d'une population — que faut-il conserver et que peut-on simplifier pour y parvenir ? »** C'est ce qui transforme un chapitre d'ingénierie en chapitre scientifique.
- *Concepts* : émergence, coût par agent, dégradation contrôlée.
- *À citer* : Schelling, Epstein & Axtell, Datseris et al. (benchmarks), Abar et al., Grow & Van Bavel.
- *Artefacts* : courbe de coût en fonction de N ; résultats de E9.
- *Expériences* : E7, E9.
- *Validation* : V-6.
- *Écrire quand* : Phases 8 et 11 (J32–J33, J39). En cas de repli : chapitre de conception et de perspective, sans expérience.

---

**CHAPITRE 8 — Analyse des conséquences socio-économiques**
- *Objectif* : interpréter. C'est ici que le mémoire dit quelque chose sur le monde.
- *Questions* : que révèlent les scénarios contrefactuels ? que dit l'écart entre transferts comportementaux et imputés ? la boucle affective produit-elle un enfermement ?
- *Artefacts* : le tableau de bord d'indicateurs 【DOC】 ; les comparaisons de scénarios.
- *Expériences* : toutes.
- *Validation* : chaque affirmation renvoie à une figure et à une expérience nommée.
- *Attention* 【RECO】 : c'est le chapitre où la tentation de sur-interpréter est la plus forte. Chaque conclusion doit porter sa condition de validité (« sous l'hypothèse que la modulation affective prenne cette forme… »).

---

**CHAPITRE 9 — Limites, éthique et perspectives**
- *Objectif* : établir la crédibilité par la lucidité. **C'est le chapitre que les jurys lisent le plus attentivement.**
- *À traiter obligatoirement* :
  - ce qui n'est pas validé et ne peut pas l'être (l'expérience émotionnelle simulée, notamment) ;
  - la sous-détermination des paramètres (Windrum et al.) ;
  - l'hypothèse de chef de ménage unique de la règle NTA, discutable dans le contexte sénégalais ;
  - l'absence d'apprentissage, et pourquoi c'est un choix ;
  - l'éthique de modéliser la pauvreté, la maladie et l'inégalité 【DOC】 ;
  - les extensions futures (§8, catégorie EXTENSION FUTURE).
- *À citer* : Windrum et al. (2007), Fagiolo et al. (2019), Grimm et al. (2020).

---

**CHAPITRE 10 — Conclusion**
- Reprendre les quatre questions de recherche 【DOC】 et y répondre explicitement, y compris par « partiellement » ou « non ».

---

# 22. CALENDRIER DÉTAILLÉ — 44 journées

**Cadence : 3 journées pleines par semaine.** Jalon 1 : V2 + prototype V3 fin novembre. Jalon 2 : V3 + mémoire fin décembre.

## Bloc 1 — septembre → novembre (31 journées)

| Journées | Sem. | Phase | Objectif de la séquence | Livrable de fin de bloc |
|---|---|---|---|---|
| J1 | 1 | **0** | Cadrage, dépôt, environnement Claude, demandes de données | Périmètre figé, `.claude/` installé |
| J2–J5 | 1–2 | **1** | Piliers 3, 1a/1b, 2, 1c + recherche systématique | 4 fiches, annexe protocole, Ch. 2 à 50 % |
| J6–J8 | 2–3 | **2** | Modèle conceptuel, ODD-V0, fiches de conception, affectation des patterns | **ODD-V0**, Ch. 3 en brouillon |
| J9–J14 | 3–5 | **3** | Implémentation V1 : états, Ledger, actions, foyer, couche NTA | V1 exécutable, ODD-V1 |
| J15–J16 | 5–6 | **4** | Invariants, tests, E1 | **Critères de sortie V1 verts** |
| J17–J23 | 6–8 | **5** | V2 : BDI dégradé, mémoire, satisficing complet, plans, β-δ | V2 exécutable, ODD-V2 |
| J24–J27 | 8–9 | **6** | E2, E3, E6, criblage de Morris puis Sobol | **Critères de sortie V2 verts**, figures de sensibilité |
| J28–J31 | 10–11 | **7** | Prototype V3 : appraisal simplifié, 4–5 émotions, modulation, E4 | **JALON NOVEMBRE — V2 + prototype V3** |

## Bloc 2 — décembre (13 journées)

| Journées | Phase | Objectif | Livrable |
|---|---|---|---|
| J32–J33 | **8** | Population de ~1 000 foyers, E7 | Profil NTA agrégé |
| J34–J36 | **9** | Population synthétique EHCVM, calibration sur le set désigné, **validation sur le set réservé** | Écarts quantifiés |
| J37–J38 | **10** | E5, E8, scénarios contrefactuels | Toutes les figures |
| J39 | **11** | Analyse, Chapitre 8 | Ch. 8 rédigé |
| J40–J44 | **12** | Finalisation : Ch. 1, 7, 9, 10 ; bibliographie nettoyée ; annexes | **JALON DÉCEMBRE — mémoire déposé** |

## Ce qui saute si un jalon glisse de plus de deux semaines

Par ordre d'abandon 【RECO】 :

1. **E5 (CPT / aversion aux pertes)** — marginal pour la question centrale
2. **E8 (écart à l'efficacité collective)** — intéressant mais non essentiel
3. **E9 (dégradation cognitive contrôlée)** — le Chapitre 7 devient conception + perspective
4. **La calibration sur EHCVM** — repli sur une population synthétique paramétrée depuis les profils NTA publiés, en le disant clairement
5. **La V3 entière** — elle devient prototype démonstratif + Chapitre 9

**Ce qui ne saute jamais :** les critères de sortie V1 et V2, l'analyse de sensibilité, la séparation calibration/validation, et le quota quotidien de rédaction.

## Hors périmètre du calendrier

- **Phase 13 (application FastAPI + React)** : après le dépôt. RV-19.
- **Phase 14 (soutenance)** : selon la date réelle, à caler quand elle sera connue.

---

# 23. RISQUES SCIENTIFIQUES

Classés par probabilité × gravité, du plus dangereux au moins.

| # | Risque | Signe précurseur | Parade | Gravité |
|---|---|---|---|---|
| **R1** | **Périmètre irréaliste au regard du calendrier** | Tu es en semaine 8 et la V1 n'est pas validée | **Trancher Q1 maintenant**, adopter le scénario correspondant et le figer par écrit | ★★★ |
| **R2** | **Sous-détermination des paramètres** — 25 paramètres libres peuvent produire n'importe quoi | Tu obtiens le résultat attendu et tu es content | Analyse de sensibilité **avant** calibration ; POM multi-patterns ; séparation calibration/validation | ★★★ |
| **R3** | **Sur-ajustement déguisé en validation** — calibrer et valider sur les mêmes cibles | Tu écris « le modèle reproduit le profil que nous avons utilisé pour le caler » | Affectation des patterns décidée en Phase 2, écrite dans l'ODD, jamais modifiée ensuite | ★★★ |
| **R4** | **Revendication d'originalité non étayée** | Tu écris « personne n'a fait cela » | Recherche systématique documentée ou formulation prudente. Voir l'avertissement préalable | ★★★ |
| **R5** | **Dérive vers le développement applicatif** | Tu passes un week-end sur l'interface avant d'avoir validé la V2 | Règle dure : **aucune ligne de frontend avant que la rédaction ne soit terminée** | ★★★ |
| **R6** | **Empilement théorique** | Ton Chapitre 2 compte sept cadres et ton Chapitre 3 les revendique tous | La classification §8 ; tout composant sans expérience associée sort | ★★ |
| **R7** | **Fuite comptable silencieuse** | Un écart de bouclage « petit » qu'on ignore | Le `Ledger` en source unique ; les invariants font échouer la simulation, pas un avertissement | ★★ |
| **R8** | **ODD écrit rétrospectivement** | Tu te dis « je le ferai à la fin » | Règle dure : aucun sous-modèle codé avant d'être décrit | ★★ |
| **R9** | **Données inaccessibles ou tardives** | Tu demandes l'EHCVM en Phase 9 | Demandes envoyées en Phase 0. Plan de repli : population synthétique paramétrée sur les profils NTA publiés | ★★ |
| **R10** | **Incohérence entre le mémoire et le code** | Le mémoire décrit un mécanisme que le code n'implémente plus | L'ODD corrigé dans le même commit que le code | ★★ |
| **R11** | **Sur-interprétation des résultats** | Une conclusion sans condition de validité | Chaque conclusion du Chapitre 8 renvoie à une expérience nommée et porte son hypothèse | ★★ |
| **R12** | **Prédiction de résultats avant exécution** | Tu écris le résultat attendu de E4 dans ton Chapitre 8 avant de l'avoir lancée | 【DOC】 c'est ta propre règle — respecte-la | ★ |

---

# 24. CRITÈRES DE PASSAGE D'UNE PHASE À LA SUIVANTE

**Règle 【RECO】 : une case non cochée bloque la phase suivante.** Pas de « je le ferai plus tard ».

| Passage | Conditions |
|---|---|
| **0 → 1** | Q1 tranchée et écrite · scénario choisi · demandes de données envoyées · contact CREFAT initié |
| **1 → 2** | 4 fiches de lecture rédigées · recherche systématique documentée en une page · tu sais expliquer oralement les 4 idées clés |
| **2 → 3** | ODD-V0 complet, dont **les design concepts** · Q2–Q5 tranchées · ordonnancement en 3 temps spécifié · au moins 3 fiches de conception rédigées |
| **3 → 4** | V1 exécutable de bout en bout · ODD-V1 à jour · suite de tests en place |
| **4 → 5** | **Tous les critères de sortie V1 verts** (§11) · E1 rapportée · chapitres 4 et 5 en brouillon |
| **5 → 6** | V2 exécutable · non-régression V1 · ODD-V2 à jour |
| **6 → 7** | Critères de sortie V2 verts (§12) · E2, E3, E-SA rapportées · ≥ 2 patterns reproduits · Chapitre 3 en brouillon complet |
| **7 → 8** | Appraisal implémenté et testé · E4 exécutée et rapportée **quel que soit son résultat** |
| **8 → 9** | Population de ≥ 1 000 foyers exécutable dans un budget temps acceptable · E7 rapportée |
| **9 → 10** | Calibration effectuée sur le set désigné · **validation effectuée sur le set réservé** · écarts quantifiés |
| **10 → 11** | Toutes les expériences prévues exécutées, y compris celles dont le résultat déçoit |
| **11 → 12** | Toutes les figures produites et reproductibles par script |
| **12 → 13** | **Mémoire déposé.** L'application ne commence pas avant |
| **13 → 14** | Démonstration exécutable hors ligne |

---

# 25. LES QUATORZE PHASES

---

### PHASE 0 — Cadrer et décider — **J1 (1 journée)**
- **Objectifs** : figer le périmètre ; lever les décisions bloquantes.
- **Lectures** : aucune.
- **Code** : initialiser le dépôt, l'environnement Python, la structure de dossiers, **et installer le dispositif Claude** (`CLAUDE.md`, `.claude/agents/`, `.claude/skills/`, `.claude/commands/`, `docs/REGLES_VALIDATION.md`) — voir le document compagnon.
- **Documents** : une note d'une page fixant Q1 à Q5 et le scénario retenu.
- **Expériences** : aucune.
- **Livrables** : périmètre écrit ; dépôt initialisé ; demandes d'accès aux données envoyées ; prise de contact avec le CREFAT.
- **Réussite** : tu peux dire en une phrase ce que ton mémoire contiendra et ce qu'il ne contiendra pas.

### PHASE 1 — Lire les piliers et documenter l'état de l'art — **J2–J5 (4 journées)**
- **Objectifs** : acquérir le socle ; établir le positionnement de façon défendable.
- **Lectures** : Balke & Gilbert · dossier méthodologique 1a/1b/1c · UN NTA Manual · Simon.
- **Code** : aucun.
- **Documents** : 4 à 5 fiches de lecture ; **une page de protocole de recherche systématique** ; brouillon du Chapitre 2 à 50 %.
- **Livrables** : fiches ; annexe de protocole ; registre bibliographique §6 mis à jour avec les statuts réels.
- **Réussite** : tu peux expliquer à l'oral, sans notes, pourquoi les transferts intra-ménage NTA sont un résidu, et pourquoi aucune architecture de décision n'est universellement supérieure.

### PHASE 2 — Modèle conceptuel et ODD-V0 — **J6–J8 (3 journées)**
- **Objectifs** : concevoir avant de coder ; trancher l'ordonnancement.
- **Lectures** : dossier méthodologique 1b (checklists) et 1c (ODD+D), relecture ciblée.
- **Code** : aucun. **C'est volontaire.**
- **Documents** : **ODD-V0** ; le pipeline corrigé schématisé ; ≥ 3 fiches de conception ; l'affectation des patterns calibration/validation.
- **Livrables** : ODD-V0 ; brouillon du Chapitre 3 ; matrice §18 remplie pour la V1.
- **Réussite** : un lecteur extérieur pourrait réimplémenter la V1 à partir de l'ODD-V0 seul.

### PHASE 3 — Implémenter la V1 — **J9–J14 (6 journées)**
- **Objectifs** : un baseline économique exécutable et documenté.
- **Lectures** : documentation Mesa 3 uniquement.
- **Code** : `agents/`, `economy/`, `nta/`, `model/`, `config/`, `tests/`.
- **Documents** : ODD-V1 en parallèle du code.
- **Livrables** : V1 exécutable ; suite de tests ; brouillons des Chapitres 4 et 5.
- **Réussite** : une simulation de 20 ans s'exécute, produit des données, et l'ODD la décrit fidèlement.

### PHASE 4 — Valider la V1 — **J15–J16 (2 journées)**
- **Objectifs** : établir la cohérence comptable. **C'est la fondation de tout le reste.**
- **Code** : `nta/invariants.py`, `tests/`.
- **Expériences** : E1.
- **Livrables** : critères de sortie V1 tous verts ; E1 rapportée ; figures du profil LCD.
- **Réussite** : 100 seeds, 20 ans, zéro violation d'invariant.

### PHASE 5 — Ajouter la cognition — **J17–J23 (7 journées)**
- **Objectifs** : rendre l'hétérogénéité cognitive effective.
- **Lectures ciblées** : Adam & Gaudou · Consumat II · *(Laibson si β-δ)*.
- **Code** : `decision/`, `cognition/memory.py`, `decision/plans.py`.
- **Documents** : ODD-V2.
- **Livrables** : V2 exécutable ; non-régression V1 ; Chapitre 3 complété.
- **Réussite** : deux agents de profils différents, dans une situation identique, prennent des décisions différentes **et tu peux expliquer pourquoi**.

### PHASE 6 — Valider les comportements — **J24–J27 (4 journées)**
- **Objectifs** : mesurer l'effet de la cognition ; hiérarchiser les paramètres.
- **Lectures ciblées** : ten Broeke et al. · Grimm et al. (2005).
- **Code** : `analysis/sensitivity.py`, `analysis/patterns.py`.
- **Expériences** : E2, E3, E6, E-SA.
- **Livrables** : figures de sensibilité ; ≥ 2 patterns reproduits ; Chapitre 6 à 50 %.
- **Réussite** : tu peux nommer les cinq paramètres qui gouvernent réellement tes résultats.

> **Point de contrôle majeur.** Si les critères de sortie V2 ne sont pas verts à J27, ne passe pas en Phase 7 : c'est le moment où le plan de repli s'applique (§22). Un prototype V3 posé sur une V2 non validée ne vaut rien.

### PHASE 7 — Affect, santé, risque — **J28–J31 (4 journées)** ◄ JALON NOVEMBRE
- **Lectures ciblées** : EMA · Mani et al. · *(Lundberg & Pollak, Tversky & Kahneman si retenus)*.
- **Code** : `cognition/appraisal.py`, `cognition/modulation.py`, `decision/risk.py`.
- **Expériences** : **E4** (centrale), E5.
- **Livrables** : ODD-V3 ; E4 rapportée quel qu'en soit le résultat.
- **Réussite** : la boucle B3 est implémentée, testée et son effet mesuré — **positivement ou négativement**.

### PHASE 8 — Population de foyers — **J32–J33 (2 journées)**
- **Code** : générateur de population, optimisation du pas de temps.
- **Expériences** : E7.
- **Livrables** : profil NTA agrégé sur ≥ 1 000 foyers ; courbe de coût en fonction de N.
- **Réussite** : un run de 1 000 foyers × 20 ans s'exécute dans un budget compatible avec 100 réplications.

### PHASE 9 — Calibration et POM — **J34–J36 (3 journées)**
- **Lectures ciblées** : Grimm et al. (2005) · Windrum et al. · microWELT.
- **Code** : `CalibrationEngine`, préparation des données EHCVM.
- **Livrables** : population synthétique initialisée sur données ; paramètres calibrés sur le set désigné ; **validation sur le set réservé** ; écarts quantifiés.
- **Réussite** : ≥ 3 patterns reproduits avec un seul jeu de paramètres, dont ≥ 1 du set validation.

### PHASE 10 — Expérimentations complètes — **J37–J38 (2 journées)**
- **Expériences** : E8, E9, scénarios contrefactuels 【DOC】 (allocation familiale, perte d'emploi, gratuité des soins, choc économique).
- **Livrables** : toutes les figures ; tableau de bord d'indicateurs.
- **Réussite** : chaque question de la matrice §18 a sa réponse expérimentale, y compris négative.

### PHASE 11 — Analyse — **J39 (1 journée)**
- **Livrables** : Chapitre 8 rédigé ; Chapitre 9 (limites) rédigé.
- **Réussite** : chaque conclusion porte sa condition de validité.

### PHASE 12 — Rédaction finale — **J40–J44 (5 journées)** ◄ JALON DÉCEMBRE
- **Livrables** : mémoire complet ; bibliographie nettoyée des citations décoratives (§6) ; annexes (ODD complet, protocole de recherche systématique, tables de sensibilité).
- **Réussite** : chaque référence de la bibliographie passe le test « pourquoi est-elle là ? ».

### PHASE 13 — Application de démonstration — **hors périmètre, après dépôt**
- **Livrables** : FastAPI minimal (8 endpoints) ; interface React sur les vues Dashboard / Foyer / NTA.
- **Réussite** : la démonstration tourne hors ligne et le moteur reste exécutable sans elle.

### PHASE 14 — Soutenance — **à caler quand la date sera connue**
- **Livrables** : présentation ; démonstration répétée ; anticipation des questions.
- **Les cinq questions à préparer en priorité 【RECO】** :
  1. *Pourquoi BDI et pas une autre architecture ?* → Balke & Gilbert + explicabilité.
  2. *Comment savez-vous que vos paramètres ne sont pas ajustés pour obtenir le résultat ?* → sensibilité + séparation calibration/validation.
  3. *Votre modèle reproduit-il la psychologie réelle ?* → non, et voici ce qu'il prétend faire à la place.
  4. *Pourquoi ne pas avoir utilisé le modèle collectif de Chiappori ?* → incompatibilité avec la rationalité limitée ; usage comme repère.
  5. *Qu'est-ce qui est nouveau dans votre travail ?* → **formulation prudente**, combinaison étudiée, pas revendication de primauté.

---

# 26. TODO LIST — J1 à J8

### J1 — Phase 0 (cadrage) — **aujourd'hui**

- [ ] **Initialiser le dépôt** `family_abm/` avec la structure §9
- [ ] **Installer le dispositif Claude** : `CLAUDE.md`, `.claude/agents/` (8 personas), `.claude/skills/` (5 skills), `.claude/commands/` (3 commandes), `docs/REGLES_VALIDATION.md` — tous les blocs sont prêts à coller dans le document compagnon
- [ ] **Contacter le Pr. Latif Dramani au CREFAT** (Université de Thiès) : présenter le sujet, demander les profils NTA du Sénégal
- [ ] **Demander l'accès aux microdonnées EHCVM** (catalogue ANADS de l'ANSD, ou microdonnées Banque mondiale). Le délai est le risque
- [ ] **Récupérer le dossier méthodologique** : les cinq ressources du §4, pilier 1 — toutes gratuites, à télécharger maintenant
- [ ] **Trancher Q2 à Q5** (pas de temps, horizon, départ du jeune adulte, démographie) et les écrire dans `docs/DECISIONS.md`
- [ ] Créer `odd/ODD_v0_conceptual.md` vide et `docs/MATRICE_QUESTION_MODELE.md` avec les en-têtes

### J2 — Phase 1

- [ ] Lire **Balke & Gilbert (2014)** intégralement → `fiche-lecture`
- [ ] Rédiger le tableau comparatif des architectures (Ch. 2)
- [ ] **Quota rédaction : une section du Chapitre 2**

### J3 — Phase 1

- [ ] Lire **l'ODD (1a)** et parcourir **les checklists (1b)** → fiche
- [ ] Remplir le gabarit ODD à 30 % (Purpose, Entities, Scales)
- [ ] **Quota rédaction : une section**

### J4 — Phase 1

- [ ] Lire le **NTA Manual** : chapitres LCD et transferts privés → fiche
- [ ] Formaliser la notation du Chapitre 4, identique à celle du manuel
- [ ] **Quota rédaction : la section 4.1**

### J5 — Phase 1

- [ ] Lire **ODD+D (1c)** → fiche
- [ ] Conduire la **recherche systématique minimale** avec `bibliothecaire` → annexe d'une page
- [ ] Reformuler toutes les phrases de positionnement du Chapitre 1 selon RV-03
- [ ] **Quota rédaction : une section du Chapitre 1**

### J6–J8 — Phase 2

- [ ] **Écrire l'ODD-V0 en entier**, les onze design concepts compris
- [ ] Répondre aux six questions ODD+D pour le sous-modèle de décision
- [ ] Spécifier l'**ordonnancement en trois temps**
- [ ] Rédiger au moins cinq **fiches de conception**
- [ ] **Figer l'affectation des patterns** calibration / validation dans l'ODD (RV-16)
- [ ] Remplir la **matrice §18** pour la V1
- [ ] Lancer `/controle-regles` avant de passer en Phase 3

### Ensuite

Suivre le calendrier du §22 et les critères de passage du §24. Le bilan de chaque journée se fait avec `/fin-journee`.

---

## Ce document et les suivants

Ce document est une **feuille de route, pas un contrat**. Révisions prévues :
- **fin Phase 1 (J5)** — quand les lectures auront modifié ta compréhension ;
- **fin Phase 4 (J16)** — quand la V1 aura révélé ce que la conception n'avait pas prévu ;
- **fin Phase 6 (J27)** — point de contrôle du jalon de novembre, et décision sur le plan de repli.

**Document compagnon :** `ENVIRONNEMENT_CLAUDE_PERSONAS_SKILLS_REGLES.md` — les 8 personas, 5 skills, 20 règles de validation et 3 commandes de session, prêts à installer. À lire avant J1.

**Prochain livrable attendu de ma part 【RECO】 :** le gabarit détaillé de l'ODD-V0, section par section, avec les questions précises auxquelles chacune doit répondre pour ton modèle — y compris les six questions ODD+D appliquées à ton moteur de décision. À produire quand tu auras tranché Q2 à Q5.

---

*Fin du document — révision v2 du 17 septembre 2026.*
