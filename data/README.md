# Données — provenance, licence, accès

Les microdonnées ne sont jamais commitées (`data/raw/` est ignoré par git). Seuls des repères
agrégés et non identifiants vont dans `data/processed/` (40 §4.4).

## Sources disponibles

| Source | Fichier | Données | Usage dans le modèle | Inventaire |
|---|---|---|---|---|
| ANSD (2021), *Rapport final de l'Enquête harmonisée sur les conditions de vie des ménages (EHCVM), Sénégal* | `docs/Rapport-final-EHCVM-vf-Senegal_2021.pdf` | **édition 2018/2019** (collecte sept.-déc. 2018 et avr.-juil. 2019), agrégats publiés | paramètres DIRECT (décision J3), seuil de pauvreté par tête et cible P6 (J2) | `docs/sources/INVENTAIRE_EHCVM_SENEGAL_2018_2019.md` |
| CREFAT (2016), *Profils NTA du Sénégal*, diaporama, Saly | `docs/NTA_SENEGAL_2016.pdf` | ESPS 2, **2011** ; profils par âge en graphique seulement | âges de bascule du LCD, contrôle qualitatif P1q (J4) | `docs/sources/INVENTAIRE_NTA_SENEGAL_2016.md` |

Le nom du fichier PDF de l'EHCVM porte « 2021 » (année de publication) ; les données sont de
2018/2019. L'EHCVM 2021-2022 n'est pas disponible dans le dépôt.

## Fichiers dérivés

| Fichier | Contenu | Source |
|---|---|---|
| `processed/targets/nta_lcd_crossing_ages.json` | âges de bascule du déficit du cycle de vie (national, par sexe, par milieu) ; repère de contexte pour P1q, jamais `a*_obs` de P4 | CREFAT 2016, p. 3, 8, 13 |
| `processed/targets/ehcvm_morbidity_bound.json` | part de malades ou blessés sur 30 jours (23,5 %) ; borne de vraisemblance des épisodes simulés (J5) | EHCVM 2018/2019, Tableau VI-1, p. 58 |

## Limites à rappeler dans le mémoire

- Années différentes : NTA 2011, EHCVM 2018/2019 ; les montants EHCVM sont en FCFA de 2018/2019,
  non déflatés vers l'année de départ du modèle.
- Les paramètres directs EHCVM (J3) et la cible de validation P6 viennent de la même enquête :
  P6 n'est pas indépendante de la paramétrisation (RV-14).
- Le taux de pauvreté EHCVM porte sur la consommation par tête (J2), pas sur le reste-à-vivre.
- Agrégats seulement : aucune distribution, donc pas de test de Kolmogorov–Smirnov (P5, P6)
  sans les microdonnées.
- Absents des deux documents : dette, épargne, transferts, profils par âge simple.
- Incohérences internes relevées dans les deux documents : voir les inventaires.

## À obtenir (40 §4.4)

1. Microdonnées EHCVM 2018/2019 et 2021/2022 : catalogue ANADS de l'ANSD ou Microdata de la
   Banque mondiale (P5, P6, P7, distributions d'initialisation).
2. Profils NTA par âge simple et note méthodologique : CREFAT (P1–P4).
