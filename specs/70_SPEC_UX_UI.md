# 70 — Spécification UX/UI (frontend React, `web/`)

> **Statut :** normatif pour la piste B (après la porte V1). Dépend de `04_DATA_MODEL.md` (colonnes) et `60_SPEC_API.md` (routes). Le frontend **ne calcule aucun indicateur** : il sélectionne, met en forme et trace des valeurs servies par l'API (S7). Toute moyenne, dispersion, variation ou écart affiché provient d'un champ de réponse.

---

## 1. Principes

| Principe | Règle d'implémentation |
|---|---|
| Plateforme scientifique, pas grand public | Densité élevée (taille de base 13 px), hiérarchie sobre, aucune illustration décorative. |
| La couleur porte du sens | Une couleur par membre du foyer, **constante** dans toute l'application (token `--member-*`). Rouge (`--signal-deficit`) réservé au déficit (LCD > 0) et aux alertes. Jamais de couleur décorative. |
| Une seule famille de graphiques | Lignes = séries temporelles ; barres = comparaisons ; aires empilées = décompositions. **Pas de camembert, pas de jauge circulaire.** |
| Échelles fixes en comparaison | Petits multiples partageant `x` et `y` (domaine fourni par l'API, `shared_domain`). |
| Toujours afficher l'incertitude | Toute valeur issue de plusieurs réplications : bande q05–q95 sur les séries, `± sd` et `n` sur les tuiles. |
| Aucune animation gratuite | Transitions désactivées sur les graphiques ; seules exceptions : indicateur de progression d'un job et dépliage d'une ligne (≤ 120 ms). `prefers-reduced-motion` respecté. |
| Thème clair par défaut | Fond blanc ; thème sombre optionnel (tokens redéfinis) ; **l'export de figure est toujours en thème clair**. |
| Figures du mémoire | Chaque `ChartCard` exporte SVG et PNG (2×) avec titre, unité, légende, source (`run_id`, `config_hash`, mention « illustratif » si applicable). |
| Honnêteté | Un run `illustrative: true` porte un bandeau permanent ; calibration et validation sont distinguées par **forme et libellé**, pas seulement par la couleur. |

## 2. Design tokens

### 2.1 Couleurs (CSS variables, `web/src/styles/tokens.css`)

Palette des membres dérivée d'Okabe-Ito (sûre pour deutéranopie/protanopie), **sans rouge** ; à vérifier avec un simulateur de daltonisme (tâche d'acceptation §11).

```css
:root {
  /* Membres — constants partout (graphes, légendes, nœuds, pistes) */
  --member-father:      #0072B2;  /* bleu */
  --member-mother:      #CC79A7;  /* rose-violet */
  --member-young-adult: #009E73;  /* vert bleuté */
  --member-adolescent:  #E69F00;  /* orange */
  --member-child:       #56B4E9;  /* bleu ciel */
  --member-baby:        #8C6D1F;  /* ocre brun */
  --member-household:   #4D4D4D;  /* nœud foyer, agrégats */

  /* Signaux — sémantiques, jamais décoratifs */
  --signal-deficit:     #C62828;  /* LCD > 0, demande refusée, alerte, InvariantViolation */
  --signal-deficit-bg:  #FDECEA;
  --signal-surplus:     #5B6770;  /* LCD < 0 (surplus) — neutre ardoise */
  --signal-warning:     #8A5A00;  /* run illustratif, données de repli */
  --signal-warning-bg:  #FFF4E0;
  --signal-ok:          #2E7D32;  /* critère vert (accompagné d'une icône ✓) */
  --status-partial:     #9E9E9E;  /* demande partielle (hachuré) */

  /* Rôles de pattern (doublés par forme : plein vs creux) */
  --pattern-calibration: #263238;  /* marqueur plein ● */
  --pattern-validation:  #263238;  /* marqueur creux ○ + hachure + badge « VALIDATION » */
  --pattern-observed:    #000000;  /* courbe observée : trait discontinu 4-3 */

  /* Neutres */
  --bg:        #FFFFFF;  --bg-subtle: #F6F7F8;  --bg-muted: #ECEEF0;
  --border:    #D5D9DD;  --grid-line: #E6E8EA;
  --text:      #1A1D21;  --text-muted: #5A6169;  --text-faint: #8A9199;
  --focus:     #1F6FEB;
  --uncertainty-alpha: 0.18;   /* opacité des bandes q05–q95 */
}
:root[data-theme="dark"] { --bg: #121417; --bg-subtle: #1A1D21; --bg-muted: #23272C;
  --border: #353A40; --grid-line: #2A2E33; --text: #E8EAED; --text-muted: #A9B0B7; --text-faint: #7D858C; }
```

Correspondance rôle → token (`web/src/theme/members.ts`) : `father|mother|young_adult|adolescent|child|baby` (valeurs de `Role`, 02 §2). La couleur suit le **rôle** (identité stable), pas le profil (qui change avec l'âge).

### 2.2 Typographie

| Token | Valeur |
|---|---|
| `--font-sans` | `"Inter", system-ui, sans-serif` ; `font-feature-settings: "tnum" 1, "cv11" 1` sur tout nombre (classe `.num`) |
| `--font-mono` | `"IBM Plex Mono", ui-monospace` — identifiants (`run_id`, `person_id`), hashes |
| Tailles | `--fs-xs 11px` · `--fs-sm 12px` · `--fs-base 13px` · `--fs-md 14px` · `--fs-lg 16px` · `--fs-xl 20px` · `--fs-kpi 22px` |
| Graisses | 400 texte, 500 libellés, 600 titres et valeurs KPI |
| Interligne | 1.35 (tableaux 1.25) |

Nombres : alignés à droite, séparateur de milliers espace fine (`Intl.NumberFormat('fr-FR')`), unités en `--text-muted` après la valeur (« 125 000 FCFA »), ratios en % avec 1 décimale.

### 2.3 Espacements, grille, élévation

- Base 4 px : `--space-1 4px` … `--space-8 32px`. Rayon `--radius 4px` (pas d'arrondis marqués). Aucune ombre ; séparation par bordures `1px var(--border)`.
- Layout : barre latérale fixe 208 px (repliable à 56 px) + zone de contenu en grille 12 colonnes, gouttière 16 px, largeur max 1680 px. Points de rupture : `lg 1280` (cible principale), `md 1024` (2 colonnes → 1), `< 1024` lecture seule dégradée (pas d'objectif mobile).

### 2.4 Configuration Tailwind (`web/tailwind.config.ts`)

```ts
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        member: { father: "var(--member-father)", mother: "var(--member-mother)",
          "young-adult": "var(--member-young-adult)", adolescent: "var(--member-adolescent)",
          child: "var(--member-child)", baby: "var(--member-baby)", household: "var(--member-household)" },
        signal: { deficit: "var(--signal-deficit)", "deficit-bg": "var(--signal-deficit-bg)",
          surplus: "var(--signal-surplus)", warning: "var(--signal-warning)",
          "warning-bg": "var(--signal-warning-bg)", ok: "var(--signal-ok)" },
        bg: { DEFAULT: "var(--bg)", subtle: "var(--bg-subtle)", muted: "var(--bg-muted)" },
        border: "var(--border)", text: { DEFAULT: "var(--text)", muted: "var(--text-muted)", faint: "var(--text-faint)" },
      },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"], mono: ["IBM Plex Mono", "ui-monospace"] },
      fontSize: { xs: "11px", sm: "12px", base: "13px", md: "14px", lg: "16px", xl: "20px", kpi: "22px" },
      borderRadius: { DEFAULT: "4px" },
    },
  },
  plugins: [],
} satisfies import("tailwindcss").Config;
```

Les polices sont **auto-hébergées** dans `web/public/fonts/` (exécution hors ligne).

## 3. Pile technique et état

| Besoin | Choix |
|---|---|
| Build | Vite + React 18 + TypeScript strict |
| Données serveur | TanStack Query v5 ; clés `[route, params]` ; `staleTime: Infinity` pour un job `completed` (immuable) ; polling 2 s du statut tant que `queued|running` |
| État global client | Zustand : `useCursorStore` (`step`, `setStep`, `playing=false` — pas de lecture animée par défaut), `useSelectionStore` (`simulationId`, `runId`, `householdId`, `personId`, `comparisonIds[]`, `baselineId`) |
| État dans l'URL | Source de vérité pour tout ce qui est partageable : `?sim=…&run=…&hh=…&p=…&step=…&cmp=a,b,c&base=a`. Synchronisation URL ↔ Zustand par un hook unique `useUrlState` (l'URL gagne au chargement) |
| Graphiques | Observable Plot (séries, barres, aires, petits multiples, histogrammes) ; D3 (`d3-shape`, `d3-scale`) pour `HouseholdGraph`, `LeeArrows`, `SimulationTimeline` |
| Types API | `web/src/api/schema.d.ts` généré par `openapi-typescript` (60 §8) ; client `openapi-fetch` |
| Routage | React Router v6 |
| i18n | `i18next`, FR par défaut (`fr.json`), clés en anglais ; EN optionnel. Libellés d'indicateurs : `label_fr` de l'API (source unique) |

## 4. Architecture de navigation et routes

```
┌─ DASHBOARD ────────── /                                vue population : où en est la simulation ?
├─ SCÉNARIOS ────────── /scenarios                       configurer, lancer, suivre la file
├─ FOYERS ───────────── /households                      liste
│                       /households/:hid                 vue foyer
│                       /households/:hid/agents/:pid     vue agent
├─ ANALYTIQUE NTA ───── /nta                             profils par âge, transferts, cycle de vie
├─ COMPARAISON ──────── /compare                         scénario A vs B vs C
└─ VALIDATION ───────── /validation                      observé vs simulé, patterns, sensibilité
```

La **frise de simulation** (écran D) n'est pas une section : c'est un panneau ancré en bas des écrans Dashboard, Foyer, Agent et NTA (repliable), dont le curseur pilote `step` pour toutes les vues ouvertes.

Chrome commun :

```
┌──────────┬──────────────────────────────────────────────────────────────────────────────┐
│ family   │ Simulation [sim_01JB…  job_loss · v2 · 20 réplications ▾]  Run [seed 1000 ▾] │
│ ABM      │ ⚠ RUN ILLUSTRATIF — paramètres PLACEHOLDER (données synthétiques)   [détails]│
│──────────│──────────────────────────────────────────────────────────────────────────────│
│ Dashboard│                                                                              │
│ Scénarios│                     contenu de l'écran                                       │
│ Foyers   │                                                                              │
│ NTA      │                                                                              │
│ Compar.  │──────────────────────────────────────────────────────────────────────────────│
│ Validat. │ FRISE ▸ chocs | décisions | transferts | états      ◀ pas 47 / 240 (an 3 m 11) ▶│
│──────────│                                                                              │
│ v0.3.0   │ config 3f9a…c21 · engine 0.3.0 · data: synthetic                             │
└──────────┴──────────────────────────────────────────────────────────────────────────────┘
```

## 5. États transverses (tous les écrans)

| État | Déclencheur | Rendu |
|---|---|---|
| Chargement | requête en cours | squelettes aux dimensions finales (pas de spinner central) ; pas de saut de mise en page |
| Vide | aucune simulation | message + bouton « Lancer une simulation » → `/scenarios` |
| Erreur réseau / 5xx | `Problem` | encart `--signal-deficit-bg` avec `title`, `detail`, bouton Réessayer ; le reste de l'écran reste utilisable |
| Run en cours | `status ∈ {queued, running}` | barre de progression (`progress`, `runs_total`), écrans de résultats désactivés avec mention « Résultats disponibles à la fin du job » (409 attendu) |
| Run échoué — InvariantViolation | `error.type` = `…/invariant-violation` | encart rouge **bloquant** : « Violation d'invariant comptable au pas {extra.step}, compte {extra.account}, résidu {extra.residual} FCFA. Les résultats de ce run ne doivent pas être interprétés. » + lien vers le foyer et le pas concernés (vue foyer, Ledger) ; les runs déjà complétés d'autres seeds restent consultables mais marqués |
| Autre échec | `failed` | encart rouge avec `Problem` complet (copiable) |
| Run illustratif | `illustrative: true` | bandeau `--signal-warning` permanent dans le chrome + mention dans chaque export de figure |
| Décisions non collectées | `decisions_available: false` | encart neutre dans la vue agent : « Traces non collectées pour ce foyer (échantillonnage `output.collect.decisions`) » |
| Fonction de version supérieure | colonne neutre (ex. `stress` en V1/V2) | panneau masqué avec mention « Disponible en V3 » — jamais une courbe plate trompeuse |

## 6. Écrans

### A. Dashboard global — `/`

**Objectif utilisateur :** savoir en 10 secondes où en est la population simulée et ce qui s'y passe.

```
┌ Indicateurs (pas 47 · moyenne sur 20 réplications) ─────────────────────────────────────┐
│ Foyers     Pas      Dette agrégée    Taux d'épargne  LCD agrégé     Gini     Pauvreté   Stress │
│ 1 000      47/240   412 M FCFA       6,8 %           −18 M FCFA     0,41     27,3 %     0,32   │
│            ▁▂▃▅     ▁▂▃▅▆ +4,1 %     ▆▅▄▄ −0,6 pt    ▂▂▃▃ +2 %      ▃▃▃▄     ▂▃▄▄ +1,2pt ▁▂▃▄ │
│            ±—       ±12 M (n=20)     ±0,9 pt         ±3 M           ±0,01    ±1,1 pt   ±0,02  │
├ Profil NTA par âge (figure signature) ──────────────────┬ Distribution dette/revenu ─────┤
│  FCFA/an  ── consommation  ── revenu du travail          │  ▇                             │
│           ▓▓ LCD (rouge si > 0, ardoise si < 0)          │  ▇▇▅                           │
│      ╭──────╮                                            │  ▇▇▇▅▃▂▁   │ médiane 0,62      │
│  ───╯        ╲____ ……… observé (si disponible)           │  ▇▇▇▇▇▅▃▂▁▁                    │
│  0    10   20   30   40   50   60   70  âge              │  0   0,5   1   1,5   2  ratio  │
│  [SVG] [PNG]                                             │  [SVG] [PNG]                   │
├ Journal d'événements (filtrable : chocs · ruptures de coordination · sorties de scolarité)┤
│ pas 47  h0312  job_loss          père              origin: endogenous                    │
│ pas 46  h0088  regime_change     normal→separate_spheres                                 │
│ pas 46  h0731  school_dropout    adolescent                                              │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

| Élément | Composant | Données |
|---|---|---|
| Bandeau KPI (8 tuiles) | `KpiTile` ×8 | `GET /simulations/{id}/indicators?scope=population&step={cursor}&metrics=…` — `n_households` (statut), `step`, `debt_to_income` *(tuile « Dette agrégée » : valeur fournie par analysis)*, `savings_rate_12m`, `lcd_household`, `gini_income`, `poverty_rate`, `stress_mean` ; champs `value`, `sparkline`, `delta` |
| Profil NTA par âge | `ChartCard` + Plot | `GET …/results?table=nta_age_profile&columns=age,c,yl,lcd,person_years` ; courbe observée = cible de P1 via `GET /validation` (`target`) si présente |
| Distribution dette/revenu | `ChartCard` + histogramme | `GET …/results?table=household_steps&columns=household_id,debt_to_income&step_from={s}&step_to={s}` ; médiane = `IndicatorValue` dédiée fournie par l'API (pas de calcul client : la médiane affichée vient de `summarize`) |
| Journal | `EventLog` | `GET …/results?table=events&columns=step,household_id,person_id,type,origin,payload` paginé |

En foyer unique (`n_households = 1`), les tuiles Gini et Pauvreté sont remplacées par `rav_per_eq` et `cohesion_index` ; l'histogramme par la série `debt_to_income` du foyer.

**Interactions :** clic sur une tuile → série complète en panneau latéral ; clic sur un événement → `/households/:hid?step=…` ; curseur de la frise → toutes les valeurs « au pas ».

**Acceptation :** (1) chaque tuile affiche valeur + sparkline + variation + dispersion `± sd (n)` quand R > 1 ; (2) aucune jauge ni camembert ; (3) le profil NTA est le plus grand graphique de l'écran ; (4) changer le curseur met à jour tuiles et histogramme sans recharger l'écran.

### B. Scénarios — `/scenarios`

**Objectif :** choisir un scénario ou une expérience, lancer, suivre la file.

```
┌ Scénarios (config/scenarios — lecture seule) ──────┬ Lancer ───────────────────────────┐
│ ● baseline          Référence                       │ Scénario   [job_loss       ▾]     │
│ ○ job_loss          Perte d'emploi du père (m36)    │ Version    (v1) (●v2) (v3)        │
│ ○ illness           Maladie grave enfant (m48)      │ Horizon    (120) (●240) [____]    │
│ ○ family_allowance  Allocation familiale (m24)      │ Foyers     [1    ]                │
│ ○ free_care         Gratuité des soins (m24)        │ Réplications [20 ] seed départ [1000]│
│ ○ economic_shock    Choc économique (m60)           │ Libellé    [_______________]      │
│ Événements : step 36 · job_loss · father            │ [ Lancer ]  → 202, ajout à la file│
├ Expériences (config/experiments) ───────────────────┴───────────────────────────────────┤
│ E2 Réactif vs délibératif · facteurs model.version ∈ {v1,v2} · 100 rép.   [Lancer]      │
├ File et historique ─────────────────────────────────────────────────────────────────────┤
│ sim_01JB…  job_loss v2 ×20   ▓▓▓▓▓▓░░░░ 12/20  running            [Annuler]             │
│ sim_01JA…  baseline v2 ×20   completed  14 min  ⚠ illustratif     [Ouvrir] [Comparer +] │
│ sim_019Z…  illness  v1 ×1    failed — InvariantViolation pas 47   [Détail]              │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Données : `GET /scenarios`, `GET /simulations` (E-1), `POST /simulations`, `POST /simulations/{id}/cancel` (E-2), `GET /simulations/{id}` (polling). Le formulaire n'expose **que** les champs de `SimulationCreate` (aucun éditeur de paramètres).

**Acceptation :** lancement → ligne en file < 1 s ; annulation confirmée par une boîte de dialogue intégrée (pas `window.confirm`) ; un 422 affiche l'erreur au champ concerné.

### C1. Foyers — liste — `/households`

Tableau virtualisé : `household_id`, `n_members`, `debt_to_income`, `rav_per_eq`, `arrears_months`, `regime`, `essential_unmet`, `savings_rate_12m` au pas courant. Source : `GET …/results?table=household_steps&step_from={s}&step_to={s}&columns=…` (tri serveur par `ORDER BY` de la colonne demandée — tri, pas calcul). Valeurs `debt_to_income > 1` et `arrears_months ≥ 3` en `--signal-deficit`. Clic → vue foyer.

### C2. Vue foyer — `/households/:hid`

**Objectif :** voir l'arbitrage : qui a demandé quoi, qui a reçu quoi, qui finance qui.

```
┌ Foyer h0312 · pas 47 (an 3, mois 11) · régime NORMAL ──────────────────────────────────┐
├ Schéma des transferts (année 4) ─────────────────┬ Finances ───────────────────────────┤
│              (Jeune adulte)                       │ Budget commun (pot)   38 200 FCFA   │
│                    ║ ▲                            │ Épargne              112 000 FCFA   │
│   (Père) ════════▶ [FOYER] ◀═════ (Mère)          │ Dette                265 000 FCFA ▲ │
│                  ╱  │   ╲                         │ Plafond de crédit    540 000 FCFA   │
│          (Bébé)◀╱   ▼    ╲▶(Enfant)               │ Arriérés             0 mois         │
│                (Adolescent)                       │ Reste-à-vivre / éq.  41 300 FCFA    │
│ épaisseur = volume annuel · flèche = sens         │ Dette/revenu         0,74           │
├ Demandes du mois ─────────────────────────────────┴─────────────────────────────────────┤
│ Membre       Besoin     Palier      Demandé   Accordé   Statut    Raison                │
│ ■ Bébé       food       essential    15 000    15 000   accordé                         │
│ ■ Enfant     education  education     8 000         0   refusé    budget_exhausted      │
│ ■ Adolescent rest       other         4 000     2 100   partiel   budget_exhausted      │
│ ▐████████████████████▌▐██████▒▒▒▒▌▐░░░░░░░░▌  demandé ▒ accordé █ refusé ░ (par palier)  │
├ Frise d'événements du foyer ────────────────────────────────────────────────────────────┤
│ m36 job_loss père · m38 arrears_start · m41 intention_adopted cope_income_loss (père)    │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

| Élément | Composant | Données |
|---|---|---|
| Schéma | `HouseholdGraph` | `GET /simulations/{id}/households/{hid}?step=` → `members`, `transfers_year` (table `nta_transfer_matrix`) |
| Finances | `StatList` | `last_state` = ligne `household_steps` : `pot`, `savings`, `debt`, `credit_limit`, `arrears_months`, `rav_per_eq`, `debt_to_income`, `regime` |
| Demandes | `DemandsBand` + tableau | `demands_step` (table `demands` : `person_id, need, tier, requested, granted, status, reason, plan_id`) |
| Événements | `EventStrip` | `events` |
| Séries (onglet) | `ChartCard` | `…/results?table=household_steps&household_id=` : `pot, savings, debt, income_total, consumption_private, commitments` (aires empilées pour la décomposition) |

**Interactions :** clic sur un nœud → vue agent ; survol d'une arête → montant annuel exact ; clic sur une demande issue d'un plan (`plan_id`) → vue agent, décision correspondante ; en régime `separate_spheres`, le nœud FOYER est scindé en deux sous-nœuds (sphère du père, sphère de la mère).

**Acceptation :** la couleur de chaque membre est identique dans le schéma, le tableau et la frise ; les refus sont lisibles sans couleur (libellé + motif hachuré) ; les montants de l'arête = valeurs de `nta_transfer_matrix` au FCFA près.

### C3. Vue agent — `/households/:hid/agents/:pid`

**Objectif :** comprendre pourquoi l'agent a agi ainsi (explicabilité BDI).

```
┌ Mère · h0312-p2 · 43 ans · profil mother · employed_informal ───────────────────────────┐
├ ÉCONOMIQUE ───────────────┬ COGNITIVE (V2) ─────────────┬ AFFECTIVE (V3) ──────────────┤
│ revenu yl   ───           │ Intention : cope_income_loss │ stress  ───  0,58             │
│ conso cf    ───           │ Plan : cope_job_loss/seek_…  │ joie / tristesse / peur /    │
│ cg          ───           │ étape 2/3                    │ colère (4 lignes)            │
│ portefeuille ───          │ Horizon eff. 14 (base 24)    │ humeur  −0,21                │
│ lcd (nta)   ▓▓            │ Alternatives eff. 5 (base 8) │ santé   0,81 · capacité 1,0  │
│                           │ Aspirations θ par besoin     │                              │
│                           │ Croyances actives : 7        │                              │
├ Décisions récentes ──────────────────────────────────────────────────────────────────────┤
│ ▸ pas 47  first_acceptable  « Consommer 30 000 food, travailler 1.0 »                    │
│ ▾ pas 46  fallback_top_need  plan cope_job_loss/seek_and_cut                             │
│     Profil effectif : H 14 · M 5 · β 0,82 · engagement 0,8                               │
│     # │ alternative                         │ food │ health │ housing │ acceptable │ échec │
│     1 │ panier habituel                     │ 0,58 │ 0,90  │ 0,95    │ non        │ food  │
│     2 │ food plein, rest réduit             │ 0,66 │ 0,90  │ 0,95    │ non        │ food  │
│     … │ (5 considérées sur 8 possibles)     │      │        │         │            │       │
│     θ │ aspirations                         │ 0,70 │ 0,65  │ 0,70    │            │       │
│     Choix : #2 — aucune acceptable, maximise food (premier besoin attendu)               │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Données : `GET /simulations/{id}/agents/{aid}?columns=…` → `series` (`person_steps` : `yl, cf, cg, wallet, health, labor_capacity, need_level_*, aspiration_*, intention_goal, plan_id, n_beliefs_active, memory_size, horizon_eff, alternatives_eff, beta_eff, stress, mood, emo_*`), `nta` (`nta_person_steps` : `lcd, tau_net_behav, tau_net_imputed, tau_gap`), `decisions` (table `decisions` : `step, rule, chosen_id, chosen_description, n_considered, considered, aspiration, profile_eff, intention_goal, plan_id, cpt`).

Colonnes masquées selon `model_version` (§5, « Disponible en V2/V3 »). Pour le bébé (`rule = reactive`), la trace montre une seule alternative et la mention « agent réactif : 1 alternative, horizon 0 ».

**Acceptation :** chaque décision dépliée montre toutes les alternatives considérées, leurs scores projetés par besoin, le seuil θ, la règle appliquée et, si présente, l'évaluation CPT (`cpt`) ; le nombre affiché « considérées sur possibles » vient de `n_considered` et du profil.

### D. Frise de simulation (panneau ancré)

```
┌ FRISE ─────────────────────────────────────────────────────────────── [replier ▾] ┐
│ chocs        ·        ◆ job_loss            ◆ price_shock                          │
│ décisions    ▏▏▏▏ ▏▏▏▏▏▏▏▏ ▏▏▏▏▏▏▏▏▏▏▏▏▏▏▏▏ (densité de changements d'intention)        │
│ transferts   ▁▁▂▂▂▃▃▃▅▅▅▆▆▅▅▄▄▃▃ (volume intra-ménage, série fournie)              │
│ états        ▬ normal ▬▬▬▬▬▬▬ separate ▬▬ normal ▬  ▬ scolarité adolescent         │
│ 0        24        48        72        96       120       ...        240 (mois)   │
│                     ▲ pas 47                                                     │
└──────────────────────────────────────────────────────────────────────────────────┘
```

`SimulationTimeline` : pistes configurables ; curseur déplaçable (souris, `←/→` pas à pas, `Maj+←/→` ±12, `Home/End`). Données : `events` (chocs `origin=scenario`, états `regime_change`, `school_*`, `profile_transition`), `decisions` (`intention_adopted`, `plan_switched` via `events`), série de transferts = `household_steps` ou agrégat fourni par `indicators`. Le curseur écrit `step` dans Zustand + URL ; toutes les vues ouvertes se resynchronisent (requêtes `?step=`).

**Acceptation :** déplacer le curseur met à jour Dashboard/Foyer/Agent/NTA en < 300 ms (cache) ; aucune lecture automatique au chargement.

### E. Analytique NTA — `/nta`

```
┌ Profil du LCD par âge ──────────────────────┬ Revenu du travail et consommation par âge ┐
│ ▓ simulé (bande q05–q95)  - - - observé (P1)│ ── yl  ── c (= cf + cg)   aires cf/cg     │
├ Flux de transferts entre classes d'âge ─────┼ Épargne / désépargne par âge ──────────────┤
│ (flèches de Lee) 0–14 ◀══ 30–49 ══▶ 65+     │ barres ya_minus_s par âge                  │
│ épaisseur = τ net intra annuel              │                                            │
├ Transferts comportementaux vs imputés (règle ONU) ──────────────────────────────────────┤
│ tau_net_intra (comportemental) vs tau_net_imputed par âge · écart behav_vs_imputed_gap  │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Données : `…/results?table=nta_age_profile` (`age, person_years, c, cf, cg, yl, lcd, tau_net_intra, tau_net_pub, tau_net_inter, ya_minus_s, tau_net_imputed`, variantes `*_norm` via bascule « normalisé (yl 30–49) ») ; dispersion entre réplications fournie par `indicators?metrics=nta_age_profile` ; cible observée via `GET /validation`. `LeeArrows` alimenté par `nta_age_profile` (classes d'âge = regroupement **côté serveur** : `…/results?table=nta_age_profile&age_bins=0,15,25,45,65` ou `table=nta_transfer_matrix&age_bins=…`, calculé par `analysis.indicators.age_bins` ; le client n'additionne pas). Écart global : métrique `behav_vs_imputed_gap`.

**Acceptation :** l'observé est en trait discontinu noir, toujours étiqueté avec son rôle de pattern ; si `person_years` < 30 pour un âge, le point est grisé et annoté « effectif faible » ; un run d'un seul foyer affiche l'avertissement « profil par âge d'un foyer unique : non comparable à un profil national (cf. V-6) ».

### F. Comparaison de scénarios — `/compare`

```
┌ Sélection : [baseline ✓ réf.] [job_loss ✓] [family_allowance ✓] [+]   Indicateur série [debt_to_income ▾] ┐
├ Petits multiples — mêmes axes x et y ──────────────────────────────────────────────────────────┤
│ baseline (réf.)        │ job_loss               │ family_allowance                             │
│   ──── bande q05–q95   │   ────                 │   ────                                       │
│ (axes identiques, domaine = shared_domain)                                                      │
├ Écarts par rapport à la référence ──────────────────────────────────────────────────────────────┤
│ Indicateur           │ baseline         │ job_loss            │ family_allowance               │
│ Dette/revenu term.   │ 0,62 ±0,05 (20)  │ 0,91 ±0,08  +46,8 % │ 0,55 ±0,04  −11,3 %            │
│ Années d'éducation   │ …                                                                       │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

Données : `POST /comparisons` → `rows` (`Dispersion`, `pct_vs_baseline`), `series` (`SeriesBand`), `shared_domain`. **Contrainte :** les domaines d'axes viennent exclusivement de `shared_domain` ; un test vérifie que toutes les vignettes ont des échelles identiques. Variation affichée en `--signal-deficit` seulement si elle dégrade un indicateur dont le sens est déclaré « plus bas = mieux » dans le catalogue (`analysis.indicators.CATALOG.direction`) — sinon neutre.

**Acceptation :** 2 à 6 scénarios ; ordre des vignettes = ordre de sélection, référence en premier ; pas de graphique superposé par défaut (option « superposer » NICE).

### G. Validation — `/validation`

```
┌ Patterns POM (affectation figée · hash ✓) ──────────────────────────────────────────────┐
│ CALIBRATION ●                               │ VALIDATION ○  (jamais utilisés pour caler)  │
│ P1 LCD par âge   [graph obs - - / sim ●]    │ P4 Transferts  [graph obs - - / sim ○ ▨]    │
│ P2 Yl par âge    …                          │ P5 Dette/revenu …                           │
│ P3 C par âge     …                          │ P6 Pauvreté / RAV …                         │
│ distance 0,08 ≤ tol 0,10 ✓                  │ distance 0,21 > tol 0,15 ✗  (rapporté tel quel)│
│ P7 Trajectoires intergénérationnelles — EXPLORATOIRE (ni calibration ni validation)        │
├ Indices de sensibilité (Morris μ*, Sobol S1/ST) — barres horizontales triées ─────────────┤
│ aspiration_init        ████████████ 0,41                                                  │
│ stress_sensitivity     ████████ 0,27                                                      │
├ Critères des portes ──────────────────────────────────────────────────────────────────────┤
│ V1 Identités NTA bouclent à ε, 100 seeds × 20 ans          ✓ vert   preuve: tests/…       │
│ V2 ≥ 2 patterns POM avec un seul jeu de paramètres          ✗ rouge                        │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Données : `GET /validation` (E-3) → `patterns` (`pattern_results` + `role`), `assignment_hash_ok`, `sensitivity` (`sensitivity_indices` : `parameter, method, mu_star, mu_star_conf, sigma, s1, s1_conf, st, st_conf, rank, output_metric`), `gates`. Si `assignment_hash_ok = false` : encart rouge bloquant « Affectation calibration/validation modifiée — résultats de validation non recevables ».

**Acceptation :** calibration et validation dans **deux colonnes séparées** avec titre, forme de marqueur et hachure distinctes (lisible en niveaux de gris) ; un pattern de validation en échec est affiché, jamais masqué ; barres de sensibilité avec intervalles de confiance.

## 7. Catalogue de composants (props TypeScript)

```ts
type Role = "father" | "mother" | "young_adult" | "adolescent" | "child" | "baby";
type Dispersion = { mean: number; sd: number | null; q05: number | null; q95: number | null; n: number };
type Unit = "FCFA" | "FCFA/mois" | "ratio" | "%" | "mois" | "années" | "—";

interface KpiTileProps {
  label: string;                 // label_fr de l'API
  value: Dispersion;             // valeur affichée = mean ; « ± sd (n) » si n > 1
  unit: Unit;
  sparkline?: number[];          // fourni par l'API
  delta?: number | null;         // fourni par l'API ; flèche + signe, couleur selon direction
  direction?: "lower_is_better" | "higher_is_better" | "neutral";
  onOpen?: () => void;
}

interface ChartCardProps {
  title: string; subtitle?: string; unit: Unit;
  source: { runId: string; configHash: string; illustrative: boolean };
  uncertainty?: "band" | "errorbar" | "none";     // bande q05–q95 si données de réplications
  exportName: string;                              // nom de fichier SVG/PNG
  children: (size: { width: number; height: number }) => React.ReactNode;
  altText: string;                                 // résumé textuel du graphique (a11y)
  dataTable?: { columns: string[]; rows: (string | number)[][] };   // « Voir les données »
}

interface HouseholdGraphProps {
  members: { personId: string; role: Role; label: string; inHousehold: boolean }[];
  edges: { src: string; dst: string; amount: number }[];   // nta_transfer_matrix, annuel
  regime: "normal" | "separate_spheres";
  maxEdgeWidth?: number;                                     // défaut 14 px ; échelle racine carrée
  onSelectMember?: (personId: string) => void;
}

interface DemandsBandProps {
  demands: { demandId: string; personId: string; role: Role; need: string; tier: number;
             requested: number; granted: number; status: "granted" | "partial" | "refused";
             reason: string; planId: string | null }[];
  groupBy: "tier" | "member";
  onSelectDemand?: (demandId: string) => void;
}

interface DecisionTimelineProps {
  decisions: { step: number; rule: string; chosenId: string; chosenDescription: string;
               nConsidered: number; considered: AlternativeEval[]; aspiration: Record<string, number>;
               profileEff: Record<string, number>; intentionGoal: string | null; planId: string | null;
               cpt: Record<string, unknown> | null }[];
  maxAlternativesBase: number;                // pour « n considérées sur N possibles »
  onLoadMore?: () => void;                    // pagination curseur
}
type AlternativeEval = { alternative_id: string; description: string;
  projected_levels: Record<string, number>; acceptable: boolean; failed_need: string | null };

interface SimulationTimelineProps {
  horizonMonths: number;
  tracks: { id: "shocks" | "decisions" | "transfers" | "states"; label: string;
            items: { step: number; endStep?: number; kind: string; label: string }[];
            series?: number[] }[];
  cursor: number;
  onCursorChange: (step: number) => void;
}

interface SmallMultiplesGridProps<T> {
  panels: { id: string; title: string; isBaseline: boolean; data: T }[];
  xDomain: [number, number]; yDomain: [number, number];   // OBLIGATOIRES : shared_domain
  renderPanel: (data: T, scales: { x: [number, number]; y: [number, number] }) => React.ReactNode;
}

interface LeeArrowsProps {
  ageBins: { id: string; label: string; centerAge: number }[];
  flows: { from: string; to: string; amount: number; kind: "intra" | "public" }[];   // servis par l'API
}

interface ObservedVsSimulatedProps {
  patternId: string; name: string;
  role: "calibration" | "validation" | "exploratory";   // forme/hachure/badge selon rôle
  observed: { x: number; y: number }[] | null;
  simulated: { x: number; y: number; q05?: number; q95?: number }[];
  distance: number | null; tolerance: number | null; pass: boolean | null;
}

interface SensitivityBarsProps {
  method: "morris" | "sobol";
  rows: { parameter: string; value: number; conf: number | null; secondary?: number }[]; // mu_star|s1 ; sigma|st
  sortBy: "value";
}

interface CriteriaTableProps {
  rows: { gate: "V1" | "V2" | "V3"; criterion: string; status: "green" | "red" | "pending"; evidence: string | null }[];
}
```

Règles : `SmallMultiplesGrid` refuse de rendre sans `xDomain`/`yDomain` (erreur de type) ; `ChartCard` exige `altText` ; `HouseholdGraph` utilise une échelle d'épaisseur racine carrée (surface ∝ montant), légende d'échelle incluse ; aucun composant n'importe une fonction statistique (`d3-array.mean/deviation/quantile` interdits par une règle ESLint `no-restricted-imports`, sauf `extent` pour l'auto-dimensionnement hors comparaison).

## 8. Accessibilité

- Contraste texte ≥ 4.5:1 (`--text-muted` sur `--bg` vérifié) ; éléments graphiques porteurs de sens ≥ 3:1.
- Information jamais portée par la seule couleur : statut des demandes (libellé + motif), rôle de pattern (forme + badge), déficit (signe + couleur).
- Clavier : navigation complète ; curseur de frise `role="slider"` avec `aria-valuenow/min/max/valuetext` (« pas 47, an 3 mois 11 ») ; lignes de décision dépliables `aria-expanded`.
- Graphiques : `role="img"` + `aria-label` = `altText` ; lien « Voir les données » ouvrant un tableau équivalent.
- Focus visible (`--focus`, 2 px).

## 9. i18n

FR par défaut (`fr-FR` pour nombres et dates relatives « an 3, mois 11 ») ; clés de traduction en anglais (`dashboard.kpi.debt`) ; libellés d'indicateurs = `label_fr` serveur ; noms de besoins, paliers, statuts, raisons, règles et types d'événements traduits via tables de correspondance (`need.food → alimentation`, `reason.budget_exhausted → budget épuisé`, `rule.fallback_top_need → repli sur le besoin prioritaire`).

## 10. Performance

- Séries longues : paramètre serveur `every` (sous-échantillonnage) calculé pour ~1 point/pixel ; jamais de décimation client par moyenne.
- Tables : virtualisation (`@tanstack/react-virtual`), pagination par curseur.
- Format `columnar` pour toutes les séries.
- Budget : premier rendu Dashboard < 1,5 s sur run en cache, bundle initial < 400 Ko gz (Plot/D3 chargés à la demande par écran).

## 11. Priorisation et tests

### MUST / SHOULD / NICE (repris de la feuille de route §17, déclinés)

| Priorité | Éléments |
|---|---|
| MUST (mémoire) | Figures reproductibles **par script** (`analysis/figures.py`) — hors frontend. Rien d'autre n'est obligatoire. |
| SHOULD | Démonstrateur Solara (§12) **ou** frontend limité à : Dashboard, Vue foyer, Analytique NTA, états §5. |
| NICE | Scénarios (lancement), Vue agent avec traces, Frise, Comparaison, Validation, thème sombre, superposition en comparaison. |

### Tests

| Niveau | Outil | Contenu |
|---|---|---|
| Unitaires | Vitest + Testing Library | `KpiTile` (affiche ± sd uniquement si n > 1), `DemandsBand` (statut lisible sans couleur), `SmallMultiplesGrid` (domaines identiques), formatage FR, mapping rôle → token |
| Contrat | Vitest | les fixtures JSON valident contre `schema.d.ts` (types générés) |
| Règle « aucun calcul » | ESLint | `no-restricted-imports` statistiques ; revue |
| Parcours | Playwright (sur API réelle + mini-run V1) | lancer une simulation → suivre → ouvrir Dashboard ; Dashboard → événement → foyer → agent → décision dépliée ; curseur de frise synchronise 3 vues ; comparaison de 3 scénarios ; run en échec InvariantViolation → encart bloquant |
| Captures de référence | Playwright `toHaveScreenshot` | chaque écran en thème clair à 1440×900 sur fixtures figées ; contrôle du daltonisme : captures filtrées deutéranopie/protanopie revues une fois |
| Accessibilité | `@axe-core/playwright` | zéro violation sérieuse par écran |

## 12. Démonstrateur léger Solara (Q8, optionnel)

`src/family_abm/viz/solara_app.py` (dépendance optionnelle `family_abm[viz]`) utilisant la visualisation native de Mesa 3 : un foyer, curseur de pas, trois graphiques (séries économiques par membre avec les tokens de couleur §2.1, besoins, LCD par membre) et le tableau des demandes du pas. Lit le modèle **en direct** (pas d'API) ; ne contient aucun calcul d'indicateur (appelle `analysis.indicators`). Lancement : `solara run src/family_abm/viz/solara_app.py`. Suffisant pour la soutenance si l'API n'est jamais construite.

## 13. Détails tranchés dans ce document

- Palette des membres Okabe-Ito sans rouge (valeurs §2.1) ; surplus en ardoise neutre, déficit en rouge ; calibration/validation distinguées par forme (● / ○ + hachure) et badge, pas par couleur.
- Couleur liée au **rôle** (stable), pas au profil.
- Inter + IBM Plex Mono auto-hébergées ; base 13 px ; chiffres tabulaires.
- Frise = panneau ancré partagé, pas une section ; pas de lecture animée par défaut.
- URL = source de vérité de la sélection ; Zustand = miroir.
- Sous-échantillonnage uniquement côté serveur (`every`) ; classes d'âge des flèches de Lee regroupées côté serveur (paramètre `age_bins` de `GET …/results`, 60 §4.3).
- Médiane de l'histogramme dette/revenu et sens « plus bas = mieux » des indicateurs fournis par `analysis.indicators.CATALOG` (champ `direction` du catalogue, exposé par `IndicatorValue.direction` et `ComparisonRow.direction`, 60 §4.4/§4.8).
- En foyer unique, Gini/Pauvreté remplacés par `rav_per_eq` et `cohesion_index`.
- Solara comme démonstrateur SHOULD alternatif au frontend.
