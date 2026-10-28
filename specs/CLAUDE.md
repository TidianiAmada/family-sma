# CLAUDE.md — family_abm

> À copier à la racine du dépôt `family_abm/`. Claude Code lit ce fichier à chaque session.

## Le projet en une phrase

Simulation multi-agents (Python 3.12, Mesa 3) d'un foyer sénégalais de six personnes — père, mère, jeune adulte, adolescent, enfant, bébé — puis d'une population de foyers, dont les conséquences socio-économiques sont mesurées par les **National Transfer Accounts** (NTA). C'est le support d'un mémoire de Master (UIDT Thiès) : **la rigueur scientifique prime sur les fonctionnalités**.

## Où sont les spécifications

`specs/` est la source normative, en lecture seule. Ordre de lecture :

1. `specs/00_DECISIONS.md` — décisions fermées (D1–D13, Q5–Q9, S1–S10)
2. `specs/01_ARCHITECTURE.md` — dépôt, couches, ordonnancement en 3 temps, boucles B1–B3
3. `specs/02_DOMAIN_MODEL.md` — entités, états, Ledger, règle d'attribution NTA
4. `specs/03_CONFIG_SCHEMAS.md` — YAML et registre des paramètres
5. `specs/04_DATA_MODEL.md` — tables Parquet et catalogue d'indicateurs
6. La spec de la version en cours : `10_SPEC_V1_ECONOMIC.md` → `20_SPEC_V2_COGNITIVE.md` → `30_SPEC_V3_AFFECTIVE_POPULATION.md`
7. `40_SPEC_VALIDATION_CALIBRATION.md`, `50_SPEC_EXPERIMENTS.md`
8. Plateforme (après la porte V1) : `60_SPEC_API.md`, `70_SPEC_UX_UI.md`
9. `90_TEST_STRATEGY_AND_GATES.md`, `95_IMPLEMENTATION_PLAN.md` — tickets ordonnés

Si deux specs se contredisent : `00` > `02` > `04` > `01` > `03` > spec de version > autres. Signale la contradiction à l'utilisateur au lieu de choisir silencieusement.

## Règles dures (un écart = arrêt et question à l'utilisateur)

1. **Un seul `PersonAgent`.** Jamais de sous-classe par rôle, jamais `if role == ...` dans la logique. L'hétérogénéité vient du `CognitiveProfile` (capacités + paramètres).
2. **Un seul point polymorphe : `DecisionEngine`.** L'allocation du foyer est une fonction pure paramétrée, pas une hiérarchie.
3. **Aucun nombre du modèle dans `src/`.** Tout paramètre est dans `config/*.yaml`, validé par Pydantic.
4. **Le `Ledger` est la seule source de vérité monétaire.** Toute variation de valeur = une écriture double entrée. Les états ne portent que des caches vérifiés par invariant.
5. **Les invariants échouent durement** (`InvariantViolation`), jamais d'avertissement. Ne jamais affaiblir un ε ni désactiver un invariant pour faire passer un test.
6. **`nta/` est en lecture seule.** Aucun module de `agents/`, `decision/`, `cognition/`, `economy/`, `health/` n'importe `nta/` ou `analysis/`. `nta/accounts.py` et `nta/imputation.py` ne s'importent pas mutuellement.
7. **Le moteur de décision ne lit jamais l'affect** : il reçoit un `EffectiveCognitiveProfile`.
8. **Tout aléa passe par `RngStreams`** (sous-flux nommés). Même seed → trajectoire identique au bit près.
9. **ODD d'abord.** Aucun sous-modèle n'est codé avant d'être décrit dans `odd/ODD_v*.md`. Quand le code diverge de l'ODD, on corrige l'ODD **dans le même commit**.
10. **Portes.** Ne commence pas une version tant que les critères de sortie de la précédente ne sont pas verts (`docs/GATES.md`, `make gate-v1` etc.). Pas de code API/frontend avant la porte V1 (schémas de sortie stables).
11. **Calibration/validation séparées.** Ne jamais modifier `config/patterns.yaml` (rôles figés, hash vérifié). Ne jamais mettre un pattern de rôle `validation` dans une fonction de perte. Ne jamais calibrer une variable de traitement d'une expérience.
12. **Ne pas prédire les résultats.** N'écris jamais dans la doc, les commentaires ou les messages un résultat attendu pour E4 ou toute expérience non exécutée. Rapporte les résultats négatifs tels quels.
13. **Le moteur reste exécutable seul** : `uv run python -m family_abm run --scenario baseline --seed 42`, sans API, frontend ni base.
14. **Pas d'affirmation d'originalité** dans la doc générée (« à notre connaissance », jamais « personne n'a fait »).

## Conventions

- Python 3.12, `uv`, `ruff` (format + lint), `mypy --strict` sur `src/`, `pytest` + `hypothesis`.
- Code et identifiants en anglais ; docstrings, ODD et docs en français.
- États : `@dataclass(slots=True)` passifs. Objets-valeurs : `frozen=True`.
- Montants : `Decimal` (quantum 0,01) dans le `Ledger`, `float64` dans les tables.
- Sorties : Parquet via `io/parquet.py` uniquement ; jamais de CSV pour les résultats.
- Pas de logique dans `notebooks/`.
- Commits : un ticket = un commit (ou une petite série), message `T-xxx: <résumé>` ; ODD et `docs/MATRICE_QUESTION_MODELE.md` mis à jour dans le même commit quand concernés.

## Commandes

```bash
uv sync                                   # installer
uv run pytest -q                          # tous les tests
uv run pytest tests/invariants -q         # invariants (V-1/V-2)
uv run lint-imports                       # contrats de couches
uv run mypy src/
uv run python -m family_abm run --scenario baseline --seed 42
uv run python -m family_abm experiment E1
uv run python -m family_abm sa morris
uv run python -m family_abm calibrate --twin        # expérience jumelle
uv run python -m family_abm figures --all
make gate-v1 | gate-v2 | gate-v3                     # vérifie une porte, met à jour docs/GATES.md
```

## Personas (`.claude/agents/`) — quand les appeler

| Persona | Rôle | Appeler |
|---|---|---|
| `architecte-gardien` | couches, point polymorphe unique, config externe, matrice (lecture seule) | avant de clore tout ticket qui crée/déplace un module, une classe ou un paramètre |
| `comptable-nta` | Ledger, identités NTA, attribution ω, imputation ONU, invariants | tout ticket `economy/`, `nta/` ; toute `InvariantViolation` |
| `modelisateur-cognitif` | satisficing, plans, mémoire, aspiration, β-δ, appraisal, modulation, CPT | tout ticket `decision/`, `cognition/` ; expliquer une décision d'agent |
| `ingenieur-tests` | tests d'abord, propriétés, injection, golden, portes | au début de chaque ticket ; avant une porte |
| `methodologiste-validation` | POM, sensibilité, calibration, plans d'expérience, honnêteté des conclusions | toute expérience, calibration, rapport de résultats |
| `redacteur-odd` | ODD, docstrings, fiches, chapitres 3–5 | après tout changement de sous-modèle ; toute rédaction pour le mémoire |
| `bibliothecaire` | références, citations exactes, recherche systématique | toute citation ajoutée ; positionnement ; nettoyage bibliographique |
| `relecteur-code` | qualité du code (lisibilité, typage, erreurs, performance) | fin de ticket, avant commit significatif |
| `ingenieur-interface` | API FastAPI et interface React (piste B) | tickets T-060 à T-081 |

## Skills (`.claude/skills/`)

`implementer-sous-modele` (procédure de bout en bout d'un ticket moteur) · `ecrire-invariant-nta` · `rediger-odd` · `concevoir-experience` · `revue-qualite` · `figure-memoire` · `fiche-conception` · `fiche-lecture`.

**Boucle de qualité d'un ticket :** `ingenieur-tests` (tests) → implémentation avec `implementer-sous-modele` → `comptable-nta` / `modelisateur-cognitif` selon le domaine → `redacteur-odd` (ODD + docstrings) → `architecte-gardien` + `relecteur-code` (revues) → commit.

Règles de qualité de référence : `docs/REGLES_VALIDATION.md` (RV-01 à RV-20).

## Commandes de session Claude Code

- `/implement-ticket T-xxx` — implémente un ticket de `specs/95_IMPLEMENTATION_PLAN.md`
- `/gate-check v1|v2|v3` — exécute la porte et rapporte case par case
- `/odd-sync` — compare le code et l'ODD de la version courante, liste les écarts
- `/controle-regles [tout|code|doc]` — contrôle le dépôt contre RV-01 à RV-20
- `/bilan-session` — journal de fin de session dans `docs/JOURNAL.md`

## Quand t'arrêter et demander

- Une spec est ambiguë ou contradictoire sur un comportement du modèle.
- Un invariant échoue et la cause n'est pas un bug évident.
- Un budget de performance est dépassé de plus de 2×.
- Tu es tenté d'ajouter un composant absent de la matrice `docs/MATRICE_QUESTION_MODELE.md` (« tout composant sans expérience associée sort »).
