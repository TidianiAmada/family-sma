"""Fixtures partagées. ``ScriptedEngine`` est la seconde implémentation de ``DecisionEngine``
(02 §1) : un moteur scripté, sans logique de décision, pour tester l'ordonnancement."""

from collections.abc import Callable, Mapping
from pathlib import Path

import numpy as np
import pytest

from family_abm.config.loader import load_config
from family_abm.config.schemas import CognitiveProfile, SimulationConfig
from family_abm.core.types import NeedKind, PersonId, Step
from family_abm.decision.engine import (
    DecisionTrace,
    Demand,
    DemandSet,
    EffectiveCognitiveProfile,
    Percept,
)

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"

type Script = Callable[[Percept], tuple[Demand, ...]]


class ScriptedEngine:
    """Rend les demandes produites par ``script`` (aucune par défaut) et journalise chaque appel."""

    def __init__(self, script: Script | None = None, labor_supply: float = 1.0) -> None:
        self.script = script
        self.labor_supply = labor_supply
        self.calls: list[tuple[Step, PersonId]] = []

    def decide(
        self,
        percept: Percept,
        profile: EffectiveCognitiveProfile,
        base: CognitiveProfile,
        aspiration: Mapping[NeedKind, float],
        rng: np.random.Generator,
    ) -> DemandSet:
        self.calls.append((percept.step, percept.person_id))
        demands = self.script(percept) if self.script is not None else ()
        trace = DecisionTrace(
            person_id=percept.person_id,
            step=percept.step,
            profile_effective=profile,
            aspiration=dict(aspiration),
            considered=(),
            chosen_id="scripted",
            rule="scripted",
        )
        return DemandSet(percept.person_id, demands, self.labor_supply, trace)


@pytest.fixture(scope="session")
def baseline_config() -> SimulationConfig:
    return load_config(CONFIG_DIR)


@pytest.fixture
def scripted_engine() -> ScriptedEngine:
    return ScriptedEngine()
