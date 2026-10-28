# Attestations de l'auteur

Une case manuelle d'une porte (90 §3) est cochée par un fichier `docs/attestations/<gate>-<item>.md`
**rédigé et signé par l'auteur**, jamais par Claude Code. `scripts/gate.py` vérifie sa présence.

Attestations attendues :

| Fichier | Objet | Exigé avant |
|---|---|---|
| `T-004-odd-v0-v1.md` | relecture et validation de `odd/ODD_v0_conceptual.md` et `odd/ODD_v1_economic.md` (T-004) | T-007 |
| `G1-6.md` | ODD-V1 cohérent avec le code (G1.6) | porte V1 |

Contenu minimal : nom, date, commit relu (`git rev-parse HEAD`), périmètre relu, corrections apportées.
