"""Repères extraits des sources (data/processed/targets) : cohérence et traçabilité."""

import json
from pathlib import Path

TARGETS = Path(__file__).resolve().parents[2] / "data" / "processed" / "targets"


def test_nta_crossing_ages_are_consistent_and_sourced() -> None:
    data = json.loads((TARGETS / "nta_lcd_crossing_ages.json").read_text(encoding="utf-8"))
    national = data["national"]
    young_end, surplus_start = national["deficit_young"][1], national["surplus"][0]
    surplus_end, old_start = national["surplus"][1], national["deficit_old_from"]
    # Deux passages par zéro (forme en U du LCD, critère P1q) et tranches contiguës.
    assert surplus_start == young_end + 1 and old_start == surplus_end + 1
    assert data["data_year"] == 2011 and "CREFAT" in data["source"]
    assert all("page" in data[key] for key in ("national", "by_sex", "by_area"))


def test_morbidity_bound_is_a_share_and_sourced() -> None:
    data = json.loads((TARGETS / "ehcvm_morbidity_bound.json").read_text(encoding="utf-8"))
    assert 0 < data["share_ill_or_injured_last_30_days"] < 1
    assert "p. 58" in data["source"]


def test_morbidity_bound_is_above_configured_episode_probabilities() -> None:
    from family_abm.config.loader import load_config

    config = load_config(Path(__file__).resolve().parents[2] / "config")
    bound = json.loads((TARGETS / "ehcvm_morbidity_bound.json").read_text(encoding="utf-8"))
    probabilities = [p for _, p in config.economic_params.health.p_episode_monthly_by_age]
    assert max(probabilities) <= bound["share_ill_or_injured_last_30_days"]
