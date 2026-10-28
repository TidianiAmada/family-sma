---
name: ecrire-invariant-nta
description: Gabarit et procédure pour ajouter ou modifier un invariant comptable (INV-xx) du modèle — formule sur le Ledger, ε, portée, test sain, test d'injection, message d'erreur. À utiliser dès qu'un sous-modèle crée une nouvelle catégorie de flux, un nouveau compte ou une nouvelle identité NTA.
---
# Écrire un invariant comptable

Un invariant n'existe que s'il est capable d'échouer. Chaque INV a donc deux tests : un qui passe sur un run sain, un qui échoue sur une faute injectée.

## Fiche de l'invariant (à ajouter dans la table des invariants de `specs/10_SPEC_V1_ECONOMIC.md` §12 et dans l'ODD §7.12)
```
ID          : INV-xx
Énoncé      : (une phrase en français)
Formule     : (agrégation sur ledger.entries(step), notation de 02 §9)
Portée      : compte | personne | foyer | global ; à chaque pas | fin de run
ε           : 0,01 FCFA (Decimal) — ne jamais relâcher
Dépendances : catégories et comptes utilisés
Version     : V1 | V2 | V3
```

## Implémentation (`nta/invariants.py`)
```python
def check_inv_xx(ledger: Ledger, step: Step, ctx: InvariantContext) -> None:
    """INV-xx — <énoncé>. Référence : ODD-V1 §7.12."""
    lhs = ...  # agrégation Decimal depuis ledger.entries(step)
    rhs = ...
    if abs(lhs - rhs) > EPSILON:
        raise InvariantViolation(
            inv="INV-xx", step=step, household_id=ctx.household_id,
            account=..., category=..., expected=rhs, observed=lhs,
        )
```
- Calcul **uniquement** à partir du Ledger (et des parts ω pour l'attribution), jamais des états d'agents — sauf l'invariant « cache = Ledger », dont c'est l'objet.
- Pas de `float`. Pas de `math.isclose`.
- Enregistrer l'invariant dans le registre appelé à chaque pas par `model/scheduler.py`.

## Tests (`tests/invariants/test_inv_xx.py`)
1. **Sain** : run baseline seed fixée, 240 pas, aucune exception.
2. **Injection** : construire un Ledger minimal valide, puis injecter **une** faute typique (écriture manquante, montant altéré de 0,02, mauvaise catégorie, bénéficiaire absent, part ω erronée) → `pytest.raises(InvariantViolation)` et vérifier `inv == "INV-xx"`, le pas et le compte.
3. **Propriété** (si possible) : pour toute séquence aléatoire d'écritures valides (hypothesis), l'invariant tient.

## Message d'erreur
Doit permettre de localiser la faute sans débogueur : INV, pas, foyer, compte, catégorie, attendu, observé, écart.
