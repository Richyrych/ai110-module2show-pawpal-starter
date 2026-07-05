"""Simple tests for the PawPal+ system.

Run with:  python3 -m pytest tests/test_pawpal.py
       or:  python3 tests/test_pawpal.py
"""

import os
import sys
from datetime import date, datetime, time, timedelta

import pytest

# pawpal_system.py lives in the parent directory of this tests/ folder.
STARTER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STARTER_DIR)

from pawpal_system import (  # noqa: E402
    Activity,
    Owner,
    Pet,
    Recurrence,
    Repeat,
    ScheduleConflict,
    Status,
)

TODAY = date.today()


def at(hour, minute=0):
    """Build a datetime for TODAY at the given time-of-day."""
    return datetime.combine(TODAY, time(hour, minute))


def make_owner_with_pet():
    """Return (owner, pet) with one pet already added."""
    owner = Owner(name="Alex")
    rex = Pet(name="Rex", owned_by=owner, breed="Labrador", sex="M")
    owner.add_pet(rex)
    return owner, rex


def test_activity_completion():
    """mark_complete() should flip the activity's status to completed."""
    activity = Activity("Morning walk", 30, "high", at(7, 0))
    assert activity.completed is False
    assert activity.status is Status.SCHEDULED

    activity.mark_complete()

    assert activity.completed is True
    assert activity.status is Status.COMPLETED


def test_activity_end_derived_from_duration():
    """end should be start + duration_minutes."""
    activity = Activity("Morning walk", 30, "high", at(7, 0))
    assert activity.end == at(7, 30)


def test_activity_addition():
    """Scheduling an activity should surface it on the pet and calendar."""
    owner, rex = make_owner_with_pet()

    assert len(rex.activities) == 0

    owner.schedule_activity(rex, Activity("Morning walk", 30, "high", at(7, 0)))

    assert len(rex.activities) == 1
    assert rex.activities[0].pet is rex


def test_conflict_is_rejected():
    """Scheduling an overlapping activity raises ScheduleConflict."""
    owner, rex = make_owner_with_pet()
    owner.schedule_activity(rex, Activity("Morning walk", 30, "high", at(7, 0)))

    # 07:15 starts before the 07:00-07:30 walk ends -> overlap.
    with pytest.raises(ScheduleConflict):
        owner.schedule_activity(rex, Activity("Vet call", 20, "high", at(7, 15)))


def test_rejected_conflict_leaves_schedule_unchanged():
    """A rejected conflict must not partially add the activity or crash."""
    owner, rex = make_owner_with_pet()
    owner.schedule_activity(rex, Activity("Vet checkup", 30, "high", at(15, 0)))

    clash = Activity("Nail trim", 20, "low", at(15, 15))
    with pytest.raises(ScheduleConflict):
        owner.schedule_activity(rex, clash)

    # The clashing activity is absent and the original schedule is intact.
    assert clash not in owner.calendar.pet_activity
    assert len(owner.activities()) == 1


def test_touching_intervals_do_not_conflict():
    """An activity starting exactly when another ends is allowed."""
    owner, rex = make_owner_with_pet()
    owner.schedule_activity(rex, Activity("Morning walk", 30, "high", at(7, 0)))

    # 07:30 starts exactly when the walk ends -> no overlap.
    owner.schedule_activity(rex, Activity("Breakfast", 15, "high", at(7, 30)))
    assert len(rex.activities) == 2


def test_conflicts_are_owner_level_across_pets():
    """Two different pets overlapping still conflicts (one owner, one body)."""
    owner, rex = make_owner_with_pet()
    mia = Pet(name="Mia", owned_by=owner, breed="Beagle", sex="F")
    owner.add_pet(mia)

    owner.schedule_activity(rex, Activity("Walk Rex", 30, "high", at(9, 0)))
    with pytest.raises(ScheduleConflict):
        owner.schedule_activity(mia, Activity("Walk Mia", 30, "high", at(9, 10)))


def test_find_conflicts_reports_overlapping_pairs():
    """find_conflicts detects overlaps that adjacent-only checks would miss."""
    owner, rex = make_owner_with_pet()
    # Add a long activity, then two short ones inside it via the calendar
    # directly (bypassing prevention) to exercise the detector.
    long = Activity("Long play", 120, "medium", at(10, 0))  # 10:00-12:00
    short = Activity("Snack", 10, "low", at(11, 0))          # 11:00-11:10
    long.pet = rex
    short.pet = rex
    owner.calendar.pet_activity.extend([long, short])

    conflicts = owner.find_conflicts()
    pairs = {frozenset((a.title, b.title)) for a, b in conflicts}
    assert frozenset(("Long play", "Snack")) in pairs


def test_activities_query_filters_and_sorts():
    """owner.activities filters by pet/status and returns sorted-by-time."""
    owner, rex = make_owner_with_pet()
    mia = Pet(name="Mia", owned_by=owner, breed="Beagle", sex="F")
    owner.add_pet(mia)

    owner.schedule_activity(rex, Activity("Evening", 30, "medium", at(18, 0)))
    owner.schedule_activity(rex, Activity("Morning", 30, "high", at(7, 0)))
    owner.schedule_activity(mia, Activity("Noon", 15, "high", at(12, 0)))

    # Sorted chronologically across all pets.
    titles = [a.title for a in owner.activities()]
    assert titles == ["Morning", "Noon", "Evening"]

    # Filter by pet.
    assert [a.title for a in owner.activities(pet=rex)] == ["Morning", "Evening"]

    # Filter by status.
    rex.activities[0].mark_complete()
    done = owner.activities(status=Status.COMPLETED)
    assert len(done) == 1


def test_recurrence_daily_count():
    """A daily count=3 rule yields three occurrences on consecutive days."""
    rule = Recurrence(frequency="daily", count=3)
    starts = list(rule.occurrences(at(9, 0)))
    assert starts == [at(9, 0), at(9, 0) + timedelta(days=1), at(9, 0) + timedelta(days=2)]


def test_recurrence_weekly_selected_days():
    """A weekly rule restricted to two weekdays only emits those days."""
    # Find the Monday of this week so the test is calendar-agnostic.
    monday = datetime.combine(TODAY - timedelta(days=TODAY.weekday()), time(8, 0))
    rule = Recurrence(frequency="weekly", weekdays=[0, 2], count=4)  # Mon & Wed
    starts = list(rule.occurrences(monday))
    weekdays = [s.weekday() for s in starts]
    assert weekdays == [0, 2, 0, 2]  # Mon, Wed, next Mon, next Wed


def test_recurrence_requires_bound():
    """An unbounded recurrence is rejected rather than looping forever."""
    with pytest.raises(ValueError):
        list(Recurrence(frequency="daily").occurrences(at(9, 0)))


def test_schedule_recurring_skips_conflicts():
    """Occurrences that clash are skipped, not aborted."""
    owner, rex = make_owner_with_pet()
    # Pre-book today at 09:00 so the first occurrence of the series clashes.
    owner.schedule_activity(rex, Activity("Blocker", 30, "high", at(9, 0)))

    scheduled, skipped = owner.schedule_recurring(
        rex, Activity("Meds", 10, "high", at(9, 0)),
        Recurrence(frequency="daily", count=3),
    )
    assert len(scheduled) == 2  # today skipped, tomorrow + day-after booked
    assert len(skipped) == 1
    assert all(a.series_id == scheduled[0].series_id for a in scheduled)


def test_auto_schedule_slides_around_conflict():
    """A clashing activity is moved to the first free slot that fits."""
    owner, rex = make_owner_with_pet()
    owner.schedule_activity(rex, Activity("Morning walk", 30, "high", at(7, 0)))

    groom = owner.auto_schedule(rex, Activity("Grooming", 30, "medium", at(7, 15)))
    # Walk occupies 07:00-07:30, so grooming lands at 07:30.
    assert groom.start == at(7, 30)


def test_auto_schedule_priority_bumps_lower():
    """A higher-priority task keeps its slot; the lower one is bumped later."""
    owner, rex = make_owner_with_pet()
    walk = Activity("Walk", 30, "low", at(13, 0))
    owner.schedule_activity(rex, walk)

    urgent = owner.auto_schedule(
        rex, Activity("Urgent meds", 30, "high", at(13, 0)),
        resolve_by_priority=True,
    )
    assert urgent.start == at(13, 0)          # winner kept its slot
    assert walk.start == at(13, 30)           # loser bumped to after the winner


def test_find_free_slot_respects_latest():
    """find_free_slot returns None when nothing fits before the deadline."""
    owner, rex = make_owner_with_pet()
    owner.schedule_activity(rex, Activity("Busy", 60, "high", at(9, 0)))  # 09:00-10:00
    # Only 09:00-09:45 window requested, but it's fully booked -> None.
    assert owner.calendar.find_free_slot(30, at(9, 0), latest=at(9, 45)) is None


def test_complete_daily_spawns_next_tomorrow():
    """Completing a DAILY task creates the next instance at today + 1 day."""
    owner, rex = make_owner_with_pet()
    task = Activity("Vitamins", 10, "high", at(10, 0), repeat=Repeat.DAILY)
    owner.schedule_activity(rex, task)

    nxt = owner.complete_activity(task)

    assert task.completed
    assert nxt is not None
    assert nxt.start.date() == date.today() + timedelta(days=1)
    assert nxt.start.time() == time(10, 0)      # same time-of-day
    assert nxt.repeat is Repeat.DAILY           # keeps rolling
    assert nxt.status is Status.SCHEDULED
    assert nxt in rex.activities


def test_complete_weekly_spawns_next_in_seven_days():
    """Completing a WEEKLY task creates the next instance at today + 7 days."""
    owner, rex = make_owner_with_pet()
    task = Activity("Bath", 20, "medium", at(16, 0), repeat=Repeat.WEEKLY)
    owner.schedule_activity(rex, task)

    nxt = owner.complete_activity(task)

    assert nxt is not None
    assert nxt.start.date() == date.today() + timedelta(days=7)


def test_complete_one_off_spawns_nothing():
    """A non-recurring task just completes; nothing new is created."""
    owner, rex = make_owner_with_pet()
    task = Activity("Vet visit", 30, "high", at(11, 0))
    owner.schedule_activity(rex, task)

    assert owner.complete_activity(task) is None
    assert len(rex.activities) == 1


def test_completing_twice_does_not_double_spawn():
    """Re-completing an already-complete task must not spawn another instance."""
    owner, rex = make_owner_with_pet()
    task = Activity("Vitamins", 10, "high", at(10, 0), repeat=Repeat.DAILY)
    owner.schedule_activity(rex, task)

    owner.complete_activity(task)
    before = len(owner.activities())
    assert owner.complete_activity(task) is None   # already completed
    assert len(owner.activities()) == before


def test_next_instance_delegates_through_pet():
    """pet.complete_activity routes through the owner and spawns the next."""
    owner, rex = make_owner_with_pet()
    task = Activity("Walkies", 15, "high", at(10, 0), repeat=Repeat.DAILY)
    owner.schedule_activity(rex, task)

    nxt = rex.complete_activity(task)
    assert nxt is not None
    assert nxt.start.date() == date.today() + timedelta(days=1)


if __name__ == "__main__":
    import pytest as _pytest

    raise SystemExit(_pytest.main([__file__, "-v"]))
