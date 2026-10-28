"""Flux aléatoires nommés (01 §7, S4).

Un ``SeedSequence`` racine engendre un générateur par usage. La clé d'un flux dérive de son
NOM (CRC-32), pas de sa position dans ``NAMES`` : ajouter un flux ou tirer dans un flux ne
décale jamais les autres. Chaque foyer reçoit ses propres flux, dérivés de
``(seed, household_index)`` comme ``SeedSequence(seed).spawn`` : un foyer donne la même
trajectoire qu'il soit simulé seul ou dans une population.
"""

import zlib

import numpy as np


class RngStreams:
    """Un ``SeedSequence`` racine → sous-générateurs nommés, stables."""

    NAMES: tuple[str, ...] = (
        "scheduling",
        "income_shocks",
        "employment",
        "health",
        "prices",
        "memory_noise",
        "population",
        "decision_ties",
        "tontine",  # mois de la cagnotte tiré (V3, 30 §7)
    )

    def __init__(self, seed: int) -> None:
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError(f"graine invalide (entier ≥ 0 attendu) : {seed!r}")
        self.seed = seed
        self._spawn_key: tuple[int, ...] = ()
        self._generators: dict[str, np.random.Generator] = {}

    def __getitem__(self, name: str) -> np.random.Generator:
        generator = self._generators.get(name)
        if generator is None:
            if name not in self.NAMES:
                raise KeyError(f"flux aléatoire inconnu : {name!r} (déclarés : {self.NAMES})")
            sequence = np.random.SeedSequence(
                self.seed, spawn_key=(*self._spawn_key, zlib.crc32(name.encode("utf-8")))
            )
            generator = np.random.default_rng(sequence)
            self._generators[name] = generator
        return generator

    def for_household(self, household_index: int) -> "RngStreams":
        """Flux propres au foyer ``household_index`` (équivalent à ``spawn`` indexé)."""
        return self._child(household_index)

    def for_member(self, member_index: int) -> "RngStreams":
        """Flux propres au membre ``member_index`` d'un foyer : un tirage d'une personne ne
        dépend pas de l'ordre de passage des autres au Temps 1 (01 §4, point 2)."""
        return self._child(member_index)

    def _child(self, index: int) -> "RngStreams":
        if index < 0:
            raise ValueError(f"indice de sous-flux négatif : {index}")
        child = RngStreams(self.seed)
        child._spawn_key = (*self._spawn_key, index)
        return child
