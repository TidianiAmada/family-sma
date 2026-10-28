"""Tests de la configuration validée (03, 10 §16 ``unit/test_config.py``)."""

import math
import shutil
from pathlib import Path

import pydantic
import pytest

from family_abm.config.loader import (
    config_hash,
    is_illustrative,
    load_config,
    load_registry,
    read_raw_config,
)
from family_abm.config.schemas import Provenance, active_profile_fields
from family_abm.core.errors import ConfigError

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


@pytest.fixture
def config_copy(tmp_path: Path) -> Path:
    target = tmp_path / "config"
    shutil.copytree(CONFIG_DIR, target)
    return target


# --- chargement


def test_baseline_config_loads() -> None:
    config = load_config(CONFIG_DIR)
    assert config.model.version == "v1"
    assert len(config.household_rules.baseline_household.members) == 6
    assert set(config.profiles) == {
        "baby",
        "child",
        "adolescent",
        "young_adult",
        "mother",
        "father",
    }


def test_allocation_weights_normalized_at_load() -> None:
    weights = load_config(CONFIG_DIR).household_rules.allocation.weights
    assert math.isclose(math.fsum(weights.values()), 1.0, abs_tol=1e-12)
    assert weights["father"] == weights["mother"] > weights["baby"]


def test_file_level_provenance_applies_to_each_profile() -> None:
    config = load_config(CONFIG_DIR)
    assert all(p.provenance is Provenance.PLACEHOLDER for p in config.profiles.values())


def test_config_is_frozen() -> None:
    config = load_config(CONFIG_DIR)
    with pytest.raises(pydantic.ValidationError):
        config.horizon_months = 12  # type: ignore[misc]


def test_missing_file_is_refused(config_copy: Path) -> None:
    (config_copy / "needs.yaml").unlink()
    with pytest.raises(ConfigError, match="needs.yaml"):
        load_config(config_copy)


def test_simulation_root_key_named_after_another_file_is_refused(config_copy: Path) -> None:
    sim = config_copy / "simulation.yaml"
    sim.write_text(sim.read_text(encoding="utf-8") + "affect: {enabled: true}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="affect"):
        load_config(config_copy)


# --- bornes et références


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("economic_params.income_shocks.formal.p_loss_monthly", 1.5),
        ("profiles.adolescent.impulsivity", -0.1),
        ("profiles.baby.max_alternatives", 0),
        ("needs.food.persistence", 1.2),
        ("horizon_months", 0),
        ("economic_params.health.p_episode_monthly_by_age", [[0, 0.5], [5, 1.5]]),
        ("economic_params.consumption_requirements.food.by_age", [[5, 1], [0, 2]]),
        ("profiles.child.aspiration_adapt.min", 0.95),
    ],
)
def test_out_of_bounds_values_are_refused_with_path(path: str, value: object) -> None:
    with pytest.raises(ConfigError) as info:
        load_config(CONFIG_DIR, {path: value})
    assert path.split(".")[-1] in str(info.value)
    assert str(info.value).startswith("configuration invalide")


def test_unknown_profile_is_refused() -> None:
    with pytest.raises(ConfigError, match="profil inconnu 'grandpa'"):
        load_config(CONFIG_DIR, {"household_rules.baseline_household.members.0.profile": "grandpa"})


def test_unknown_profile_in_transition_is_refused() -> None:
    with pytest.raises(ConfigError, match="profil inconnu 'elder'"):
        load_config(CONFIG_DIR, {"household_rules.profile_transitions.0.to": "elder"})


def test_ownership_not_summing_to_one_is_refused() -> None:
    with pytest.raises(ConfigError, match="Σω"):
        load_config(CONFIG_DIR, {"household_rules.baseline_household.ownership.father": 0.6})


def test_ownership_of_unknown_member_is_refused() -> None:
    with pytest.raises(ConfigError, match="membres inconnus"):
        load_config(
            CONFIG_DIR,
            {"household_rules.baseline_household.ownership": {"father": 0.5, "uncle": 0.5}},
        )


def test_missing_member_weight_is_refused() -> None:
    weights = {"father": 1.0, "mother": 1.0}
    with pytest.raises(ConfigError, match="manquants"):
        load_config(CONFIG_DIR, {"household_rules.allocation.weights": weights})


def test_unknown_key_is_refused() -> None:
    with pytest.raises(ConfigError, match="wagez"):
        load_config(CONFIG_DIR, {"economic_params.wagez": 1})


def test_invariants_cannot_be_disabled() -> None:
    with pytest.raises(ConfigError, match="invariants"):
        load_config(CONFIG_DIR, {"checks.invariants": False})


def test_sampling_below_one_requires_gate_v1(config_copy: Path, tmp_path: Path) -> None:
    gates = tmp_path / "GATES.md"
    with pytest.raises(ConfigError, match="porte V1"):
        load_config(config_copy, {"checks.invariant_run_sample_rate": 0.5}, gates_path=gates)
    gates.write_text("# Portes\ngate_v1: passed\n", encoding="utf-8")
    config = load_config(config_copy, {"checks.invariant_run_sample_rate": 0.5}, gates_path=gates)
    assert config.checks.invariant_run_sample_rate == 0.5


# --- surcharges


def test_dotted_override_is_applied() -> None:
    config = load_config(CONFIG_DIR, {"economic_params.wages.father": 180000})
    assert config.economic_params.wages["father"] == 180000


def test_root_simulation_override_is_applied() -> None:
    assert load_config(CONFIG_DIR, {"model.version": "v2"}).model.version == "v2"


def test_wildcard_override_sets_absolute_value_on_all_profiles() -> None:
    config = load_config(CONFIG_DIR, {"profiles.*.impulsivity": 0.5})
    assert {p.impulsivity for p in config.profiles.values()} == {0.5}


def test_selection_override_touches_only_selected_profiles() -> None:
    config = load_config(CONFIG_DIR, {"profiles.{mother,father}.discounting.beta": 0.8})
    assert config.profiles["mother"].discounting.beta == 0.8
    assert config.profiles["father"].discounting.beta == 0.8
    assert config.profiles["adolescent"].discounting.beta == 0.7


def test_override_layers_apply_in_order() -> None:
    layers = [{"economic_params.wages.father": 1}, {"economic_params.wages.father": 2}]
    assert load_config(CONFIG_DIR, layers).economic_params.wages["father"] == 2


@pytest.mark.parametrize(
    "path",
    ["economic_params.nope.father", "unknown_namespace.x", "profiles.{mother,uncle}.impulsivity"],
)
def test_override_on_unknown_path_is_refused(path: str) -> None:
    with pytest.raises(ConfigError, match="chemin"):
        load_config(CONFIG_DIR, {path: 1})


def test_overrides_do_not_mutate_base_tree() -> None:
    before = read_raw_config(CONFIG_DIR)
    load_config(CONFIG_DIR, {"economic_params.wages.father": 1})
    assert read_raw_config(CONFIG_DIR) == before


# --- empreinte et provenance


def test_config_hash_is_stable() -> None:
    first, second = config_hash(load_config(CONFIG_DIR)), config_hash(load_config(CONFIG_DIR))
    assert first == second
    assert len(first) == 64 and int(first, 16) >= 0


def test_config_hash_changes_with_a_parameter() -> None:
    base = config_hash(load_config(CONFIG_DIR))
    assert config_hash(load_config(CONFIG_DIR, {"economic_params.wages.father": 1})) != base


def test_config_hash_ignores_the_seed() -> None:
    base = config_hash(load_config(CONFIG_DIR))
    assert config_hash(load_config(CONFIG_DIR, {"seed": 7})) == base


def test_placeholder_makes_config_illustrative() -> None:
    assert is_illustrative(load_config(CONFIG_DIR))


def test_config_without_placeholder_is_not_illustrative() -> None:
    direct = {
        "profiles.*.provenance": "DIRECT",
        "household_rules.provenance": "DIRECT",
        "economic_params.provenance": "DIRECT",
    }
    assert not is_illustrative(load_config(CONFIG_DIR, direct))


def test_a_single_nested_placeholder_makes_config_illustrative() -> None:
    overrides = {
        "profiles.*.provenance": "DIRECT",
        "household_rules.provenance": "DIRECT",
        "economic_params.provenance": "DIRECT",
        "economic_params.tax.provenance": "PLACEHOLDER",
    }
    assert is_illustrative(load_config(CONFIG_DIR, overrides))


# --- profils V2/V3


def test_v2_v3_profile_parameters_are_inactive_in_v1() -> None:
    v1 = active_profile_fields("v1")
    assert {
        "capabilities",
        "max_alternatives",
        "planning_horizon",
        "attended_needs",
        "aspiration_init",
        "impulsivity",
    } == v1
    assert {"aspiration_adapt", "memory", "intention_commitment", "discounting"} <= (
        active_profile_fields("v2") - v1
    )
    assert {"risk", "stress_sensitivity"} == active_profile_fields("v3") - active_profile_fields(
        "v2"
    )


def test_v2_v3_profile_parameters_are_read_and_validated_in_v1() -> None:
    config = load_config(CONFIG_DIR)
    assert config.model.version == "v1"
    assert config.profiles["father"].risk.lambda_ == 2.25
    with pytest.raises(ConfigError, match="capacity"):
        load_config(CONFIG_DIR, {"profiles.father.memory.capacity": -1})


# --- registre


def test_registry_loads_and_paths_resolve() -> None:
    config = load_config(CONFIG_DIR)
    registry = load_registry(CONFIG_DIR, config)
    assert any(p.path == "profiles.*.planning_horizon" for p in registry.parameters)


def test_registry_path_resolving_to_nothing_is_refused(config_copy: Path) -> None:
    registry = config_copy / "parameters_registry.yaml"
    registry.write_text(
        registry.read_text(encoding="utf-8")
        + "  - { path: profiles.*.typo, bounds: [0, 1], treatment: FIX, sa: true }\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="typo"):
        load_registry(config_copy, load_config(config_copy))


# --- non-régression (revue T-003)


def test_wildcard_skips_branches_without_the_rest_of_the_path() -> None:
    # household_rules.* contient des listes (profile_transitions) et des scalaires.
    config = load_config(CONFIG_DIR, {"household_rules.*.enabled": False})
    assert config.household_rules.separate_spheres.enabled is False


def test_wildcard_over_a_list() -> None:
    path = "household_rules.baseline_household.members.*.employment"
    config = load_config(CONFIG_DIR, {path: "inactive"})
    members = config.household_rules.baseline_household.members
    assert {m.employment.value for m in members} == {"inactive"}


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("profiles.father.memory.retrieval_threshold", float("nan")),
        ("economic_params.wages.father", float("inf")),
        ("horizon_months", True),
        ("seed", "7"),
    ],
)
def test_non_finite_and_coerced_values_are_refused(path: str, value: object) -> None:
    with pytest.raises(ConfigError):
        load_config(CONFIG_DIR, {path: value})


@pytest.mark.parametrize("layers", [["x"], [{1: 2}]])
def test_malformed_override_layers_are_refused(layers: list[object]) -> None:
    with pytest.raises(ConfigError, match="couche"):
        load_config(CONFIG_DIR, layers)  # type: ignore[arg-type]


def test_config_hash_ignores_output_dir_and_provenance() -> None:
    base = config_hash(load_config(CONFIG_DIR))
    assert config_hash(load_config(CONFIG_DIR, {"output.dir": "elsewhere"})) == base
    assert config_hash(load_config(CONFIG_DIR, {"economic_params.provenance": "DIRECT"})) == base


def test_config_hash_includes_data_source() -> None:
    base = config_hash(load_config(CONFIG_DIR))
    assert config_hash(load_config(CONFIG_DIR, {"data.source": "ehcvm"})) != base


# --- transitions de profil (revue T-006)


def test_cyclic_profile_transitions_are_refused() -> None:
    cycle = [
        {"from": "baby", "to": "child", "at_age": 5},
        {"from": "child", "to": "baby", "at_age": 5},
    ]
    with pytest.raises(ConfigError, match="cycle"):
        load_config(CONFIG_DIR, {"household_rules.profile_transitions": cycle})


def test_two_transitions_from_same_profile_are_refused() -> None:
    rules = [
        {"from": "baby", "to": "child", "at_age": 5},
        {"from": "baby", "to": "adolescent", "at_age": 6},
    ]
    with pytest.raises(ConfigError, match="plusieurs transitions"):
        load_config(CONFIG_DIR, {"household_rules.profile_transitions": rules})


def test_member_older_than_its_profile_transition_is_refused() -> None:
    with pytest.raises(ConfigError, match="cède la place"):
        load_config(CONFIG_DIR, {"household_rules.baseline_household.members.3.age": 19})


@pytest.mark.parametrize(
    "path", ["economic_params.default_wage_key", "household_rules.default_pooling_key"]
)
def test_default_keys_must_exist(path: str) -> None:
    with pytest.raises(ConfigError, match="absente"):
        load_config(CONFIG_DIR, {path: "nobody"})
