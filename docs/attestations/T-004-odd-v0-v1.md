# Attestation T-004 — relecture de l'ODD V0 et de l'ODD V1

| Champ | Valeur |
|---|---|
| Auteur | Cheikh Ahmadou Tidiani TOP |
| Date | 2026-10-28 |
| Commit relu | `b78f4dc` (ODD V0) ; `351bf66` (ODD V1) |
| Ticket | T-004 (exigée avant T-007) |

## Périmètre et décision

| Document | Relu | Validé | Corrections apportées |
|---|---|---|---|
| `odd/ODD_v0_conceptual.md` | oui | oui | aucune |
| `odd/ODD_v1_economic.md` | oui | oui | aucune |

Ajouts apportés à `odd/ODD_v1_economic.md` depuis la copie de `specs/odd` (à relire avec la V1) :

- §2.1 : seuls `capabilities`, `max_alternatives`, `planning_horizon`, `attended_needs`, `aspiration_init` et `impulsivity` agissent en V1 ; les autres paramètres du profil sont lus et validés sans effet (commit `7f7ce28`, T-003).
- §5 : membres sans `wage_key` ni `pooling` → clés par défaut de la configuration (`default_wage_key`, `default_pooling_key`) (commit `ab60a98`, décision J1).
- §6 : agrégats EHCVM 2018/2019 repris comme paramètres DIRECT (salaires, éducation, logement, seuil de pauvreté par tête) ; âges de bascule NTA 2011 comme contrôle qualitatif (commit `351bf66`, décisions J2–J5).
- §7.1 : `active_ages` lus comme intervalles semi-ouverts [min, max[ ; vieillissement et transitions en fin de pas, après la collecte (commit `b78f4dc`, T-006).

## Déclaration

J'ai relu les documents marqués « relu » ci-dessus et j'en valide le contenu comme description du modèle.

Signature : Cheikh Ahmadou Tidiani TOP — 2026-10-28
