"""Exceptions du moteur (01 §2, 10 §1, 40 §6).

L'absence de plan applicable est un ÉVÉNEMENT, pas une exception. Une ``InvariantViolation``
arrête le run : elle n'est jamais convertie en avertissement.
"""

from family_abm.core.types import HouseholdId, Step


class FamilyAbmError(Exception):
    """Base de toutes les erreurs du moteur."""


class ConfigError(FamilyAbmError):
    """Configuration invalide (bornes, références inconnues, schéma)."""


class LedgerError(FamilyAbmError):
    """Écriture refusée par le ``Ledger`` (02 §8.2)."""


class AllocationError(FamilyAbmError):
    """Entrée incohérente pour ``allocate()``."""


class NotInV1Error(FamilyAbmError):
    """Fonctionnalité demandée qui n'existe pas dans la version de modèle active."""


class InvariantViolation(FamilyAbmError):  # noqa: N818 — nom normatif (01 §2)
    """Violation d'un invariant comptable ``INV-xx`` : arrêt dur du run."""

    def __init__(
        self, inv_id: str, step: Step, household_id: HouseholdId | None, detail: str
    ) -> None:
        self.inv_id = inv_id
        self.step = step
        self.household_id = household_id
        self.detail = detail
        super().__init__(f"{inv_id} au pas {step}, foyer {household_id} : {detail}")

    def __reduce__(self) -> tuple[type["InvariantViolation"], tuple[str, Step, str | None, str]]:
        # Picklable : l'erreur doit traverser les processus des campagnes parallèles.
        return (type(self), (self.inv_id, self.step, self.household_id, self.detail))


class CalibrationLeakError(FamilyAbmError, RuntimeError):
    """Un pattern dont le rôle n'est pas ``calibration`` entre dans la perte (40 §6)."""


class TreatmentCalibrationError(FamilyAbmError, RuntimeError):
    """Une variable de traitement d'une expérience figure parmi les paramètres libres (40 §6)."""
