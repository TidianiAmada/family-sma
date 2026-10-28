"""Machine à états de la scolarité (T-008, 10 §6, 02 §10.4)."""

import pytest

from family_abm.config.schemas import SchoolingParams, SimulationConfig
from family_abm.core.types import SchoolStatus
from family_abm.economy.actions import school_status_after_fees, school_status_by_age

NOT_SCHOOL_AGE = SchoolStatus.NOT_SCHOOL_AGE
ENROLLED = SchoolStatus.ENROLLED
DROPPED_OUT = SchoolStatus.DROPPED_OUT
COMPLETED = SchoolStatus.COMPLETED


@pytest.fixture(scope="module")
def schooling(baseline_config: SimulationConfig) -> SchoolingParams:
    return baseline_config.economic_params.schooling


def test_enrolment_at_entry_age(schooling: SchoolingParams) -> None:
    entry = schooling.entry_age
    assert school_status_by_age(NOT_SCHOOL_AGE, entry - 1 / 12, schooling) is NOT_SCHOOL_AGE
    assert school_status_by_age(NOT_SCHOOL_AGE, entry, schooling) is ENROLLED


def test_completion_at_tertiary_exit_age(schooling: SchoolingParams) -> None:
    secondary, tertiary = schooling.exit_age.secondary, schooling.exit_age.tertiary
    assert school_status_by_age(ENROLLED, secondary, schooling) is ENROLLED  # poursuite (V1)
    assert school_status_by_age(ENROLLED, tertiary - 1 / 12, schooling) is ENROLLED
    assert school_status_by_age(ENROLLED, tertiary, schooling) is COMPLETED


def test_dropped_out_and_completed_are_absorbing_in_v1(schooling: SchoolingParams) -> None:
    for status in (DROPPED_OUT, COMPLETED):
        assert school_status_by_age(status, 10, schooling) is status
        assert school_status_after_fees(status, 0, paid=False, schooling=schooling) == (status, 0)


def test_dropout_after_consecutive_refusals(schooling: SchoolingParams) -> None:
    m_drop = schooling.drop_after_refused_months
    status, refused = ENROLLED, 0
    for month in range(1, m_drop):
        status, refused = school_status_after_fees(status, refused, paid=False, schooling=schooling)
        assert (status, refused) == (ENROLLED, month)
    status, refused = school_status_after_fees(status, refused, paid=False, schooling=schooling)
    assert (status, refused) == (DROPPED_OUT, m_drop)


def test_paid_fees_reset_the_counter(schooling: SchoolingParams) -> None:
    status, refused = school_status_after_fees(ENROLLED, 2, paid=True, schooling=schooling)
    assert (status, refused) == (ENROLLED, 0)
