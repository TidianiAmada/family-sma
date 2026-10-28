---
name: figure-memoire
description: Règles et outillage pour produire des figures scientifiques reproductibles de family_abm destinées au mémoire et cohérentes avec l'interface — palette par membre, signaux, types de graphiques autorisés, incertitude, échelles partagées, étiquetage des runs illustratifs, export. À utiliser pour écrire ou modifier analysis/figures.py ou tout graphique (matplotlib, Observable Plot).
---
# Figures du mémoire

## Règles
1. **Reproductible par script** : chaque figure est produite par une fonction de `analysis/figures.py` lisant uniquement les tables Parquet ; `uv run python -m family_abm figures --all` régénère tout. Jamais de figure faite à la main ni dans un notebook.
2. **Types** : lignes (séries temporelles, profils par âge), barres (comparaisons, indices de sensibilité triés, horizontales), aires empilées (décompositions). Pas de camembert, pas de 3D, pas de double axe Y.
3. **Couleur porteuse de sens** : une couleur par membre, constante (palette ci-dessous, identique aux jetons de l'interface) ; rouge réservé au déficit (LCD > 0) et aux alertes ; surplus en ardoise.
4. **Incertitude toujours visible** : bande 5–95 % (ou ± écart-type, le dire en légende) et n dans la légende ou le titre.
5. **Comparaisons** : petits multiples aux **mêmes échelles** ; jamais d'axes libres entre scénarios comparés.
6. **Observé vs simulé** : observé en trait discontinu ; patterns de calibration et de validation visuellement distingués (badge ou couleur de cadre), jamais mélangés sans légende.
7. **Runs illustratifs** : si un run provient d'une configuration contenant un `PLACEHOLDER`, ajouter la mention « illustratif — valeurs provisoires » sous le titre.
8. **Texte** : titres et axes en français, unités entre parenthèses (FCFA/mois, années, part), séparateur de milliers espace fine, virgule décimale.
9. **Export** : PDF (vectoriel) pour le mémoire + PNG 300 dpi ; nom = `fig_<ID>_<sujet>.pdf` ; métadonnées (commit, ConfigHash) en propriété du fichier.

## Palette (identique à `specs/70_SPEC_UX_UI.md`)
```python
MEMBER_COLORS = {
    "father": "#0072B2", "mother": "#CC79A7", "young_adult": "#009E73",
    "adolescent": "#E69F00", "child": "#56B4E9", "baby": "#8C6D1F",
    "household": "#4D4D4D",
}
SIGNAL = {"deficit": "#C62828", "surplus": "#5B6770", "warning": "#8A5A00", "ok": "#2E7D32"}
```

## Feuille de style matplotlib (`src/family_abm/analysis/family_abm.mplstyle`)
```
figure.figsize: 6.3, 3.9
figure.dpi: 150
savefig.dpi: 300
savefig.bbox: tight
font.family: sans-serif
font.size: 9
axes.titlesize: 10
axes.labelsize: 9
axes.spines.top: False
axes.spines.right: False
axes.grid: True
grid.color: "#E0E0E0"
grid.linewidth: 0.5
lines.linewidth: 1.4
legend.frameon: False
axes.formatter.use_locale: True
```

## Gabarit de fonction
```python
def fig_e1_lcd_by_member(catalog: Catalog, experiment_id: str, out_dir: Path) -> list[Path]:
    """Profil du LCD par membre (moyenne et bande 5–95 %). Référence : 50_SPEC E1."""
    df = catalog.query("...")            # aucune agrégation métier ici : lire les indicateurs de analysis/
    with plt.style.context(STYLE_PATH):
        ...
    return save_figure(fig, out_dir / "fig_E1_lcd_by_member", meta=run_meta)
```
