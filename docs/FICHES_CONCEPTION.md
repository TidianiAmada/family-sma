# Fiches de conception

> Gabarit de la feuille de route §19. Les fiches 1 à 3 reprennent la feuille de route ; les fiches 4 à 10 documentent les choix tranchés dans ce dossier de spécifications. Statut : 【DOC】 / 【LIT】 / 【RECO】 / 【HYP】 / 【SPEC】. Les références marquées « à vérifier » doivent être confirmées par l'auteur avant citation.

```
CHOIX : · QUESTION : · ALTERNATIVES : · LITTÉRATURE : · JUSTIFICATION : · HYPOTHÈSE IMPLICITE :
IMPLÉMENTATION : · TEST : · VALIDATION : · LIMITES : · CHAPITRE : · STATUT :
```

---

## Fiche 1 — Satisficing plutôt que MAUT
Reprise intégrale de la feuille de route §19, Fiche 1. **Implémentation :** `decision/satisficing.py` (règle lexicographique non compensatoire sur `attended_needs`, troncature à `max_alternatives`, projection sur `planning_horizon`). **Test :** `max_alternatives=1, planning_horizon=0` ⇒ règle `reactive` ; aspiration 0 ⇒ première alternative. **Chapitre :** 3 §3.4, 6 §6.2.

## Fiche 2 — Pas de HTN
Reprise intégrale de la feuille de route §19, Fiche 2. **Implémentation :** `decision/plans.py` + `config/plans.yaml`. **Validation :** métrique `no_applicable_plan_rate` ≤ 5 % (= `no_applicable_plan` / adoptions tentées ; porte G2.8). **Chapitre :** 3 §3.6, 9.

## Fiche 3 — Les NTA comme couche de mesure, pas de mécanisme
Reprise intégrale de la feuille de route §19, Fiche 3. **Implémentation :** `nta/accounts.py` + `nta/attribution.py` (mesure comportementale) et `nta/imputation.py` (règle du manuel), sans import croisé (contrat C3). **Chapitre :** 4 §4.3, 8, 9.

---

## Fiche 4 — Ledger en double entrée comme source unique de vérité
- **CHOIX :** tout mouvement de valeur est une écriture (src, dst, montant, catégorie, bénéficiaire) dans un journal à double entrée ; les états des agents n'en sont que des caches.
- **QUESTION :** comment garantir que les identités NTA bouclent exactement et localiser toute fuite ?
- **ALTERNATIVES :** calcul des NTA à partir des états à chaque pas ; comptabilité simple entrée par agent.
- **LITTÉRATURE :** comptabilité en partie double (standard) ; UN NTA Manual (2013) pour la nomenclature des flux — à vérifier pour la table de correspondance des catégories.
- **JUSTIFICATION :** les identités deviennent des agrégations sur le journal ; une fuite est localisable à l'écriture près (pas, compte, catégorie) ; les tests d'injection prouvent que les invariants détectent les fautes.
- **HYPOTHÈSE IMPLICITE :** toutes les grandeurs NTA utiles sont des flux monétaires observables dans le modèle (le temps domestique, NTTA, est traité à part).
- **IMPLÉMENTATION :** `economy/ledger.py`, `Decimal` quantifié à 0,01.
- **TEST :** somme globale des soldes = 0 ; cache = Ledger ; injection d'une écriture fautive ⇒ `InvariantViolation`.
- **VALIDATION :** V-1/V-2.
- **LIMITES :** coût mémoire du journal en population → collecte du Ledger désactivable au-delà de 100 foyers (invariants calculés en flux, sans stockage).
- **CHAPITRE :** 4, 5. **STATUT :** 【RECO】.

## Fiche 5 — Attribution du pot commun par parts de propriété ω
- **CHOIX :** le pot, l'épargne et la dette du foyer sont la propriété conjointe des parents (ω = 0,5/0,5 par défaut) ; les transferts intra-ménage comportementaux sont dérivés des écritures selon ces parts (02 §9).
- **QUESTION :** comment mesurer des transferts individuels quand le foyer met ses revenus en commun ?
- **ALTERNATIVES :** (a) convention NTA du chef de ménage unique propriétaire ; (b) pot comme entité distincte (rompt Σ τ intra = 0) ; (c) comptes strictement individuels (contredit la mise en commun observée).
- **LITTÉRATURE :** UN NTA Manual (2013), transferts privés intra-ménage ; modèles collectifs (Chiappori) pour la notion de partage — à vérifier.
- **JUSTIFICATION :** conserve Σ τ intra = 0 par construction ; rend la convention comparable à la règle ONU (cas ω_head = 1) ; ω est un paramètre explicite discutable plutôt qu'une hypothèse cachée.
- **HYPOTHÈSE IMPLICITE :** 【HYP】 la propriété des actifs du foyer est partagée selon des parts fixes ; dans le contexte sénégalais (polygamie, ménages élargis), c'est une simplification.
- **IMPLÉMENTATION :** `nta/attribution.py`. **TEST :** avec ω_head = 1, l'attribution comportementale et l'imputation ONU coïncident sur un foyer où seul le chef a un revenu (cas jouet).
- **VALIDATION :** V-2. **LIMITES :** ω n'est pas observé ; sensibilité de `behav_vs_imputed_gap` à ω à rapporter. **CHAPITRE :** 4 §4.3, 9. **STATUT :** 【SPEC】.

## Fiche 6 — Ordonnancement en trois temps
- **CHOIX :** Temps 1 perception & demandes ; Temps 2 arbitrage du foyer ; Temps 3 action & comptabilité.
- **QUESTION :** dans quel ordre individus et foyer agissent-ils pour éviter dépenses non financées et annulations ?
- **ALTERNATIVES :** pipeline initial (action puis coordination) ; activation asynchrone aléatoire.
- **LITTÉRATURE :** Grimm et al. (2020), « Process overview and scheduling ».
- **JUSTIFICATION :** audit, problème 4 de la feuille de route ; aucune dépense sans allocation préalable.
- **HYPOTHÈSE IMPLICITE :** les demandes sont simultanées au sein d'un mois (pas de négociation itérative).
- **IMPLÉMENTATION :** `model/scheduler.py`. **TEST :** invariance à l'ordre des personnes au Temps 1. **CHAPITRE :** 3 §3.3. **STATUT :** 【RECO】.

## Fiche 7 — Une seule fonction d'allocation paramétrée
- **CHOIX :** `allocate()` pure ; les modes unitaire / poids fixes / poids variables / sphères séparées sont des paramètres ou des découpages de budget, pas des classes.
- **QUESTION :** comment comparer des mécanismes de décision du foyer (E6) sans multiplier les points de variation ?
- **ALTERNATIVES :** patron Strategy avec une classe par mécanisme ; résolution d'un problème de Nash.
- **LITTÉRATURE :** Beal Cohen et al. (2021) pour le design de comparaison ; Lundberg & Pollak (1993) pour les sphères séparées — à vérifier.
- **JUSTIFICATION :** principe « un seul point polymorphe » (S1) ; les mécanismes partagent la même logique de paliers et de rationnement, seuls les poids et le périmètre du budget changent — l'écart mesuré en E6 est donc attribuable aux poids, pas à des implémentations différentes.
- **HYPOTHÈSE IMPLICITE :** un foyer non unitaire peut être approximé par des poids de rationnement.
- **TEST :** propriétés 90 §2.5. **CHAPITRE :** 4 §4.5. **STATUT :** 【SPEC】.

## Fiche 8 — L'affect module le processus, il ne produit pas d'utilité
- **CHOIX :** l'appraisal produit émotions et stress ; un `ModulationEngine` transforme le `CognitiveProfile` en `EffectiveCognitiveProfile` (horizon, alternatives, aspiration, β, engagement, λ) ; le moteur de décision ne lit jamais l'affect.
- **QUESTION :** sous-question 2 du mémoire — articuler dimensions « dures » et « molles ».
- **ALTERNATIVES :** émotions comme termes d'une utilité ; OCC complet (22 émotions) ; aucune émotion.
- **LITTÉRATURE :** Marsella & Gratch (2009, EMA) ; Mani et al. (2013) ; Lazarus (appraisal) — à vérifier.
- **JUSTIFICATION :** conserve D3 (non compensatoire) ; correspond à l'interprétation « bande passante cognitive » de la rareté ; rend la boucle B3 testable par simple bascule.
- **HYPOTHÈSE IMPLICITE :** 【HYP】 la forme fonctionnelle de la modulation (linéaire par défaut). C'est l'hypothèse la plus fragile du modèle ; une variante sigmoïde est fournie pour un test de robustesse.
- **TEST :** stress = 0 ⇒ profil de base ; contrat d'import C4. **VALIDATION :** E4, sensibilité sur `affect.modulation.*`. **CHAPITRE :** 3, 6, 8, 9. **STATUT :** 【RECO】 fondé 【LIT】.

## Fiche 9 — Mémoire à activation décroissante (emprunt unique à ACT-R)
- **CHOIX :** mémoire épisodique bornée ; activation de niveau de base `A = ln Σ (t − tⱼ)^(−d)` ; éviction par activation minimale.
- **QUESTION :** de quoi se souvient un agent, et comment ce souvenir pèse-t-il sur ses attentes, son point de référence et son aspiration ?
- **ALTERNATIVES :** fenêtre glissante ; moyenne mobile exponentielle ; ACT-R complet.
- **LITTÉRATURE :** Anderson & Lebiere (ACT-R) pour l'équation d'activation — à vérifier ; D5.
- **JUSTIFICATION :** donne à la capacité mémoire un sens paramétrique (bébé 0, parent 60) ; la répétition renforce ; coût négligeable.
- **HYPOTHÈSE IMPLICITE :** l'unité de temps de l'équation (mois) est transposée de l'échelle des millisecondes/secondes d'ACT-R ; c'est un emprunt de forme, pas une revendication psychologique.
- **TEST :** propriétés 90 §2.5. **CHAPITRE :** 3 §3.5. **STATUT :** 【RECO】.

## Fiche 10 — Pas mensuel, cohorte fixe, horizon 20 ans
- **CHOIX :** D11, D12, Q5.
- **QUESTION :** quelle résolution temporelle et quelle démographie pour reproduire la signature du LCD ?
- **ALTERNATIVES :** pas hebdomadaire ; microsimulation démographique (naissances, décès, formation des ménages).
- **JUSTIFICATION :** les flux NTA sont mensuels/annuels ; 20 ans suffisent à voir les enfants changer de position NTA ; la démographie endogène est un autre métier (Chap. 9).
- **LIMITES :** la retraite n'est pas couverte ; en population, la couverture des âges vient de la diversité des gabarits et du jitter d'âge, pas du vieillissement. **CHAPITRE :** 3 §3.2, 9. **STATUT :** 【RECO】.
