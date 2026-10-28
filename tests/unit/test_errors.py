"""Tests des exceptions du noyau (01 §2, 10 §1, 40 §6)."""

import pytest

from family_abm.core.errors import (
    AllocationError,
    CalibrationLeakError,
    ConfigError,
    FamilyAbmError,
    InvariantViolation,
    LedgerError,
    NotInV1Error,
    TreatmentCalibrationError,
)


def test_invariant_violation_carries_context() -> None:
    err = InvariantViolation("INV-01", step=47, household_id="h0001", detail="résidu 3.00")
    assert (err.inv_id, err.step, err.household_id, err.detail) == (
        "INV-01",
        47,
        "h0001",
        "résidu 3.00",
    )
    assert "INV-01" in str(err) and "47" in str(err) and "h0001" in str(err)


@pytest.mark.parametrize(
    "cls",
    [
        ConfigError,
        LedgerError,
        AllocationError,
        NotInV1Error,
        InvariantViolation,
        CalibrationLeakError,
        TreatmentCalibrationError,
    ],
)
def test_all_errors_share_base(cls: type[Exception]) -> None:
    assert issubclass(cls, FamilyAbmError)


def test_calibration_guards_are_runtime_errors() -> None:
    assert issubclass(CalibrationLeakError, RuntimeError)
    assert issubclass(TreatmentCalibrationError, RuntimeError)


def test_invariant_violation_is_not_a_warning() -> None:
    assert not issubclass(InvariantViolation, Warning)


def test_invariant_violation_survives_pickle() -> None:
    import pickle

    err = InvariantViolation("INV-01", step=3, household_id="h0001", detail="x")
    clone = pickle.loads(pickle.dumps(err))
    assert (clone.inv_id, clone.step, clone.household_id, clone.detail) == (
        "INV-01",
        3,
        "h0001",
        "x",
    )
    assert str(clone) == str(err)
