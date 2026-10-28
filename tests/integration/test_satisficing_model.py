"""Le modèle tourne avec ``SatisficingEngine`` (T-009)."""

from collections import Counter

from family_abm.config.schemas import SimulationConfig
from family_abm.decision.engine import DemandSet
from family_abm.decision.satisficing import SatisficingEngine
from family_abm.model.family_model import FamilyModel


def _run(config: SimulationConfig, steps: int) -> tuple[FamilyModel, list[DemandSet]]:
    model = FamilyModel(config, SatisficingEngine(config.needs))
    collected: list[DemandSet] = []
    for _ in range(steps):
        model.step()
        collected.extend(model.households[0].demand_sets.values())
    return model, collected


def test_240_steps_with_satisficing_engine(baseline_config: SimulationConfig) -> None:
    model, demand_sets = _run(baseline_config, 240)
    assert model.step_index == 240
    assert len(demand_sets) == 240 * 6
    profiles = baseline_config.profiles
    for demand_set in demand_sets:
        person = model.households[0].member(demand_set.person_id)
        trace = demand_set.trace
        assert 1 <= len(trace.considered) <= profiles[person.profile_key].max_alternatives
        assert trace.rule in {"reactive", "first_acceptable", "fallback_top_need"}
        ids = [d.demand_id for d in demand_set.demands]
        assert len(ids) == len(set(ids))
        assert all(d.amount_requested >= d.amount_min for d in demand_set.demands)


def test_baby_decides_reactively(baseline_config: SimulationConfig) -> None:
    _, demand_sets = _run(baseline_config, 12)
    rules = Counter(d.trace.rule for d in demand_sets if d.person_id == "h0000-p5")
    assert set(rules) == {"reactive"}


def test_savings_target_is_fixed_at_step_zero(baseline_config: SimulationConfig) -> None:
    model = FamilyModel(baseline_config, SatisficingEngine(baseline_config.needs))
    household = model.households[0]
    initial = household.savings_target()
    for _ in range(120):
        model.step()
    assert household.savings_target() == initial


def test_same_seed_same_decisions(baseline_config: SimulationConfig) -> None:
    first = _run(baseline_config, 24)[1]
    second = _run(baseline_config, 24)[1]
    assert first == second
