"""Les trois temps d'un pas mensuel, explicitement nommés (01 §4, ODD-V1 §3).

Ordre normatif d'un pas : 0. événements → Temps 1 (perception et demande, personnes en
ordre aléatoire seedé) → Temps 2 (arbitrage du foyer, une fois par pas) → Temps 3 (action)
→ mesure (NTA, invariants, collecte) → vieillissement et transitions de profil, **après**
la collecte (G1). Ce module porte chaque temps ; ``FamilyModel.step`` les enchaîne.
"""

from enum import StrEnum

from family_abm.agents.household import HouseholdAgent, MemberEvent
from family_abm.agents.person import PersonAgent
from family_abm.config.schemas import Needs, ProfileTransition
from family_abm.core.types import MONTHS_PER_YEAR, NeedKind, Step
from family_abm.economy.accounts import AccountKind
from family_abm.model.events import ModelEvent


class Phase(StrEnum):
    EVENTS = "events"  # 0. chocs exogènes du scénario
    TIME1 = "time1"  # perception et demande
    TIME2 = "time2"  # arbitrage du foyer
    TIME3 = "time3"  # action
    MEASURE = "measure"  # NTA, invariants, collecte
    AGE = "age"  # vieillissement et transitions de profil


def active_needs(needs: Needs, age_years: float) -> frozenset[NeedKind]:
    """Besoins actifs à cet âge : ``active_ages = [min, max[`` (03 §5, ODD-V1 §7.1)."""
    return frozenset(
        kind
        for kind in NeedKind
        if getattr(needs, kind.value).active_ages[0]
        <= age_years
        < getattr(needs, kind.value).active_ages[1]
    )


def _logged(household: HouseholdAgent, step: Step, events: list[MemberEvent]) -> list[ModelEvent]:
    return [
        ModelEvent(
            step=step,
            type=event.type,
            household_id=household.household_id,
            person_id=event.person_id,
            detail=event.detail,
        )
        for event in events
    ]


def time1(household: HouseholdAgent, step: Step) -> list[ModelEvent]:
    """Temps 1 : santé et scolarité du mois, puis chaque membre perçoit et décide ; les
    demandes sont soumises au foyer.

    L'ordre des personnes est tiré dans ``streams["scheduling"]`` ; il est sans effet sur le
    résultat : les demandes sont arbitrées simultanément au Temps 2 et chaque personne tire
    dans ses propres flux (01 §4, point 2).
    """
    household.start_step()
    events = household.start_of_month(step)
    savings = household.ledger.balance(household.account(AccountKind.HOUSEHOLD_SAVINGS))
    target = household.savings_target()
    members = household.members
    for position in household.streams["scheduling"].permutation(len(members)):
        person = members[int(position)]
        person.econ.spent_by_need = {}
        percept = person.perceive(
            step,
            ownership_share=household.state.ownership.get(person.person_id, 0.0),
            requirements=household.requirements(person, step),
            savings=savings,
            savings_target=target,
        )
        household.submit(person.decide(percept))
    return _logged(household, step, events)


def time2(household: HouseholdAgent, step: Step) -> list[ModelEvent]:
    """Temps 2 : arbitrage du foyer (revenus, mise en commun, engagements, allocation)."""
    return _logged(household, step, household.run_time2(step))


def time3(household: HouseholdAgent, step: Step) -> None:
    """Temps 3 : chaque membre exécute ses allocations."""
    for person in household.members:
        person.act(household.allocations.get(person.person_id, ()))


def age(
    household: HouseholdAgent,
    step: Step,
    transitions: tuple[ProfileTransition, ...],
    needs: Needs,
) -> list[ModelEvent]:
    """Vieillissement d'un mois et transitions de profil (10 §2), après la collecte.

    Une règle ``from → to`` s'applique quand ``age_months`` franchit ``at_age × 12`` et que
    ``from`` est le profil courant ; l'aspiration est réinitialisée à celle du nouveau
    profil (10 §20.14) et les besoins actifs sont recalculés. Le rôle ne change jamais.
    """
    events: list[ModelEvent] = []
    for person in household.members:
        before = person.age_months
        person.age_months += 1
        changed = True
        while changed:  # plusieurs seuils franchis au même pas s'enchaînent
            changed = False
            for rule in transitions:
                threshold = rule.at_age * MONTHS_PER_YEAR
                if rule.from_ == person.profile_key and before < threshold <= person.age_months:
                    person.profile_key = rule.to
                    aspiration = person.profile.aspiration_init
                    person.cog.aspiration = {kind: aspiration for kind in NeedKind}
                    events.append(
                        ModelEvent(
                            step=step,
                            type="profile_transition",
                            household_id=household.household_id,
                            person_id=person.person_id,
                            detail={"from": rule.from_, "to": rule.to},
                        )
                    )
                    changed = True
        _activate_needs(household, person, active_needs(needs, person.age_years))
    return events


def _activate_needs(
    household: HouseholdAgent, person: PersonAgent, active: frozenset[NeedKind]
) -> None:
    """Besoins actifs recalculés ; un besoin qui devient actif part du niveau initial de
    10 §4 : 1, sauf SECURITY, qui prend la valeur commune du foyer."""
    for kind in active - person.needs.active:
        level = household.security_level() if kind is NeedKind.SECURITY else None
        person.needs.level[kind] = 1.0 if level is None else level
    person.needs.active = active
