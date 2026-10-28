---
description: Comparer le code et l'ODD de la version courante
---
Lis `config/simulation.yaml` (`model.version`), puis l'ODD correspondant dans `odd/`.

Pour chaque sous-modèle de l'ODD : localise le code, compare équations, paramètres, ordre d'exécution et variables d'état. Pour chaque variable d'état et chaque paramètre du code : vérifie qu'il figure dans l'ODD.

Produis un tableau : élément · ODD dit · code fait · écart (aucun / mineur / majeur) · correction proposée (dans l'ODD ou dans le code). Ne corrige rien sans l'accord de l'auteur : l'ODD devient le texte du mémoire.
