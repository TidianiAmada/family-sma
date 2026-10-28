# Règles de validation RV-01 à RV-20

> Référentiel unique de qualité scientifique, logicielle et rédactionnelle. Les personas (`.claude/agents/`), les skills (`.claude/skills/`) et la commande `/controle-regles` s'y réfèrent par identifiant.
>
> **Gravité :** ⛔ bloquant (aucun commit / aucune porte) · ⚠️ à corriger avant la fin du ticket · ℹ️ à signaler.

| ID | Règle | Gravité | Vérifiée par |
|---|---|:-:|---|
| **RV-01** | Un seul `PersonAgent` ; l'hétérogénéité vient du `CognitiveProfile` (capacités + paramètres), jamais d'un branchement sur le rôle. | ⛔ | `tests/architecture/test_single_person_class.py`, `test_no_role_branching.py` ; persona `architecte-gardien` |
| **RV-02** | Aucun nombre du modèle dans `src/` : tout paramètre est dans `config/`, validé et doté d'une provenance. | ⛔ | `test_no_magic_numbers.py` ; `revue-qualite` |
| **RV-03** | Positionnement prudent : jamais « personne n'a fait », « premier », « inédit ». « À notre connaissance » seulement adossé à la recherche systématique documentée (annexe de protocole). | ⛔ | persona `redacteur-odd`, `bibliothecaire` ; grep dans `/controle-regles` |
| **RV-04** | Le `Ledger` est l'unique source de vérité monétaire ; les invariants échouent durement ; aucun ε n'est relâché pour faire passer un test. | ⛔ | `tests/invariants/` ; persona `comptable-nta` |
| **RV-05** | Les NTA sont une couche de mesure en lecture seule ; `nta/accounts.py` et `nta/imputation.py` restent séparés. | ⛔ | `lint-imports` (C1, C3) |
| **RV-06** | ODD d'abord : aucun sous-modèle codé avant d'être décrit dans l'ODD ; un écart code/ODD se corrige dans le même commit. | ⛔ | `tests/architecture/test_odd_sync.py`, `/odd-sync` ; persona `redacteur-odd` |
| **RV-07** | Toute affirmation de résultat (mémoire, ODD, docstring, rapport) renvoie à une expérience nommée et à une figure ou table reproductible par script. | ⚠️ | persona `methodologiste-validation` |
| **RV-08** | Chaque conclusion porte sa condition de validité (« sous l'hypothèse que… »). | ⚠️ | persona `methodologiste-validation`, `redacteur-odd` |
| **RV-09** | Aucun résultat n'est prédit avant exécution ; les résultats nuls ou négatifs sont rapportés tels quels. | ⛔ | personas `methodologiste-validation`, `redacteur-odd` |
| **RV-10** | Déterminisme : tout aléa passe par `RngStreams` ; même seed ⇒ mêmes tables au bit près. | ⛔ | `tests/regression/test_reproducibility.py` |
| **RV-11** | L'analyse de sensibilité (criblage de Morris) précède toute calibration ; on ne calibre que les paramètres retenus. | ⛔ | `analysis/calibration.py` (refus) ; persona `methodologiste-validation` |
| **RV-12** | On ne calibre jamais une variable de traitement d'une expérience. | ⛔ | registre `treatment_variable_of` + test |
| **RV-13** | Seuls V-1 (code) et V-2 (comptable) sont binaires ; les autres niveaux produisent des écarts quantifiés et discutés, pas des verdicts. | ⚠️ | persona `methodologiste-validation` |
| **RV-14** | La validation sur patterns retenus n'est pas une validation hors-échantillon temporelle ; l'écrire ainsi. | ⛔ | grep « hors-échantillon » dans `/controle-regles` |
| **RV-15** | Toute valeur agrégée sur réplications est montrée avec sa dispersion (écart-type ou intervalle 5–95 %, n). | ⚠️ | skill `figure-memoire` ; persona `ingenieur-interface` |
| **RV-16** | L'affectation des patterns calibration/validation est figée avant toute calibration : `config/patterns.yaml` + hash ; aucun pattern de validation dans une fonction de perte. | ⛔ | `test_patterns_frozen.py`, `test_calibration_leak.py` |
| **RV-17** | Toute référence citée a une fiche de lecture (statut READ/PARTIAL/FOUNDATION) ou est marquée « à vérifier » ; aucune citation décorative ; citations exactes avec page. | ⚠️ | persona `bibliothecaire` |
| **RV-18** | Tout composant a une ligne dans `docs/MATRICE_QUESTION_MODELE.md` reliée à une expérience ; sinon il sort. | ⚠️ | persona `architecte-gardien` |
| **RV-19** | La plateforme (API + interface) ne contient aucune logique de modèle ni calcul d'indicateur ; elle ne lit que les tables Parquet et n'appelle le moteur que via `api_entry.run_simulation` ; le moteur reste exécutable sans elle. | ⛔ | contrats `lint-imports` A1 ; `test_engine_standalone.py` ; persona `ingenieur-interface` |
| **RV-20** | Un run issu d'une configuration contenant un `PLACEHOLDER` est étiqueté « illustratif » dans toute figure, table et phrase qui l'utilise. | ⚠️ | skill `figure-memoire` ; persona `redacteur-odd` |
