# 20 — Spécification V2 : architecture cognitive

> **Prérequis bloquant :** porte V1 verte (`docs/GATES.md`, critères de 10_SPEC_V1 et feuille de route §11).
> **Objectif scientifique (feuille de route §12) :** établir que l'architecture cognitive change les trajectoires économiques — et de combien.
> **Principe :** la V2 n'ajoute **aucun nouveau mécanisme de choix**. Le `SatisficingEngine` (voir 10_SPEC_V1 §7 (moteur de décision)) reste l'unique mécanisme. La cognition V2 agit en amont sur ses **entrées** : taux d'allocation attendus (mémoire), seuils θ (aspiration), ordre de saillance des alternatives (intention/plan), pondération temporelle D(t) (actualisation).
> Références de conception : Adam & Gaudou (2016) BDI en simulation sociale ; Jager & Janssen Consumat II (2012) ; Bratman (persistance des intentions) ; Simon (1955) ; Laibson (1997) si β-δ ; ten Broeke et al. (2016) pour E-SA.

---

## 1. Périmètre

| Élément | Statut | Module | Bascule de config |
|---|---|---|---|
| Croyances / désirs / intentions persistantes (BDI dégradé) | CORE | `cognition/beliefs.py`, `decision/plans.py` | `cognition.bdi.enabled` |
| Mémoire bornée à activation décroissante | CORE | `cognition/memory.py` | `cognition.memory.enabled` |
| Seuil d'aspiration adaptatif | CORE | `cognition/aspiration.py` | `loops.b2.enabled` |
| Bibliothèque de plans + replanification | CORE | `decision/plans.py`, `config/plans.yaml` | `cognition.bdi.enabled` |
| `CognitiveProfile` pleinement actif (paramètres V2 du tableau 03 §3) | CORE | `config/schemas.py` | `model.version: v2` |
| Analyse de sensibilité globale (Morris → Sobol) | CORE | `analysis/sensitivity.py` | — (voir 40/50) |
| Actualisation β-δ (naïf / sophistiqué) | **Optionnel, forte priorité** | `decision/discounting.py` | `cognition.discounting.enabled` |
| Poids de négociation variables | Optionnel | `agents/allocation.py` | `household_rules.allocation.mode: variable_weights` |
| NTTA (travail domestique valorisé) | Optionnel | `nta/ntta.py` | `nta.ntta.enabled` (nouvelle clé, §11) |
| Départ du jeune adulte (D13) | Optionnel (paramètre) | `agents/household.py`, plan `leave_household/*` | `household_rules.young_adult_can_leave` |

**Exclus de la V2 :** appraisal, émotions, stress, modulation, CPT, régime « sphères séparées », population de foyers (> 1 foyer uniquement via D13), calibration. Les champs correspondants restent à leur valeur neutre (02 §4).

**Activation :** `model.version: v2` active les blocs V2 ; chaque bloc reste désactivable individuellement (S8). Une personne n'utilise mémoire et plans que si son profil contient `remember` / `plan` dans `capabilities` (le bébé et l'enfant restent donc réactifs/simples sans branchement de code — D1).

## 2. Ordonnancement V2 dans les trois temps

Ajouts à la séquence de 01 §4 (les étapes V1 sont inchangées et dans le même ordre) :

```
TEMPS 1 (par personne, ordre seedé)
  1.1  remise à zéro des dépenses du pas, santé, fatigue, perception [V1 + fatigue]  (les niveaux de besoins sont lissés au Temps 3, après les actions — 10 §13)
  1.2  MemoryService.encode(épisodes « perçus » du pas : income, shock, refus du pas t−1)   [V2]
  1.3  beliefs.revise(percept, memory)                             [V2]
  1.4  beliefs.derive_desires(...)                                 [V2]
       [V3 : appraisal → affect → modulation → EffectiveCognitiveProfile s'insèrent ICI, entre 1.4 et 1.5 — 30 §2]
  1.5  intention = plans.deliberate(desires, beliefs, intention, profile_eff)   [V2] (adoption / persistance / reconsidération ; lit profile_eff.intention_commitment)
  1.6  alternatives = generate(capabilities, plan_step=intention.current_step)  [V1 + tête de saillance V2]
  1.7  SatisficingEngine.decide(...) avec ê_k (mémoire) et D(t) (actualisation)  [V1 + entrées V2]
  1.8  DemandSet → foyer
TEMPS 2  inchangé, sauf allocate(mode=variable_weights) si activé
TEMPS 3
  3.1  act(allocation) + complément personnel ; lissage des niveaux de besoins   [V1]
  3.2  outcome = évaluer le pas (sat_k réalisées, demandes refusées, étape de plan réussie ?)  [V2]
  3.3  MemoryService.encode(consumption, allocation_refused, plan_outcome)   [V2]
  3.4  aspiration.update(outcome)                                  [V2]
  3.5  plans.advance(intention, outcome) — succès / étape suivante / replanification / échec   [V2]
  3.6  NTA + invariants + collecte                                 [V1]
  3.7  départ du foyer éventuel (D13) appliqué en FIN de pas, après la comptabilité   [V2]
```

Règle : aucune étape V2 n'écrit dans le `Ledger`. Toutes les conséquences monétaires de la cognition passent par les demandes (Temps 1) et leur exécution (Temps 3) — la conservation V1 n'est donc pas touchée.

## 3. `MemoryService` (`cognition/memory.py`) — service transversal

### 3.1 Modèle

Mémoire épisodique **par personne**, bornée à `profile.memory.capacity` épisodes (`Episode`, 02 §6). Activation de niveau de base (emprunt unique à ACT-R, D5) :

```
A_i(t) = ln( Σ_{t_j ∈ rehearsals_i} (t − t_j)^(−d) )        avec t − t_j ≥ 1 (mois), d = profile.memory.decay
```

- **Rappel** : un épisode est rappelable si `A_i(t) ≥ retrieval_threshold`.
- **Bruit** : désactivé par défaut (déterminisme). Si `cognition.memory.noise_s > 0` (nouvelle clé, défaut 0), ajouter un bruit logistique d'échelle s tiré dans `rng["memory_noise"]` au moment du rappel.
- **Renforcement (rehearsal)** : un épisode rappelé et utilisé dans une décision reçoit `t` dans `rehearsals` (au plus 1 fois par pas). Les épisodes rappelés mais non utilisés ne sont pas renforcés.
- **Éviction** : à l'encodage, si la mémoire est pleine, retirer l'épisode d'activation minimale ; égalité → le plus ancien (`step` minimal), puis ordre lexicographique de `key` (déterminisme).
- **Fusion** : un nouvel épisode de même `(kind, key)` et même `step` remplace l'existant (pas de doublon intra-pas).
- `capacity = 0` ⇒ `encode` est un no-op et tous les rappels renvoient le vide (le bébé), sans test sur le rôle.

### 3.2 API (normative)

```python
class MemoryService:
    def __init__(self, capacity: int, decay: float, retrieval_threshold: float, noise_s: float, rng: np.random.Generator | None): ...
    def encode(self, episode: Episode) -> None
    def activation(self, episode: Episode, t: Step) -> float
    def recall(self, t: Step, kind: str | None = None, key_prefix: str | None = None, k: int | None = None) -> list[tuple[Episode, float]]
        # épisodes rappelables triés par activation décroissante ; renforce si mark_used() appelé ensuite
    def mark_used(self, episodes: Iterable[Episode], t: Step) -> None
    def weighted_mean(self, t: Step, kind: str, key_prefix: str | None = None, default: float | None = None) -> float | None
        # Σ softmax(A_i)·value_i sur les épisodes rappelables ; poids = exp(A_i)/Σexp(A_j) ; default si vide
    def recent_outcomes(self, goal: str, k: int, t: Step) -> list[Episode]       # aspiration, plans
    def plan_history(self, plan_id: str, t: Step) -> list[Episode]              # éviter un plan récemment échoué
    def reference_level(self, kind: str, t: Step) -> float | None               # V3 (CPT) — défini dès V2, = weighted_mean
    def size(self) -> int
    def snapshot(self) -> list[Episode]                                          # tests, collecte
```

`Episode` est immuable : le renforcement remplace l'instance (`dataclasses.replace`). Complexité visée : O(capacity) par rappel ; activation recalculée à la demande (pas de cache inter-pas, capacité ≤ 100).

### 3.3 Qui encode quoi, quand

| `kind` | `key` | `value` | `valence` | Encodé par / quand |
|---|---|---|---|---|
| `income` | `income:labor` | Yl du pas (FCFA) | signe de (Yl − expected_income)/expected_income, borné | Temps 1.2 (revenu du pas t−1, perçu) |
| `shock` | `shock:<type>` (job_loss, health_episode, price_shock, income_shock) | amplitude | −1 | Temps 1.2, événements du pas t−1 touchant la personne ou le foyer |
| `allocation` | `alloc:<need>` | taux accordé `granted/requested` ∈ [0,1] | 2·taux − 1 | Temps 3.3, pour chaque demande |
| `allocation_refused` | `refused:<need>` | montant refusé | −1 | Temps 3.3, statut REFUSED |
| `consumption` | `cons:total` | Cf du pas | 0 | Temps 3.3 |
| `plan_outcome` | `plan:<plan_id>/<step_index>` | 1 succès / 0 échec | ±1 | Temps 3.5 |
| `need` | `need:<k>` | sat_k réalisée | sat_k − θ_k | Temps 3.3 (sert l'aspiration) |

Seules les personnes ayant `remember` encodent. Avec les profils de 03 §3, l'enfant possède `remember` (capacité 10 : mémoire simple, « apprentissage » DOC §3) ; le bébé n'a ni capacité mémoire ni `remember`. Voir Détails tranchés n°1.

## 4. Croyances (`cognition/beliefs.py`)

`revise(person, percept, memory, t) -> dict[str, Belief]` — **règles déterministes**, pas d'inférence probabiliste. Toute croyance non recalculée garde sa valeur et son `updated_step`.

| Clé | Type | Règle de dérivation | Confiance |
|---|---|---|---|
| `expected_income` | float (FCFA) | `memory.weighted_mean(kind="income")` ; défaut = `wage_monthly × labor_supply × labor_capacity` | `min(1, n_rappelés / confidence_saturation_n)` |
| `income_stable` | bool | CV des épisodes `income` rappelés < `income_cv_stable` (≥ `min_episodes_stable` épisodes) | `min(1, n/confidence_saturation_n)` |
| `employed` | bool | `employment ∈ {EMPLOYED_FORMAL, EMPLOYED_INFORMAL}` (perception directe) | 1 |
| `job_lost` | bool | événement `job_loss` touchant la personne dans les `job_loss_memory_months` derniers mois **et** non `employed` | 1 |
| `job_at_risk` | bool | `employment = EMPLOYED_INFORMAL` et (¬`income_stable` ou ≥ 1 épisode `shock:income_shock` rappelable) ; ou épisode `shock:job_loss` rappelable concernant un autre membre | 0,5 + 0,5·`min(1, n_shocks/3)` |
| `household_job_lost` | bool | un membre pourvoyeur (`work` ∈ capabilities, pooling > 0) a `employment = UNEMPLOYED` (perçu via `household_view`) | 1 |
| `debt_manageable` | bool | `debt_to_income` (vue foyer) < `debt_manageable_dti` | 1 |
| `debt_critical` | bool | `arrears_months ≥ debt_critical_arrears` (vue foyer) | 1 |
| `buffer_ok` | bool | `sat_security ≥ θ_security` | 1 |
| `child_sick:<pid>` | bool | membre `pid` avec `sick = True` et âge < `adult_age` | 1 |
| `school_at_risk:<pid>` | bool | membre `pid` `ENROLLED` et ≥ 1 refus de frais d'éducation dans les `school_risk_window_months` derniers mois (perçu via `household_view.refusals`) | 1 |
| `out_of_school:<pid>` | bool | `pid` `DROPPED_OUT` et âge < `school_exit_age.secondary` | 1 |
| `expected_alloc:<k>` | float ∈ [0,1] | `ê_k = memory.weighted_mean(kind="allocation", key_prefix=f"alloc:{k}")` ; défaut = taux accordé au pas précédent (règle V1), 1,0 au départ | `min(1, n/6)` |
| `can_leave` | bool | `young_adult_can_leave` ∧ `leave_household` ∈ capabilities ∧ âge ≥ `leave_rule.min_age` ∧ `months_employed ≥ leave_rule.min_months_employed` | 1 |

**Seuils (B2 — aucun nombre en dur) :** tous les seuils et coefficients de cette table sont des clés de `plans.beliefs` (03 §14) : `income_cv_stable: 0.10`, `min_episodes_stable: 3`, `confidence_saturation_n: 6`, `job_loss_memory_months: 12`, `debt_manageable_dti: 1.0`, `debt_critical_arrears: 2`, `school_risk_window_months: 3`, `adult_age: 18`, `job_risk_conf_base: 0.5`, `job_risk_shock_saturation: 3` (confiance de `job_at_risk` = `job_risk_conf_base + (1 − job_risk_conf_base)·min(1, n_shocks/job_risk_shock_saturation)`).

**Perception (sensing) :** chaque personne perçoit son état, l'état agrégé du foyer (`household_view` : dette, arriérés, ratio dette/revenu, statut d'emploi et santé des membres, refus du pas précédent par membre) et les événements la concernant. Elle **ne perçoit pas** les paramètres des autres ni le budget futur. `household_view` est un objet immuable construit par le foyer en début de Temps 1.

**Sans `remember` :** les croyances dérivées de la mémoire prennent leur valeur par défaut ; les croyances perceptives sont calculées. Sans `plan` : les croyances sont calculées mais ne servent qu'à `ê_k`.

## 5. Désirs (`beliefs.derive_desires`)

Deux sources, fusionnées puis triées par priorité décroissante (égalité → ordre de `attended_needs`, puis `goal` lexicographique) :

1. **`need_deficit`** — pour chaque k ∈ `attended_needs` avec `level_k < θ_k` :
   `goal = f"satisfy:{k}"`, `priority = (θ_k − level_k) × (n_att − rang_k) / n_att` où `rang_k` ∈ {0..n_att−1}.
2. **`long_term`** — générés si la condition est vraie et la capacité présente :

| `goal` | Condition | Capacité requise | Priorité |
|---|---|---|---|
| `cope_income_loss` | `job_lost` ∨ `household_job_lost` | `plan` | 0,9 |
| `repay_debt` | ¬`debt_manageable` ∨ `debt_critical` | `plan`, `save` | 0,8 si `debt_critical`, sinon 0,5 |
| `build_buffer` | ¬`buffer_ok` ∧ `debt_manageable` | `save`, `plan` | 0,4 |
| `educate:<pid>` | `school_at_risk:<pid>` ∨ `out_of_school:<pid>` | `plan` et âge ≥ 18 | 0,6 |
| `health_crisis:<pid>` | `child_sick:<pid>` ∨ (pid = soi ∧ `sick`) | `plan` | 0,85 |
| `find_job` | ¬`employed` ∧ `seek_job` ∈ capabilities ∧ employment ≠ STUDENT | `seek_job` | 0,7 |
| `leave_household` | `can_leave` | `leave_household` | 0,3 |

Ces priorités sont des paramètres : `config/plans.yaml → desires.long_term.<goal>.priority` (registre : `FIX`, exploré par Morris si E-SA les inclut).

## 6. Intentions et reconsidération (`decision/plans.py`)

Une seule intention active par personne (`CognitiveState.intention`). Les sous-buts vivent dans la pile du plan.

```python
def deliberate(desires, beliefs, intention, profile_eff, library, memory, t) -> Intention | None:
    top = first(d for d in desires if library.applicable(d.goal, beliefs, memory, t))
    if intention is None or intention.status != ACTIVE:
        return adopt(top) if top else None                       # événement intention_adopted
    if goal_achieved(intention, beliefs):                         # success du plan
        return close(intention, SUCCEEDED) then adopt(top)
    if goal_irrelevant(intention, desires):                       # le désir a disparu
        return close(intention, DROPPED) then adopt(top)
    p_int = priority_of(intention.goal, desires)
    if top and top.goal != intention.goal and top.priority > p_int * (1 + profile_eff.intention_commitment):
        suspend(intention); return adopt(top)                     # SUSPENDED (reprise possible, max 1 suspendue)
    return intention                                              # persistance (Bratman)
```

- `intention_commitment = 0` ⇒ l'agent suit toujours le désir le plus prioritaire (reconsidération permanente, « open-minded ») ; valeur élevée ⇒ « single-minded ».
- **Intention suspendue :** au plus une ; reprise quand l'intention active se termine et que son désir existe encore ; abandonnée (`DROPPED`) après `max_duration_months` du plan.
- `adopt(d)` choisit le **premier plan applicable** pour `d.goal` dans l'ordre `priority` croissant, en excluant les plans ayant un épisode `plan_outcome` d'échec rappelable (`memory.plan_history`) ; si tous sont exclus, l'exclusion est levée (repli : mieux vaut réessayer qu'être bloqué).

## 7. Bibliothèque de plans

### 7.1 Mini-DSL des conditions (`decision/plans.py → ConditionParser`)

Parser **écrit à la main** (descente récursive) ou `lark` en mode LALR avec grammaire figée. **`eval`/`exec`/`ast.literal_eval` interdits.** Les conditions sont compilées une fois au chargement de `plans.yaml` en arbres immuables ; une condition invalide ⇒ `ConfigError` au chargement (jamais à l'exécution).

```ebnf
expr        = or_expr ;
or_expr     = and_expr , { "or" , and_expr } ;
and_expr    = not_expr , { "and" , not_expr } ;
not_expr    = [ "not" ] , comparison ;
comparison  = operand , [ comp_op , operand ] ;          (* operand seul ⇒ booléen *)
comp_op     = "==" | "!=" | "<" | "<=" | ">" | ">=" ;
operand     = number | boolean | string | ref | "(" , expr , ")" ;
ref         = namespace , "." , ident , [ ":" , selector ] ;
namespace   = "belief" | "need" | "aspiration" | "econ" | "phys" | "person" | "household" | "self" | "plan" ;
selector    = "self" | "any_child" | "any_member" | "target" ;
ident       = letter , { letter | digit | "_" } ;
number      = [ "-" ] , digit , { digit } , [ "." , digit , { digit } ] ;
boolean     = "true" | "false" ;
string      = "'" , { char - "'" } , "'" ;

(* Champs de montant (clé `amount:` d'une étape) : grammaire SÉPARÉE et restreinte — pas d'arithmétique générale *)
amount      = number | symbol | ref | number , "*" , ( ref | symbol ) ;
symbol      = "gap_essential" | "arrears_amount" | "freed_amount" | "extra_income" | "debt_service"
            | "care_need" , [ "(" , "target" , ")" ] ;     (* liste fermée, 20 §13 `amounts` *)
```

Résolution des références (table blanche — tout autre nom ⇒ `ConfigError`) :

| Référence | Valeur |
|---|---|
| `belief.<key>` | valeur de la croyance (bool/float) ; absente ⇒ `false` / `0` |
| `belief.<key>:any_child` | vrai si `<key>:<pid>` vrai pour au moins un membre < 18 ans ; `:target` = membre cible de l'intention (`educate:<pid>`) |
| `need.<k>` | `level_k` ; `aspiration.<k>` = θ_k |
| `econ.<field>` | champs de `EconomicState` (liste blanche : `employment_*` booléens, `wage_monthly`, `labor_supply`, `pooling_rate`, `wallet_cached`, `months_unemployed`) |
| `household.<field>` | `household_view` : `debt_to_income`, `arrears_months`, `savings`, `pot`, `credit_headroom`, `n_members`, `debt_service` (échéance minimale du mois) |
| `phys.<field>` | `PhysicalState` (liste blanche : `sick`, `health`, `labor_capacity`) ; sélecteur `:self` (défaut) ou `:target` |
| `person.<field>` | attributs de `PersonAgent` (liste blanche : `in_household`, `age_years`, `enrolled`) |
| `self.<cap>` | vrai si la capacité est dans le profil (ex. `self.work`) |
| `plan.step_failures`, `plan.months_active` | état de l'intention courante |

### 7.2 Format d'un plan (`config/plans.yaml`)

```yaml
plans:
  - id: <goal_family>/<variant>         # unique
    goal: <goal> | "<goal>:*"            # ":*" = paramétré par une cible (pid)
    context: "<expr>"                     # applicabilité
    priority: <int>                       # ordre d'essai (1 = premier)
    body:                                 # étapes exécutées une par pas (sauf `repeat`)
      - { action: <ActionKind>, need: <k>?, factor: <float>?, amount: <amount>? (grammaire « amount » de §7.1), target: target? , repeat: <int|until_success>? }
      - { subgoal: <goal> }               # empile le premier plan applicable de ce but
    success: "<expr>"                     # but atteint ⇒ SUCCEEDED
    failure: "<expr>"                     # échec du plan ⇒ replanification
    max_duration_months: <int>
desires:
  long_term: { <goal>: { priority: <float> } }
```

Sémantique d'une étape :
- **`action`** : produit une **alternative de tête** (§8). Elle réussit si l'alternative est acceptée par le satisficing **et** que la demande associée est accordée (GRANTED ou PARTIAL ≥ `amount_min`) ou que l'action non monétaire est exécutée ; sinon échec d'étape (`plan.step_failures += 1`).
- **`subgoal`** : empile un sous-plan (profondeur max 2 — **Détails tranchés n°4**) ; l'étape réussit quand le sous-plan réussit.
- **`repeat: until_success`** : l'étape reste courante tant que `success` du plan n'est pas atteint (borné par `max_duration_months`).

### 7.3 Bibliothèque complète (V2)

Les montants sont exprimés par rapport aux besoins (`factor` × r_k ou × montant habituel). « Habituel » = panier choisi au pas précédent.

| # | `id` | `goal` | `context` | `body` (étapes) | `success` | `failure` | durée max |
|---|---|---|---|---|---|---|---|
| 1 | `cope_income_loss/seek_and_cut` | `cope_income_loss` | `belief.job_lost and self.seek_job and not belief.debt_critical` | `seek_job (repeat until_success)` ‖ en parallèle : `reduce_consumption need=rest factor=0.5` au 1er pas ; `subgoal satisfy:food` | `belief.employed` | `plan.step_failures >= 3` | 6 |
| 2 | `cope_income_loss/draw_buffer` | `cope_income_loss` | `(belief.job_lost or belief.household_job_lost) and household.savings > 0` | `withdraw_savings amount=gap_essential` (repeat until_success) ; `reduce_consumption need=rest factor=0.5` | `belief.employed or not belief.household_job_lost` | `household.savings <= 0` | 6 |
| 3 | `cope_income_loss/borrow` | `cope_income_loss` | `belief.household_job_lost and household.credit_headroom > 0 and not belief.debt_critical` | `request_borrow amount=gap_essential` ; `subgoal satisfy:food` | `not belief.household_job_lost` | `household.credit_headroom <= 0 or belief.debt_critical` | 4 |
| 4 | `cope_income_loss/other_earner` | `cope_income_loss` | `belief.household_job_lost and self.work and not belief.job_lost` | `increase_labor factor=1.15` (repeat until_success) ; `contribute_more factor=1.0` | `not belief.household_job_lost` | `plan.step_failures >= 2` | 6 |
| 5 | `repay_debt/cut_and_repay` | `repay_debt` | `not belief.debt_critical and self.save` | `reduce_consumption need=rest factor=0.5` ; `repay_extra amount=0.1*household.debt_service` (repeat until_success) | `belief.debt_manageable` | `plan.step_failures >= 3` | 12 |
| 6 | `repay_debt/extra_work` | `repay_debt` | `self.work and econ.labor_supply < 1.1` | `increase_labor factor=1.15` ; `repay_extra amount=extra_income` (repeat until_success) | `belief.debt_manageable` | `plan.step_failures >= 3` | 12 |
| 7 | `repay_debt/use_savings` | `repay_debt` | `belief.debt_critical and household.savings > 0` | `withdraw_savings amount=arrears_amount` ; `repay_extra amount=arrears_amount` | `not belief.debt_critical` | `household.savings <= 0` | 2 |
| 8 | `build_buffer/regular_saving` | `build_buffer` | `belief.debt_manageable and self.save` | `save amount=0.1*belief.expected_income` (repeat until_success) | `belief.buffer_ok` | `plan.step_failures >= 4` | 24 |
| 9 | `build_buffer/cut_leisure` | `build_buffer` | `belief.debt_manageable and self.save and need.rest > aspiration.rest` | `reduce_consumption need=rest factor=0.7` ; `save amount=freed_amount` (repeat until_success) | `belief.buffer_ok` | `plan.step_failures >= 4` | 18 |
| 10 | `educate/pay_fees` | `educate:*` | `belief.school_at_risk:target` | `consume need=education target=target factor=1.0` (repeat 3) — demande portée au nom de la cible, tier EDUCATION, priorité 0 | `not belief.school_at_risk:target` | `plan.step_failures >= 2` | 6 |
| 11 | `educate/reenrol` | `educate:*` | `belief.out_of_school:target and household.debt_to_income < 1.5` | `consume need=education target=target factor=1.0` (repeat until_success) ; `reduce_consumption need=rest factor=0.7` | `not belief.out_of_school:target` | `plan.step_failures >= 3` | 12 |
| 12 | `health_crisis/pay_care` | `health_crisis:*` | `phys.sick:target` | `seek_care target=target` (repeat until_success) ; `subgoal satisfy:food` | `not phys.sick:target` | `plan.step_failures >= 2` | 3 |
| 13 | `health_crisis/borrow_for_care` | `health_crisis:*` | `household.credit_headroom > 0` | `request_borrow amount=care_need(target)` ; `seek_care target=target` | idem #12 | `household.credit_headroom <= 0` | 2 |
| 14 | `satisfy_food/protect_food` | `satisfy:food` | `true` | `consume need=food factor=1.0` ; `reduce_consumption need=rest factor=0.5` | `need.food >= aspiration.food` | `plan.step_failures >= 3` | 3 |
| 15 | `satisfy_food/minimal` | `satisfy:food` | `belief.debt_critical or belief.household_job_lost` | `consume need=food factor=0.7` (repeat until_success) | `need.food >= aspiration.food` | `plan.step_failures >= 3` | 3 |
| 16 | `find_job/search` | `find_job` | `self.seek_job and not belief.employed` | `seek_job` (repeat until_success) | `belief.employed` | `plan.months_active >= 12` | 12 |
| 17 | `find_job/informal_entry` | `find_job` | `self.work and econ.months_unemployed >= 6` | `enter_work` (accepte un emploi informel, probabilité de retour ×2) | `belief.employed` | `plan.step_failures >= 3` | 6 |
| 18 | `contribute/raise_pooling` | `cope_income_loss` (aussi sous-but de `repay_debt`) | `self.work and belief.employed and econ.pooling_rate < 1.0` | `contribute_more factor=1.0` — pooling porté à 1,0 pour la durée du plan | `not belief.household_job_lost and belief.debt_manageable` | `plan.months_active >= 6` | 6 |
| 19 | `leave_household/move_out` | `leave_household` | `belief.can_leave and belief.debt_manageable and not belief.household_job_lost` | `save amount=0.2*belief.expected_income` (repeat 6) ; `leave_household` | `not person.in_household` | `plan.step_failures >= 2` | 12 |
| 20 | `reduce_consumption/across_board` | `repay_debt` / `build_buffer` (priorité 9, dernier recours) | `self.consume` | `reduce_consumption need=rest factor=0.5` ; `reduce_consumption need=food factor=0.9` | `belief.debt_manageable` | `plan.step_failures >= 2` | 3 |
| 21 | `drop_school/teen_work` | `cope_income_loss` (priorité 8) | `self.work and econ.employment_student and belief.debt_critical` | `drop_school` ; `enter_work` | `belief.employed` | `plan.step_failures >= 2` | 3 |

Remarques :
- Le plan 21 n'est applicable qu'à une personne ayant à la fois `work` et le statut étudiant (jeune adulte étudiant, ou adolescent si un profil lui donne `work`). Avec les profils de 03 §3, l'adolescent ne l'a pas : le plan est inactif sans code spécifique (D1).
- Les montants symboliques (`gap_essential`, `arrears_amount`, `freed_amount`, `extra_income`, `care_need(target)`, `household.debt_service`) sont **calculés par `decision/plans.py → resolve_amount()`** à partir de la vue foyer ; liste fermée, définie §13.
- Variantes `drop_school/*` et `teen_work` sont des comportements possiblement dommageables : ils existent pour que P7 et l'indicateur « années d'éducation » puissent varier ; leur fréquence est rapportée (métrique `dropout_by_plan`).

### 7.4 Replanification et repli

```
on step failure:
  intention.failures += 1 ; memory.encode(plan_outcome = 0)
  if eval(plan.failure): 
      plan marqué échoué (épisode) ; next = premier autre plan applicable pour intention.goal (§6)
      if next: intention.plan_id = next.id ; step_index = 0 ; événement plan_switched
      else:    intention.status = FAILED ; événement intention_failed
on no applicable plan at adoption:
  événement no_applicable_plan(goal) ; la personne décide par satisficing pur ce pas (règle V1)
```

**Métrique de validité de la Fiche 2 :** `no_applicable_plan_rate = n(no_applicable_plan) / n(adoptions tentées)` par run. Seuil d'alerte : > 5 % ⇒ revoir la bibliothèque (critère de sortie §15). Aucune exception n'est levée pour l'absence de plan : c'est un repli identifiable, jamais une erreur silencieuse.

## 8. Intégration plan → alternatives → satisficing

Le satisficing reste l'unique mécanisme de choix (D3, S1). Le plan agit **uniquement** sur l'ordre de saillance et sur le contenu de l'alternative de tête :

1. `alternatives.generate(capabilities, needs, profile_eff, plan_step)` : si une étape de plan est courante, l'**alternative de plan** (panier habituel modifié par l'action de l'étape : facteur sur un besoin, montant d'épargne, offre de travail, demande d'emprunt, demande au nom d'une cible) est placée **en position 0** ; les autres suivent l'ordre V1 ; troncature à `max_alternatives_eff` (l'alternative de plan n'est jamais tronquée).
2. `SatisficingEngine.decide()` (10_SPEC_V1 §7 (moteur de décision)) évalue dans l'ordre. Si l'alternative de plan est acceptable ⇒ `rule = "plan_step"`. Sinon, l'étape échoue (§7.4) et le moteur poursuit sur les alternatives suivantes (`first_acceptable` / `fallback_top_need`).
3. Les actions non monétaires (`seek_job`, `increase_labor`, `enter_work`, `drop_school`, `leave_household`, `contribute_more`) sont portées par l'alternative (champ `labor_supply`, drapeaux) et exécutées en Temps 3 par `economy/actions.py` ; elles n'écrivent dans le `Ledger` que par leurs effets monétaires normaux (salaire, pooling).
4. Les demandes d'emprunt (`request_borrow`) sont des `Demand(tier=ESSENTIAL, action=REQUEST_BORROW)` : le foyer emprunte selon `allocate()` (10_SPEC_V1 §8 (allocation)) ; la personne ne peut jamais emprunter seule (pas de compte de prêt personnel).
5. Effets des actions V2 (paramètres dans `economic_params.actions`, nouvelle clé, §13) : `seek_job` multiplie `p_find_monthly` par `seek_job_multiplier` (défaut 2,0) ; `increase_labor` porte `labor_supply` à `factor` (≤ 1,25) et augmente `fatigue` de `fatigue_per_extra` × (labor_supply − 1) ; REST alors dégradé par la formule V1 (`sat_rest = clip(1 − 0.6·max(0, labor_supply − 0.8) − fatigue, 0, 1)`) ; `fatigue` décroît de `fatigue_recovery` par mois si `labor_supply ≤ 1`.

## 9. Adaptation de l'aspiration (`cognition/aspiration.py`) — boucle B2

Pour chaque k ∈ `attended_needs`, en Temps 3.4, avec `s_k` = satisfaction réalisée du pas :

```
si s_k ≥ θ_k :  θ_k ← θ_k + up   · (s_k − θ_k)          ; failure_streak[k] ← 0
sinon        :  θ_k ← θ_k − down · (θ_k − s_k)          ; failure_streak[k] += 1
θ_k ← clip(θ_k, min, max)                                (profile.aspiration_adapt)
```

`loops.b2.enabled: false` ⇒ θ_k = `aspiration_init` constant (comportement V1). `failure_streak` est collecté (diagnostic) mais n'entre pas dans la formule (forme retenue = celle des notes partagées ; toute variante non monotone serait une hypothèse nouvelle à documenter — Fiche 1, HYP).

## 10. Actualisation β-δ (`decision/discounting.py`) — optionnel, forte priorité

Pondération D(t) utilisée dans le score projeté du satisficing (10_SPEC_V1 §7 (moteur de décision), étape 3) :

| `discounting.mode` | D(0) | D(t ≥ 1) |
|---|---|---|
| `none` (ou bloc désactivé) | 1 | 1 |
| `exponential` | 1 | δ^t |
| `naive`, `sophisticated` | 1 | β·δ^t |

`cognition.discounting.enabled: false` ⇒ D(t) = 1 pour tous (V1).

**Naïf vs sophistiqué** — la différence porte sur l'**évaluation des plans** à l'adoption, pas sur le choix courant :

```python
def plan_value(plan, person, horizon, mode, beta, delta):
    # projection des niveaux de besoins si le plan est suivi jusqu'au bout
    traj = simulate_plan_projection(plan, person, horizon)          # déterministe, sans Ledger
    if mode == "naive":
        # l'agent croit que ses futurs « moi » suivront δ (aucun biais futur)
        w = [1.0] + [delta**t for t in range(1, horizon+1)]          # adoption évaluée en exponentiel
    elif mode == "sophisticated":
        # l'agent anticipe que chaque futur « moi » appliquera β au moment d'agir
        w = [1.0] + [beta * delta**t for t in range(1, horizon+1)]
        traj = apply_anticipated_deviation(traj, plan, beta)         # étapes coûteuses à court terme supposées abandonnées
    return weighted_need_score(traj, w)

def choose_plan(goal, candidates, ...):   # remplace « premier applicable » quand discounting.enabled
    return max(applicable(candidates), key=plan_value, default=None)  # égalité ⇒ priority croissante
```

- **Exécution** (tous modes β-δ) : chaque pas, le choix courant passe par le satisficing avec D(t) = β·δ^t. Pour un agent naïf, l'alternative de plan d'une étape coûteuse à court terme (épargne, remboursement) peut devenir inacceptable ⇒ échec d'étape ⇒ abandon caractéristique du présent-biais (procrastination).
- **Sophistiqué** : `apply_anticipated_deviation` marque comme « probablement abandonnée » toute étape dont l'alternative serait inacceptable sous β ; un plan d'épargne simple vaut alors moins qu'un plan **à engagement**. Plan à engagement disponible en V2 : `build_buffer/regular_saving` avec `commitment: true` (l'étape `save` est exécutée en COMMITMENT par le foyer, pas réévaluée chaque mois) — **Détails tranchés n°6**. `JOIN_TONTINE` reste V3 (CPT).
- `simulate_plan_projection` réutilise la projection du satisficing (persistance ρ_k, ê_k) ; elle n'appelle ni le foyer ni le Ledger.

**Paramètres :** `profiles.*.discounting.{mode, beta, delta}` ; β est une variable de traitement de E3 (jamais calibré, registre 03 §12).

## 11. Poids de négociation variables et NTTA (optionnels)

**Poids variables** — dans `allocate()` (une seule fonction, S1) : `w_i = normalise(w0_i · (1 + γ · Yl_i / ΣYl))`, calculés en début de Temps 2 sur le Yl du pas ; ΣYl = 0 ⇒ w = w0. `HouseholdState.weights` est mis à jour et collecté. Aucune autre différence avec `fixed_weights`.

**NTTA** (`nta/ntta.py`, `nta.ntta.enabled`, défaut `false`) — comptes de temps séparés, **jamais** additionnés aux NTA monétaires :
- Temps domestique produit par personne : `h_dom_i = domestic_hours_by_role` (config `nta.ntta.domestic_hours`, heures/mois, par clé de membre — donnée, pas code) × (1 − labor_supply_i)⁺ ;
- Valorisation au salaire fictif `nta.ntta.shadow_wage_per_hour` (FCFA) ;
- Consommation de temps domestique attribuée aux bénéficiaires par l'échelle OCDE modifiée ;
- Sorties : table `ntta_person_steps` (`run_id, step, household_id, person_id, age_years, time_produced_h, time_consumed_h, value_produced, value_consumed, time_transfer_net`) ; invariant : Σ produit = Σ consommé par foyer et par pas.

## 12. Départ du jeune adulte (D13)

Si `household_rules.young_adult_can_leave: true` et que le plan `leave_household/move_out` exécute l'étape `leave_household` :
1. En fin de pas (Temps 3.7, après NTA et collecte), le foyer crée un **nouvel `HouseholdAgent` d'une personne** (`HouseholdId` suivant ; aucun nouveau type d'agent) : la personne y est propriétaire unique (ω = 1) et tête pour l'imputation.
2. Transfert de son portefeuille : aucune écriture (le compte `PERSON_WALLET` le suit). Pot initial du nouveau foyer = 0. Le coût de logement d'une personne seule = `leave_rule.housing_cost_single` (nouvelle clé, placeholder 45 000 FCFA).
3. Chaque mois suivant : `INTER_HOUSEHOLD_TRANSFER` (POT du nouveau foyer → OTHER_HOUSEHOLDS) et symétriquement (OTHER_HOUSEHOLDS → POT du foyer d'origine) pour `remittance_share × Yl`. Les deux écritures sont postées au même pas ; les comptes externes s'annulent (test).
4. `person_steps.in_household` = `false` côté foyer d'origine (la personne est désormais rattachée au nouveau `household_id`) ; événement `left_household`.
5. Le foyer d'origine recalcule poids (normalisation) et propriété (inchangée si le jeune adulte n'était pas propriétaire).

Les sous-flux aléatoires du nouveau foyer dérivent de `(seed, household_index_d'origine, "split", person_index)` afin de ne pas perturber ceux des autres foyers.

## 13. Configuration — ajouts V2

Ajouts **compatibles** avec 03 (nouvelles clés seulement, valeurs neutres = comportement V1) :

```yaml
# simulation.yaml
cognition:
  memory: { enabled: true, noise_s: 0.0 }
nta:
  ntta: { enabled: false }

# economic_params.yaml
actions:
  seek_job_multiplier: 2.0
  max_labor_supply: 1.25
  fatigue_per_extra: 0.5
  fatigue_recovery: 0.2
  enter_work_find_multiplier: 2.0

# household_rules.yaml
leave_rule:
  housing_cost_single: 45000       # PLACEHOLDER

# plans.yaml
max_subgoal_depth: 2
desires:
  long_term:
    cope_income_loss: { priority: 0.9 }
    health_crisis:    { priority: 0.85 }
    repay_debt:       { priority: 0.5, priority_if_critical: 0.8 }
    find_job:         { priority: 0.7 }
    educate:          { priority: 0.6 }
    build_buffer:     { priority: 0.4 }
    leave_household:  { priority: 0.3 }
amounts:                            # liste fermée des montants symboliques (resolve_amount)
  gap_essential: "Σ demandes ESSENTIAL du foyer − budget du pas (≥ 0)"
  arrears_amount: "échéances impayées cumulées"
  freed_amount: "économie produite par l'étape reduce_consumption précédente"
  extra_income: "Yl(labor_supply) − Yl(1.0)"
  care_need: "PhysicalState.care_need de la cible"
  debt_service: "échéance minimale du mois"
```

## 14. Sorties — extensions (compatibles avec 04)

Aucune colonne de 04 n'est modifiée. Colonnes V2 déjà prévues et désormais renseignées : `intention_goal`, `plan_id`, `n_beliefs_active`, `memory_size`, `beta_eff`, `fatigue`, `in_household`, `aspiration_{k}` (variables). Événements V2 déjà listés en 04 §2.7 (`intention_adopted`, `intention_failed`, `plan_switched`, `no_applicable_plan`, `left_household`).

Ajouts :
- `person_steps` : `intention_status` (cat), `plan_step_index` (i32), `failure_streak_{k}` (i32 ×6).
- `household_steps` : `weight_{person_key}` n'est **pas** ajouté en large ; nouvelle table longue `household_weights` (`run_id, step, household_id, person_id, weight, ownership`).
- `beliefs_steps` (optionnelle, `output.collect.beliefs: sample`) : `run_id, step, person_id, key, value (f64), confidence`.
- `ntta_person_steps` (§11) si NTTA activé.
- `metrics` : `no_applicable_plan_rate`, `intention_persistence_mean` (durée moyenne des intentions, mois), `plan_success_rate`, `dropout_by_plan`.

## 15. Tests (V-1 et V-3)

### 15.1 Non-régression V1 — **obligatoire, bloquant**

`tests/integration/test_v2_reduces_to_v1.py` : pour 20 seeds, avec `model.version: v2`, `cognition.bdi.enabled: false`, `cognition.memory.enabled: false`, `loops.b2.enabled: false`, `cognition.discounting.enabled: false`, allocation `fixed_weights`, D13 `false` : **les tables `ledger`, `household_steps`, `person_steps` (colonnes V1) et `nta_person_steps` sont identiques bit à bit** à celles d'un run `model.version: v1`. Conséquence de conception : aucune consommation de nombre aléatoire supplémentaire quand les blocs V2 sont désactivés (S4 : flux nommés), aucun changement d'ordre d'itération.

Toute la suite V1 (invariants sur 100 seeds × 240 pas, reproductibilité, conservation) est rejouée en V2 **tous blocs actifs**.

### 15.2 Unitaires

| Module | Tests |
|---|---|
| `memory` | activation conforme à la formule (valeurs de référence calculées à la main) ; décroissance monotone en t ; éviction de l'activation minimale avec départage déterministe ; `capacity=0` ⇒ no-op ; `weighted_mean` = valeur unique si un seul épisode ; renforcement augmente l'activation ; bruit nul ⇒ déterminisme |
| `beliefs` | chaque ligne de la table §4 : cas vrai / faux / défaut sans mémoire |
| `desires` | priorité need_deficit conforme ; aucun désir long terme sans la capacité requise ; tri stable |
| `ConditionParser` | grammaire : précédence `not > and > or` ; parenthèses ; référence inconnue ⇒ `ConfigError` au chargement ; tentative d'injection (`__import__`, `os.system`, attributs) ⇒ `ConfigError` ; fuzz `hypothesis` : le parser ne lève que `ConfigError` |
| `plans` | chargement de la bibliothèque complète sans erreur ; chaque plan a ≥ 1 situation de test où il est applicable (fixture par plan) ; replanification après `failure` ; `no_applicable_plan` émis, pas d'exception ; profondeur de sous-buts ≤ 2 |
| `deliberate` | `commitment=0` ⇒ suit toujours le désir max ; `commitment=1` ⇒ persiste tant que priorité concurrente ≤ 2× ; suspension/reprise |
| `aspiration` | succès ⇒ θ non décroissant ; échec ⇒ θ non croissant ; bornes respectées ; `b2` désactivé ⇒ θ constant |
| `discounting` | D(0)=1 ; β=1 ⇒ exponentiel ; naïf adopte un plan d'épargne simple et l'abandonne plus souvent qu'un sophistiqué (scénario jouet déterministe) |
| `allocation` | `variable_weights` avec γ=0 ⇒ identique à `fixed_weights` ; poids somme 1 |
| D13 | départ ⇒ nouveau foyer, conservation globale, transferts inter-ménages appariés, identités NTA par foyer |

### 15.3 Propriétés (`hypothesis`)

- Pour tout profil généré dans les bornes du registre : aucune `InvariantViolation` sur 60 pas.
- `max_alternatives=1, planning_horizon=0`, sans `plan`/`remember` ⇒ `rule ∈ {"reactive"}` à chaque pas (le bébé reste réactif en V2).
- Monotonie : à seed égal, augmenter `aspiration_init` ne diminue jamais le nombre d'alternatives évaluées par décision.

### 15.4 Comportementaux (V-3, Phase 6)

- **Hétérogénéité expliquée (critère de réussite Phase 5)** : `tests/integration/test_profiles_differ.py` — deux personnes de profils différents placées dans une situation identique (fixture) prennent des décisions différentes, et la différence est attribuable via `DecisionTrace` (troncature `max_alternatives`, horizon, ou plan).
- Choc `job_loss` : l'intention `cope_income_loss` est adoptée par au moins un parent dans les 2 pas ; signe des réponses (consommation de repos ↓, offre de travail de l'autre parent ↑ ou désépargne).
- Performance : 1 foyer × 240 pas < 15 s (`tests/performance/`).

## 16. Expériences V2

Définitions YAML et runner : **voir 50_SPEC_EXPERIMENTS.md**. Rappel du contenu scientifique (feuille de route §12) :

| Exp. | Manipulé | Contrôlé | Métriques (04 §3) |
|---|---|---|---|
| **E2** Réactif vs délibératif | `model.version ∈ {v1, v2}` | tous paramètres économiques, mêmes 100 seeds | `consumption_volatility`, `savings_rate_12m` moyen, `debt_to_income_terminal` |
| **E3** Présent-biais (si β-δ activé) | `profiles.{adolescent,young_adult,mother,father}.discounting.beta ∈ {1.0, 0.9, 0.7, 0.5}` | δ, revenus, prix | `debt_to_income_terminal`, `education_years_*` |
| **E6** Foyer unitaire / non unitaire | `household_rules.allocation.mode ∈ {unitary, fixed_weights, variable_weights}` ; scénario à contrainte forte (`job_loss`) | profils, seeds | part de consommation par membre, `education_years_*`, écart au repère d'efficacité (repère calculé en V3 — en V2 : tableau des parts uniquement) |
| **E-SA** Sensibilité globale | registre `sa: true` | — | Morris puis Sobol sur 8–10 survivants ; métriques de sortie : `debt_to_income_terminal`, `savings_rate_12m`, `lcd_household`, `consumption_volatility` |

Rappel de discipline : E2 rapporte la différence **ou l'absence de différence** ; la dépendance de l'écart à la bibliothèque de plans est une limite à discuter (Chap. 6, 9).

## 17. Critères de sortie V2 (porte V2 — `docs/GATES.md`)

- [ ] Tous les critères V1 restent verts, **tous blocs V2 activés** (100 seeds × 240 pas, zéro violation d'invariant).
- [ ] `test_v2_reduces_to_v1` vert (identité bit à bit, blocs désactivés).
- [ ] E2 exécutée et rapportée (différence mesurable et expliquée, ou absence rapportée).
- [ ] E-SA : hiérarchie des paramètres influents établie (indices Morris + Sobol, figure obligatoire Chap. 6).
- [ ] ≥ 2 patterns POM reproduits avec un seul jeu de paramètres (voir 40_SPEC).
- [ ] `no_applicable_plan_rate` ≤ 5 % sur le scénario de référence et sur `job_loss` (sinon bibliothèque revue — Fiche 2).
- [ ] `ODD_v2_cognitive.md` à jour et cohérent avec le code (chaque sous-modèle V2 y est décrit avant d'être codé).
- [ ] 1 foyer × 240 pas < 15 s.

## 18. Risques V2

| Risque | Signe précurseur | Parade |
|---|---|---|
| La V2 casse la conservation V1 | invariants rouges seulement en V2 | règle §2 : la cognition n'écrit jamais au Ledger ; tout passe par les demandes |
| Non-régression impossible (flux aléatoires décalés) | `test_v2_reduces_to_v1` rouge sans changement de logique | sous-flux nommés ; aucun tirage quand un bloc est désactivé |
| Bibliothèque de plans qui « fabrique » le résultat de E2 | l'écart E2 disparaît dès qu'on retire 2 plans | ablation : E2 rejouée sans les plans 5–9 (rapportée en limite) |
| Explosion du nombre de paramètres | priorités de désirs, montants de plans, coefficients de fatigue non contrôlés | tous dans le registre (03 §12) ; Morris les crible |
| Parser DSL dangereux | usage de `eval` | interdit ; tests d'injection |
| Dérive « BDI complet » | ajout d'événements, de messages entre agents | hors périmètre : BDI dégradé (une intention, plans pré-écrits, pas de communication) |

## 19. Détails tranchés dans ce document

1. **Encodage mémoire conditionné à `remember`** : la capacité `remember` gouverne l'**existence** de l'encodage, `memory.capacity` sa taille. Un profil avec `capacity > 0` sans `remember` n'encoderait rien (cas absent des profils de 03 §3 : l'enfant a `remember` et une capacité de 10).
2. **Pondération des rappels par softmax des activations** (`weighted_mean`) — les notes disent « moyenne pondérée par activation » ; les activations étant des logarithmes (éventuellement négatifs), le poids retenu est `exp(A_i)` normalisé.
3. **Une seule intention suspendue** au plus, abandonnée après `max_duration_months`.
4. **Profondeur de sous-buts ≤ 2** (`plans.max_subgoal_depth`).
5. **Plan choisi par valeur β-δ** (et non « premier applicable ») uniquement quand `cognition.discounting.enabled` ; sinon ordre `priority`.
6. **Plan à engagement** : `commitment: true` sur une étape `save` ⇒ l'épargne devient une demande `Tier.COMMITMENT` pour la durée du plan (non réévaluée chaque mois) ; seul mécanisme d'engagement en V2.
7. **Actions V2 et leurs coefficients** (`economic_params.actions`), **montants symboliques** (liste fermée), `leave_rule.housing_cost_single`, `cognition.memory.noise_s`, `nta.ntta.*` : nouvelles clés, valeurs `PLACEHOLDER`.
8. **Tables nouvelles** `household_weights`, `beliefs_steps`, `ntta_person_steps` et colonnes `intention_status`, `plan_step_index`, `failure_streak_{k}` : ajouts à 04, sans modification de l'existant.
9. **Tirage des sous-flux du foyer issu d'un départ** : `(seed, household_index_d'origine, "split", person_index)`.
