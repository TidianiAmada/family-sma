# Spécifications d'implémentation — SMA Famille × NTA

**Projet :** « La cellule familiale comme système multi-agents : architecture cognitive hétérogène et mesure des conséquences socio-économiques via les National Transfer Accounts » — Cheikh Ahmadou Tidiani TOP, Master Data Science & IA, UIDT Thiès.

**Source :** feuille de route architecturale et technique v2 (17 septembre 2026), proposition de sujet, proposition d'attribution. Ce dossier transforme la feuille de route en spécifications exécutables par Claude Code.

---

## Contenu

| Fichier | Rôle | Version |
|---|---|---|
| `install-claude.ps1`, `install-claude.cmd` | Installation automatisée du dispositif Claude dans `.claude\` (Windows) | toutes |
| `CLAUDE.md` | Règles dures et commandes — **à copier à la racine du dépôt** | toutes |
| `claude-commands/` | 5 commandes : `/implement-ticket`, `/gate-check`, `/odd-sync`, `/controle-regles`, `/bilan-session` — **à copier dans `.claude/commands/` du dépôt** | toutes |
| `claude-agents/` | 9 personas (sous-agents) : architecte-gardien, comptable-nta, modelisateur-cognitif, ingenieur-tests, methodologiste-validation, redacteur-odd, bibliothecaire, relecteur-code, ingenieur-interface — **à copier dans `.claude/agents/`** | toutes |
| `claude-skills/` | 8 skills : implementer-sous-modele, ecrire-invariant-nta, rediger-odd, concevoir-experience, revue-qualite, figure-memoire, fiche-conception, fiche-lecture — **à copier dans `.claude/skills/`** | toutes |
| `docs/REGLES_VALIDATION.md` | Règles de qualité RV-01 à RV-20 (référence des personas et de `/controle-regles`) | toutes |
| `00_DECISIONS.md` | Décisions fermées D1–D13, questions Q5–Q9 tranchées, décisions logicielles S1–S10 | toutes |
| `01_ARCHITECTURE.md` | Conteneurs, structure du dépôt, couches et contrats, pipeline en 3 temps, boucles B1–B3, RNG, budgets de performance | toutes |
| `02_DOMAIN_MODEL.md` | Classes, énumérations, états, demandes/allocations, objets cognitifs, trace de décision, Ledger, règle d'attribution NTA, machines à états | toutes |
| `03_CONFIG_SCHEMAS.md` | YAML complets (profils, foyer, besoins, économie, scénarios, expériences), registre des paramètres, patterns figés | toutes |
| `04_DATA_MODEL.md` | Tables Parquet de sortie et catalogue d'indicateurs (formules de référence) | toutes |
| `10_SPEC_V1_ECONOMIC.md` | Baseline économique : sous-modèles, invariants, tests, E1, porte V1 | V1 |
| `20_SPEC_V2_COGNITIVE.md` | Mémoire, croyances, désirs, intentions, plans, aspiration, β-δ, poids, porte V2 | V2 |
| `30_SPEC_V3_AFFECTIVE_POPULATION.md` | Appraisal, émotions, modulation, population, sphères séparées, CPT, efficacité, porte V3 | V3 |
| `40_SPEC_VALIDATION_CALIBRATION.md` | V-1…V-6, POM, données, sensibilité, calibration, expérience jumelle | V2–V3 |
| `50_SPEC_EXPERIMENTS.md` | Runner générique et fiches E1–E9, E-SA, scénarios contrefactuels | V1–V3 |
| `60_SPEC_API.md` | Backend FastAPI (après porte V1) | plateforme |
| `70_SPEC_UX_UI.md` | Interfaces React : tokens, écrans, composants, états | plateforme |
| `90_TEST_STRATEGY_AND_GATES.md` | Stratégie de tests, non-régression, portes de passage | toutes |
| `95_IMPLEMENTATION_PLAN.md` | Tickets ordonnés T-001…T-081 | toutes |
| `odd/ODD_v0…v3` | Brouillons d'ODD (Grimm et al. 2020) par version | V0–V3 |
| `docs/MATRICE_QUESTION_MODELE.md` | Question → modèle → code → expérience → chapitre | toutes |
| `docs/FICHES_CONCEPTION.md` | Fiches de conception 1–10 | toutes |

## Démarrer avec Claude Code

**Windows (automatisé)** — double-cliquer `install-claude.cmd`, ou en PowerShell depuis ce dossier :

```powershell
.\install-claude.ps1                         # installe dans le dossier parent (ex. D:\family-sma)
.\install-claude.ps1 -IncludeProjectDocs     # + odd\ et docs\ (sans écraser l'existant)
.\install-claude.ps1 -RepoPath D:\family_abm -CopySpecs -IncludeProjectDocs   # dépôt ailleurs
.\install-claude.ps1 -WhatIf                 # simulation, rien n'est écrit
.\install-claude.ps1 -Prune                  # retire les personas/skills/commandes supprimés de specs
```

Le script copie `claude-agents\` → `.claude\agents\`, `claude-skills\` → `.claude\skills\`, `claude-commands\` → `.claude\commands\` et `CLAUDE.md` à la racine. Il vérifie le frontmatter de chaque fichier et sauvegarde toute version remplacée dans `.claude-backup\<horodatage>\` (ajouté au `.gitignore`). `CLAUDE.md`, `odd\` et `docs\` ne sont jamais écrasés sans `-Force`, car tu les modifies. Il se relance sans risque après chaque mise à jour de `specs`.

**Manuel (bash)** :

```bash
mkdir family_abm && cd family_abm && git init
cp -r <ce dossier> specs/
cp specs/CLAUDE.md ./CLAUDE.md
mkdir -p .claude/commands .claude/agents .claude/skills
cp specs/claude-commands/*.md .claude/commands/
cp specs/claude-agents/*.md .claude/agents/
cp -r specs/claude-skills/* .claude/skills/
mkdir -p odd docs && cp specs/odd/*.md odd/ && cp specs/docs/*.md docs/
claude            # puis : /implement-ticket T-001
```

## Ce qu'il faut savoir avant de lancer

- **Les montants par défaut sont des placeholders** (`provenance: PLACEHOLDER`). Le modèle tourne et produit des runs marqués « illustratifs » tant que les profils NTA (CREFAT) ou l'EHCVM ne les ont pas remplacés.
- **Les ODD sont des brouillons générés** : ils deviennent les chapitres 3 à 5 du mémoire et doivent être relus, corrigés et appropriés par l'auteur (ticket T-004/T-020/T-040 : attestation de relecture).
- **Les références marquées « à vérifier »** dans les fiches et ODD doivent être confirmées avant d'être citées.
- **L'application (API + interface)** démarre après la porte V1 et avance en parallèle de V2/V3 (piste B du plan).
- Chaque spec de version contient une section « Détails tranchés dans ce document » : ce sont les choix faits pour combler un vide de la feuille de route ; à relire en priorité.
