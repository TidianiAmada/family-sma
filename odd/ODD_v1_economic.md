# ODD-V1 — Baseline économique

> **Brouillon généré — à réviser et s'approprier par l'auteur ; devient Chap. 3–5.**
> Décrit **exactement** le modèle V1 tel qu'implémenté (spécification : `specs/10_SPEC_V1_ECONOMIC.md`). Autoportant. Toute divergence code/ODD se corrige dans le même commit.

---

## Correspondance avec le mémoire

| Section ODD | Chapitre / section du mémoire |
|---|---|
| 1 Purpose and patterns | Chap. 1 (problématique) ; Chap. 6 §patterns |
| 2 Entities, state variables, scales | Chap. 3 §3.2 |
| 3 Process overview and scheduling | Chap. 3 §3.3 + schéma du pipeline |
| 4 Design concepts | Chap. 3 §3.1 |
| 5 Initialization | Chap. 5 §5.3 ; Chap. 6 §6.1 |
| 6 Input data | Chap. 4 §4.6 ; Chap. 6 §6.3 |
| 7 Submodels 7.1–7.9 (économiques) | Chap. 4 §4.1–4.4 |
| 7 Submodels 7.10–7.12 (NTA) | Chap. 4 §4.3 ; Chap. 5 |

---

## 1. Purpose and patterns

La V1 vérifie qu'un foyer de six membres, représenté par une architecture d'agent unique et des règles économiques simples, produit des flux **comptablement cohérents** et une **signature du déficit du cycle de vie** correcte par membre. Elle ne prétend à aucun réalisme comportemental.

Pattern visé au niveau d'un foyer : signe du LCD — positif pour le bébé, l'enfant et l'adolescent, négatif pour les parents — sur toute la période (forme individuelle de P1). Critère binaire associé : identités NTA bouclées à 0,01 FCFA près à chaque pas.

## 2. Entities, state variables and scales

### 2.1 `PersonAgent` (une seule classe)

| Variable | Type / domaine | Description |
|---|---|---|
| `person_id`, `household_id` | identifiants | |
| `role` | étiquette | descriptive, jamais utilisée par la logique |
| `profile_key` | clé | profil cognitif courant ; change avec l'âge |
| `age_months` | entier ≥ 0 | |
| `capabilities` | ensemble | du profil : `work, consume, save, seek_care, study, rest, …` |
| `max_alternatives` | entier ≥ 1 | nombre maximal d'alternatives examinées |
| `planning_horizon` H | entier ≥ 0 (mois) | horizon de projection |
| `attended_needs` | liste ordonnée | besoins vérifiés, par priorité |
| `impulsivity` ι | [0, 1] | probabilité de ne vérifier que le premier besoin |
| `aspiration` θ_k | [0, 1] par besoin | seuils, **fixes** en V1 (= `aspiration_init`) |
| `employment` | {formel, informel, chômeur, étudiant, inactif} | |
| `wage_monthly` | FCFA | salaire de référence à temps plein |
| `labor_supply` | [0, 1] | 1 si employé, 0 sinon (constant en V1) |
| `pooling_rate` | [0, 1] | part du revenu net versée au pot |
| `wallet` | FCFA ≥ 0 | portefeuille personnel |
| `health` | [0, 1] | |
| `sick`, `cared`, `episode_months`, `care_need` | | épisode de maladie |
| `labor_capacity` | [0, 1] | `clip((health − h_min)/(1 − h_min), 0, 1)` |
| `school_status` | {pas en âge, inscrit, abandon, terminé} | |
| `level_k`, `sat_k` | [0, 1] | niveau lissé et satisfaction instantanée des 6 besoins |
| `habitual`, `last_grant_ratio_k`, `envelope` | | mémoire de travail minimale (pas précédent uniquement) |

Six profils : `baby`, `child`, `adolescent`, `young_adult`, `mother`, `father` (valeurs : `config/cognitive_profiles.yaml`). Gradation : `max_alternatives` 1/2/3/5/8/8 ; H = 0/1/3/12/24/24 mois. Seuls `capabilities`, `max_alternatives`, `planning_horizon`, `attended_needs`, `aspiration_init` et `impulsivity` agissent en V1 ; les autres paramètres du profil (`aspiration_adapt`, `memory`, `intention_commitment`, `discounting` en V2 ; `risk`, `stress_sensitivity` en V3) sont lus et validés au chargement mais restent sans effet (03 §3).

### 2.2 `HouseholdAgent`

| Variable | Description |
|---|---|
| `members` | identifiants des personnes |
| `pot`, `savings`, `debt` | FCFA ; la dette est un passif ≥ 0 |
| `credit_limit` | κ × revenu mensuel moyen (12 mois) |
| `arrears_months` | mois consécutifs d'échéance impayée |
| `weights` w_i | poids d'allocation (Σ = 1), fixes |
| `ownership` ω_i | parts de propriété du pot commun (défaut père 0,5 / mère 0,5) |
| `head_id` | chef de ménage (convention ONU, mesure uniquement) |
| `allocation_mode` | `fixed_weights` (référence) ou `unitary` |

### 2.3 Environnement

Indice des prix P_t = (1 + π)^(t/12) × chocs ; indice des salaires W_t = (1 + g)^⌊t/12⌋ ; probabilités de chocs d'emploi et de santé ; politiques publiques (impôt à la source sur l'emploi formel, consommation publique en nature d'éducation et de santé, transferts en espèces selon le scénario) ; banque (taux d'épargne et d'emprunt).

### 2.4 Ledger

Journal en double entrée. Comptes internes : portefeuille de chaque personne, pot, épargne, prêt (passif). Comptes externes : employeur, marché, État, banque, autres ménages. Chaque écriture : pas, foyer, source, destination, montant > 0, catégorie, besoin, bénéficiaire. Les grandeurs NTA sont des agrégations de ce journal.

### 2.5 Échelles

Pas d'un mois ; horizon 240 mois (variantes 120 / cycle de vie) ; aucun espace ; FCFA ; cohorte fixe.

## 3. Process overview and scheduling

Pour chaque pas t :

**0. Environnement.** Application des événements de scénario datés (perte d'emploi, épisode de santé, choc de prix ou de revenu, changement de politique).

**Temps 1 — perception et demande** (personnes en ordre aléatoire ; l'ordre n'a pas d'effet car les demandes sont arbitrées simultanément) :
1. mise à jour de la santé (7.4) ;
2. construction de la perception (besoins, exigences r_k, taux d'allocation passé, enveloppe, habitude) ;
3. décision (7.7) → demandes priorisées + trace.

**Temps 2 — arbitrage du foyer** :
4. transitions d'emploi, versement du revenu du travail, impôt à la source (7.2–7.3) ;
5. transferts publics en espèces ; intérêts sur l'épargne et la dette ; mise en commun (7.3) ; mise à jour du plafond de crédit (7.9) ;
6. engagements (logement, échéance) puis allocation par paliers (7.8) ; écritures de retrait, d'emprunt, de remboursement, de dépôt ;
7. notification des allocations.

**Temps 3 — action et comptabilité** :
8. consommation financée par le pot (au bénéfice nominatif de chaque membre), complément depuis les portefeuilles, consommation publique en nature (7.6) ;
9. mise à jour des satisfactions et niveaux de besoins, de la scolarité ;
10. calcul NTA depuis le Ledger (7.10–7.11), vérification des invariants (7.12) — une violation arrête le run ;
11. observation (collecte) ; **puis** vieillissement d'un mois et transitions de profil (7.1).

## 4. Design concepts

- **Basic principles** : satisficing non compensatoire (Simon) ; continuum réactif → délibératif par `max_alternatives` et H ; NTA comme mesure ex post.
- **Emergence** : trajectoires de dette et d'épargne, volumes de transferts intra-familiaux, LCD par membre.
- **Adaptation** : aucune adaptation des règles ; le taux d'allocation et l'enveloppe du pas précédent orientent l'ordre et la projection des alternatives.
- **Objectives** : acceptabilité lexicographique des besoins attendus vs θ ; pas d'utilité.
- **Learning** : aucun.
- **Prediction** : projection naïve sur H mois à taux d'allocation constant ; pas d'actualisation.
- **Sensing** : propres états, allocations passées, épargne du foyer ; pas les demandes des autres.
- **Interaction** : via le budget commun (rationnement) et la mise en commun.
- **Stochasticity** : emploi (perte, retour), revenu informel log-normal d'espérance 1, épisodes de santé et gravité, impulsivité, ordre de perception. Sous-flux nommés seedés.
- **Collectives** : le foyer.
- **Observation** : tables Parquet par pas ; indicateurs ; profils par âge.

## 5. Initialization

| Membre | Profil | Âge | Emploi | Salaire de réf. (FCFA/mois) | Mise en commun |
|---|---|---|---|---|---|
| Père | father | 45 | formel | 250 000 | 1,0 |
| Mère | mother | 40 | informel | 120 000 | 0,8 |
| Jeune adulte | young_adult | 20 | étudiant (inscrit) | 60 000 si employé | 0,5 |
| Adolescent | adolescent | 15 | étudiant (inscrit) | — | — |
| Enfant | child | 9 | étudiant (inscrit) | — | — |
| Bébé | baby | 1 | inactif | — | — |

Actifs : pot 50 000, épargne 150 000, dette 0, posés au Ledger par écritures d'ouverture au pas −1 (exclues des NTA). Besoins : niveau 1 ; sécurité = épargne / (3 × dépense mensuelle initiale estimée). Santé 1. ω : père 0,5, mère 0,5 ; chef ONU : père. Poids d'allocation (avant normalisation) : 1 / 1 / 0,8 / 0,7 / 0,6 / 0,6. Toutes ces valeurs sont des **placeholders** : le run est marqué illustratif.

## 6. Input data

Aucune donnée externe obligatoire en V1 (source `synthetic`). Les scénarios fournissent des événements datés : `job_loss` (père, mois 36), `illness` (enfant, mois 48, gravité 0,6, 6 mois), `family_allowance` (10 000 FCFA par enfant de moins de 15 ans au pot dès le mois 24), `free_care` (soins pris en charge par l'État dès le mois 24), `economic_shock` (prix +20 %, revenu informel −15 % au mois 60).

## 7. Submodels

### 7.1 Vieillissement et transitions de profil
`age_months` augmente de 1 par pas. Le profil change lorsque l'âge atteint 5 ans (bébé → enfant), 13 ans (enfant → adolescent), 18 ans (adolescent → jeune adulte) ; θ est alors réinitialisé à l'aspiration initiale du nouveau profil. Les besoins actifs suivent les plages d'âge (`active_ages`).

### 7.2 Travail et emploi
Revenu brut : `Yl = wage × W_t × labor_supply × labor_capacity × m`, avec m = 1 (formel) ou m ~ LogNormal(−σ²/2, σ), σ = 0,15 (informel). Transitions mensuelles : perte d'emploi p = 0,004 (formel) / 0,010 (informel) ; retour à l'emploi p = 0,05 / 0,10 selon le secteur du dernier emploi (informel si jamais employé), formel avec probabilité 0,2. Fin d'études (25 ans) ⇒ chômeur en recherche. Seules les personnes dotées de la capacité `work` perçoivent un revenu.

### 7.3 Impôt et mise en commun
Impôt à la source : 10 % du revenu formel, 0 % informel. Mise en commun : `pooling_rate × (Yl − impôt)` vers le pot ; le reste reste au portefeuille.

### 7.4 Santé
Hors épisode : probabilité mensuelle d'épisode selon l'âge (0,06 / 0,03 / 0,02 / 0,04 à 0, 5, 18, 50 ans) ; gravité ~ N(0,25 ; 0,10) bornée [0,05 ; 0,9] retranchée à la santé ; coût de l'épisode (25 000 FCFA avant 18 ans, 40 000 ensuite, × P_t) demandé une fois. Récupération : +0,15/mois si soigné, +0,03 sinon ; fin d'épisode quand la santé revient à 0,05 du niveau antérieur ou après 6 mois. Hors épisode : +0,01/mois jusqu'à 1. Capacité de travail : seuil h_min = 0,3.

### 7.5 Besoins
`level_k,t = ρ_k·level_k,t−1 + (1 − ρ_k)·sat_k,t` avec ρ = 0,5 (alimentation, repos), 0,8 (santé), 0,9 (éducation, logement, sécurité). Satisfactions : alimentation et soins de routine = dépense / exigence par âge (bornée à 1) ; éducation = 1 si frais payés, 0 sinon ; logement = part payée / part due ; repos = `clip(1 − 0,6·max(0, labor_supply − 0,8), 0, 1)` ; santé en épisode = 1 si soigné, sinon 0,2 × ratio de routine ; sécurité = épargne / (3 × dépense mensuelle moyenne sur 12 mois), commune au foyer.

### 7.6 Scolarité et consommation publique
Inscription à 6 ans ; frais mensuels indivisibles par âge ; trois refus consécutifs ⇒ abandon ; sortie à 25 ans. Consommation publique en nature (Cg) : éducation (6 000 / 9 000 / 12 000 FCFA selon l'âge) pour tout inscrit ; santé de routine (1 000 à 3 000 selon l'âge).

### 7.7 Décision (satisficing)
1. Besoins demandables : actifs, monétaires, hors logement (engagement du foyer), sous réserve des capacités ; épargne seulement pour les propriétaires (ω > 0).
2. Alternatives = paniers de montants par besoin, niveaux {plein = r_k, réduit = 0,7·r_k, minimal} (indivisibles : {r_k, 0} ; épargne : {ω·écart/12, ω·écart/24, 0}). Ordre de saillance : panier habituel, puis ordre lexicographique « plein d'abord » selon `attended_needs` ; si H ≥ 1, les paniers dont le total ne dépasse pas l'enveloppe attendue passent en tête. Seules les `max_alternatives` premières sont examinées.
3. Projection sur t = 0..H : `n̂_t = ρ·n̂_t−1 + (1 − ρ)·ŝ`, ŝ = min(1, montant × ê / r), ê = 1 si le panier tient dans l'enveloppe, sinon le taux accordé au pas précédent. Score `s_k = moyenne des n̂_t`.
4. Acceptable si `s_k ≥ θ_k` pour tout besoin attendu (ou pour le seul premier, avec probabilité ι). Choix : première alternative acceptable ; à défaut, repli lexicographique sur le premier besoin non satisfaisable. Règle « réactive » si `max_alternatives = 1` et H = 0.
5. Sortie : une demande par besoin (palier : essentiel pour l'alimentation et l'épisode de soin ; éducation ; autre pour les soins de routine ; épargne), priorité = rang du besoin.

### 7.8 Allocation du foyer
Financement dans l'ordre pot → épargne → emprunt. Engagements d'abord : logement (90 000 × P_t, réparti selon l'échelle OCDE modifiée 1 / 0,5 / 0,3), puis échéance = 5 % × (dette du mois précédent + intérêts du mois) (`min_repayment_share`). Puis paliers essentiel → éducation → autre → épargne : demande satisfaite si les ressources suffisent ; sinon indivisibles accordés en entier par poids décroissant tant qu'ils tiennent, divisibles au prorata poids × montant avec plancher. L'emprunt n'est mobilisable que pour les engagements et l'essentiel, dans la limite du plafond ; l'épargne n'est pas mobilisée pour le palier épargne. Mode unitaire : poids égaux et priorités du chef. Les montants accordés sont dépensés par le pot au bénéfice nominatif du membre ; une demande partielle ou refusée peut être complétée depuis le portefeuille personnel.

### 7.9 Crédit, dette, épargne
Taux mensuels issus des taux annuels (épargne 3 %, dette 18 %). `debt_t = debt_t−1 + intérêts + emprunts − remboursements`. Plafond : 3 mois de revenu moyen. Arriérés comptés si l'échéance n'est pas intégralement payée.

### 7.10 Mesure NTA (comportementale)
Par personne et par pas, depuis le Ledger : Yl, Cf, Cg, impôts, transferts publics, transferts intra-ménage, revenus d'actifs Ya, épargne S. Les transferts intra-ménage découlent de la **règle d'attribution du pot commun** : le pot, l'épargne et la dette appartiennent aux propriétaires selon ω ; une mise en commun par k transfère `x·ω_j` à chaque autre propriétaire j ; une dépense du pot au bénéfice de b est un transfert `x·ω_j` de chaque propriétaire j ≠ b vers b ; Ya et S du foyer sont attribués selon ω. Identité vérifiée :
`C_i − Yl_i = (τ⁺_i − τ⁻_i) + (Ya_i − S_i)`, avec `C = Cf + Cg`, `S_i = Δwallet_i + ω_i·Δ(pot + épargne − dette)`.

### 7.11 Imputation ONU (comparaison)
Le chef de ménage détient tous les actifs du foyer. Pour chaque non-chef : `τ_imp_i = Cf_i + Δwallet_i − (Yl_i − impôt_i + transferts publics en espèces_i)` ; le chef finance la somme : `τ_imp_head = −Σ τ_imp_i`. L'écart `τ_behav − τ_imp` est enregistré (résultat étudié au Chap. 8). Les deux calculs sont indépendants.

### 7.12 Invariants (échec dur)
Double entrée (somme des soldes nulle) ; variation de chaque compte = entrées − sorties ; non-négativité des actifs ; identité NTA individuelle (ε = 0,01 FCFA) ; somme nulle des transferts intra-ménage ; équation de désépargne du foyer `ΣYl + ΣYa + transferts publics en espèces nets d'impôts − ΣCf = ΣS` ; équation de la dette ; cohérence des allocations ; Σω = Σw = 1 ; somme nulle des transferts imputés.
