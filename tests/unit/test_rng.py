"""Tests de RngStreams (01 §7, S4) : sous-flux nommés, stables et reproductibles."""

import numpy as np
import pytest

from family_abm.core.rng import RngStreams

N_DRAWS = 50


def _draws(rng: RngStreams, name: str) -> np.ndarray:
    return rng[name].random(N_DRAWS)


def test_same_seed_same_draws() -> None:
    for name in RngStreams.NAMES:
        assert np.array_equal(_draws(RngStreams(42), name), _draws(RngStreams(42), name))


def test_different_seeds_differ() -> None:
    assert not np.array_equal(
        _draws(RngStreams(42), "income_shocks"), _draws(RngStreams(43), "income_shocks")
    )


def test_streams_are_distinct() -> None:
    rng = RngStreams(42)
    series = [tuple(_draws(rng, name)) for name in RngStreams.NAMES]
    assert len(set(series)) == len(RngStreams.NAMES)


def test_same_name_returns_same_generator() -> None:
    rng = RngStreams(42)
    assert rng["health"] is rng["health"]


def test_draws_in_one_stream_do_not_shift_another() -> None:
    reference = _draws(RngStreams(42), "income_shocks")
    rng = RngStreams(42)
    rng["health"].random(1_000)
    assert np.array_equal(_draws(rng, "income_shocks"), reference)


def test_adding_a_stream_does_not_perturb_existing_ones(monkeypatch: pytest.MonkeyPatch) -> None:
    reference = {name: _draws(RngStreams(42), name) for name in RngStreams.NAMES}
    monkeypatch.setattr(RngStreams, "NAMES", ("a_new_stream", *RngStreams.NAMES))
    rng = RngStreams(42)
    rng["a_new_stream"].random(1_000)
    for name, expected in reference.items():
        assert np.array_equal(_draws(rng, name), expected)


def test_unknown_stream_is_refused() -> None:
    with pytest.raises(KeyError, match="unknown_stream"):
        RngStreams(42)["unknown_stream"]


def test_household_streams_reproducible_and_independent_of_population() -> None:
    root = RngStreams(42)
    alone = _draws(RngStreams(42).for_household(3), "health")
    # Dériver d'autres foyers avant (population plus grande) ne change rien.
    for index in range(10):
        root.for_household(index)["health"].random(5)
    assert np.array_equal(_draws(root.for_household(3), "health"), alone)


def test_household_streams_differ_between_households_and_from_root() -> None:
    root = RngStreams(42)
    h0 = _draws(root.for_household(0), "health")
    h1 = _draws(root.for_household(1), "health")
    assert not np.array_equal(h0, h1)
    assert not np.array_equal(h0, _draws(RngStreams(42), "health"))


@pytest.mark.parametrize("seed", [-1, True])
def test_invalid_seed_is_refused(seed: int) -> None:
    with pytest.raises(ValueError):
        RngStreams(seed)


def test_stream_keys_do_not_collide() -> None:
    import zlib

    keys = {zlib.crc32(name.encode("utf-8")) for name in RngStreams.NAMES}
    assert len(keys) == len(RngStreams.NAMES)
