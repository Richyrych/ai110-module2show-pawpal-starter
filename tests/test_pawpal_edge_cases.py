"""Edge-case tests for the PawPal+ system.

These complement the happy-path suite in ``test_pawpal.py`` and target the
boundary conditions where a pet scheduler with sorting + recurrence tends to
break: interval math, status semantics, degenerate inputs, and the rolling
"complete spawns next" flow.

Run with:  python3 -m pytest tests/test_pawpal_edge_cases.py -v
"""

import os
import sys
from datetime import date, datetime, time, timedelta

import pytest

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


def at(hour, minute=0, day_offset=0):
    """Build a datetime for TODAY (+offset days) at the given time-of-day."""
    return datetime.combine(TODAY + timedelta(days=day_offset), time(hour, minute))


def make_owner_with_pet():
    """Return (owner, pet) with one pet already added."""
    owner = Owner(name="Alex")
    rex = Pet(name="Rex", owned_by=owner, breed="Labrador", sex="M")
    owner.add_pet(rex)
    return owner, rex


def book(owner, pet, activity):
    """Force an activity onto the calendar, bypassing conflict rejection.

    Used to construct overlapping/degenerate states the normal API forbids so
    the detectors can be exercised directly.
    """
    activity.pet = pet
    owner.calendar.pet_activity.append(activity)
    return activity


# ---------------------------------------------------------------------------
# Interval / overlap boundary conditions
# ---------------------------------------------------------------------------

def test_full_containment_is_a_conflict():
    """A short task entirely inside a long one must be rejected."""
    owner, rex = make_owner_with_pet()
    owner.schedule_activity(rex, Activity("Long play", 120, "medium", at(10, 0)))
    with pytest.raises(ScheduleConflict):
        owner.schedule_activity(rex, Activity("Snack", 10, "low", at(11, 0)))


def test_identical_interval_is_a_conflict():
    """An exact duplicate time range conflicts."""
    owner, rex = make_owner_with_pet()
    owner.schedule_activity(rex, Activity("Walk", 30, "high", at(8, 0)))
    with pytest.raises(ScheduleConflict):
        owner.schedule_activity(rex, Activity("Walk again", 30, "high", at(8, 0)))


def test_one_minute_overlap_is_a_conflict():
    """The smallest possible overlap (1 minute) still conflicts."""
    owner, rex = make_owner_with_pet()
    owner.schedule_activity(rex, Activity("A", 30, "high", at(8, 0)))  # 08:00-08:30
    with pytest.raises(ScheduleConflict):
        owner.schedule_activity(rex, Activity("B", 30, "high", at(8, 29)))  # 08:29-


def test_touching_backwards_is_allowed():
    """Booking a task that ends exactly when an existing one starts is fine."""
    owner, rex = make_owner_with_pet()
    owner.schedule_activity(rex, Activity("Second", 30, "high", at(8, 30)))
    # 08:00-08:30 ends exactly when the 08:30 task starts -> no overlap.
    owner.schedule_activity(rex, Activity("First", 30, "high", at(8, 0)))
    assert len(rex.activities) == 2


def test_zero_duration_point_inside_interval_conflicts():
    """A zero-minute marker strictly inside a booked interval DOES conflict.

    The backend Activity allows duration 0 (the UI floors it at 1). With the
    half-open overlap test, a point at 11:00 sits inside 10:00-12:00 and is
    treated as busy time, so it is rejected.
    """
    owner, rex = make_owner_with_pet()
    owner.schedule_activity(rex, Activity("Long", 120, "high", at(10, 0)))
    with pytest.raises(ScheduleConflict):
        owner.schedule_activity(rex, Activity("Marker", 0, "low", at(11, 0)))


def test_zero_duration_point_on_boundary_is_allowed():
    """A zero-minute marker at the exact end boundary does not conflict.

    A point at 12:00 (== the interval's end) is excluded by the half-open test.
    """
    owner, rex = make_owner_with_pet()
    owner.schedule_activity(rex, Activity("Long", 120, "high", at(10, 0)))  # ends 12:00
    owner.schedule_activity(rex, Activity("Marker", 0, "low", at(12, 0)))
    assert len(rex.activities) == 2


# ---------------------------------------------------------------------------
# Status semantics: what still occupies time
# ---------------------------------------------------------------------------

def test_cancelled_activity_frees_its_slot():
    """A cancelled activity no longer blocks its time range."""
    owner, rex = make_owner_with_pet()
    walk = Activity("Walk", 30, "high", at(9, 0))
    owner.schedule_activity(rex, walk)
    walk.cancel()
    # Same slot is now free to rebook.
    owner.schedule_activity(rex, Activity("Vet", 30, "high", at(9, 0)))
    assert len(owner.activities()) == 2


def test_cancelled_activity_not_in_find_conflicts():
    """Cancelled activities drop out of conflict detection."""
    owner, rex = make_owner_with_pet()
    a = book(owner, rex, Activity("A", 60, "high", at(9, 0)))
    book(owner, rex, Activity("B", 60, "high", at(9, 30)))  # overlaps A
    a.cancel()
    assert owner.find_conflicts() == []


def test_completed_activity_still_blocks_slot():
    """Documents current behaviour: a COMPLETED task still occupies its time.

    Only CANCELLED frees a slot; a finished task is still 'busy' as far as the
    calendar is concerned.
    """
    owner, rex = make_owner_with_pet()
    walk = Activity("Walk", 30, "high", at(9, 0))
    owner.schedule_activity(rex, walk)
    walk.mark_complete()
    with pytest.raises(ScheduleConflict):
        owner.schedule_activity(rex, Activity("Vet", 30, "high", at(9, 0)))


# ---------------------------------------------------------------------------
# Sorting / degenerate collections
# ---------------------------------------------------------------------------

def test_empty_schedule_queries_are_safe():
    """All query methods behave on an empty calendar."""
    owner, _ = make_owner_with_pet()
    assert owner.activities() == []
    assert owner.find_conflicts() == []
    # An open-ended free-slot search on an empty calendar returns the earliest.
    assert owner.calendar.find_free_slot(30, at(9, 0)) == at(9, 0)


def test_sorting_is_chronological_regardless_of_insert_order():
    """activities() returns start-ascending even for reverse-inserted data."""
    owner, rex = make_owner_with_pet()
    for hour in (20, 6, 13, 9):
        owner.schedule_activity(rex, Activity(f"T{hour}", 30, "low", at(hour, 0)))
    hours = [a.start.hour for a in owner.activities()]
    assert hours == sorted(hours)


def test_multi_day_sorting_spans_dates():
    """Sorting orders by full datetime, not just time-of-day."""
    owner, rex = make_owner_with_pet()
    owner.schedule_activity(rex, Activity("Tomorrow early", 30, "low", at(6, 0, day_offset=1)))
    owner.schedule_activity(rex, Activity("Today late", 30, "low", at(23, 0)))
    titles = [a.title for a in owner.activities()]
    assert titles == ["Today late", "Tomorrow early"]


def test_simultaneous_starts_are_detected_as_conflict():
    """Two activities with identical start times are reported by find_conflicts."""
    owner, rex = make_owner_with_pet()
    book(owner, rex, Activity("A", 30, "high", at(9, 0)))
    book(owner, rex, Activity("B", 30, "high", at(9, 0)))
    assert len(owner.find_conflicts()) == 1


# ---------------------------------------------------------------------------
# Bounded recurrence (Recurrence.occurrences)
# ---------------------------------------------------------------------------

def test_recurrence_until_before_first_start_yields_nothing():
    """An until date before the first occurrence produces no occurrences."""
    rule = Recurrence(frequency="daily", until=TODAY - timedelta(days=1))
    assert list(rule.occurrences(at(9, 0))) == []


def test_recurrence_until_is_inclusive():
    """Occurrences on the until date itself are included."""
    rule = Recurrence(frequency="daily", until=TODAY + timedelta(days=2))
    starts = list(rule.occurrences(at(9, 0)))
    assert [s.date() for s in starts] == [
        TODAY, TODAY + timedelta(days=1), TODAY + timedelta(days=2)
    ]


def test_recurrence_weekly_every_other_week():
    """A weekly interval=2 rule skips a week between occurrences."""
    monday = datetime.combine(TODAY - timedelta(days=TODAY.weekday()), time(8, 0))
    rule = Recurrence(frequency="weekly", interval=2, count=3)
    starts = list(rule.occurrences(monday))
    gaps = [(starts[i + 1] - starts[i]).days for i in range(len(starts) - 1)]
    assert gaps == [14, 14]


def test_recurrence_daily_interval_skips_days():
    """A daily interval=3 rule lands every third day."""
    rule = Recurrence(frequency="daily", interval=3, count=3)
    starts = list(rule.occurrences(at(9, 0)))
    assert [s.date() for s in starts] == [
        TODAY, TODAY + timedelta(days=3), TODAY + timedelta(days=6)
    ]


def test_recurrence_unsupported_frequency_rejected():
    """A frequency other than daily/weekly is rejected."""
    with pytest.raises(ValueError):
        list(Recurrence(frequency="monthly", count=2).occurrences(at(9, 0)))


def test_recurrence_count_zero_yields_nothing():
    """count=0 should produce zero occurrences (suspected off-by-one bug)."""
    rule = Recurrence(frequency="daily", count=0)
    assert list(rule.occurrences(at(9, 0))) == []


def test_recurrence_interval_zero_is_rejected_cleanly():
    """interval=0 should raise a ValueError, not a ZeroDivisionError.

    (Suspected bug: the modulo math divides by interval with no guard.)
    """
    with pytest.raises(ValueError):
        list(Recurrence(frequency="daily", interval=0, count=3).occurrences(at(9, 0)))


# ---------------------------------------------------------------------------
# schedule_recurring
# ---------------------------------------------------------------------------

def test_schedule_recurring_all_clean_shares_series_id():
    """A conflict-free series schedules every occurrence under one series_id."""
    owner, rex = make_owner_with_pet()
    scheduled, skipped = owner.schedule_recurring(
        rex, Activity("Meds", 10, "high", at(9, 0)),
        Recurrence(frequency="daily", count=3),
    )
    assert len(scheduled) == 3
    assert skipped == []
    assert len({a.series_id for a in scheduled}) == 1


def test_schedule_recurring_rejects_unowned_pet():
    """Scheduling a series for an unowned pet raises ValueError."""
    owner, _ = make_owner_with_pet()
    stranger = Pet(name="Stranger", owned_by=None, breed="cat", sex="F")
    with pytest.raises(ValueError):
        owner.schedule_recurring(
            stranger, Activity("X", 10, "low", at(9, 0)),
            Recurrence(frequency="daily", count=2),
        )


# ---------------------------------------------------------------------------
# auto_schedule
# ---------------------------------------------------------------------------

def test_auto_schedule_no_conflict_keeps_time():
    """With no clash the activity is booked at its requested time."""
    owner, rex = make_owner_with_pet()
    a = owner.auto_schedule(rex, Activity("Walk", 30, "high", at(7, 0)))
    assert a.start == at(7, 0)


def test_auto_schedule_priority_tie_slides_instead_of_bumping():
    """Equal priority does NOT bump the incumbent; the newcomer slides."""
    owner, rex = make_owner_with_pet()
    walk = Activity("Walk", 30, "medium", at(13, 0))
    owner.schedule_activity(rex, walk)
    other = owner.auto_schedule(
        rex, Activity("Groom", 30, "medium", at(13, 0)), resolve_by_priority=True
    )
    assert walk.start == at(13, 0)      # incumbent unmoved
    assert other.start == at(13, 30)    # newcomer slid past it


def test_auto_schedule_without_priority_flag_always_slides():
    """resolve_by_priority=False slides even a higher-priority newcomer."""
    owner, rex = make_owner_with_pet()
    walk = Activity("Walk", 30, "low", at(13, 0))
    owner.schedule_activity(rex, walk)
    urgent = owner.auto_schedule(rex, Activity("Urgent", 30, "high", at(13, 0)))
    assert walk.start == at(13, 0)      # not bumped
    assert urgent.start == at(13, 30)   # slid


def test_auto_schedule_raises_when_no_slot_before_latest():
    """A hard deadline with no room raises ScheduleConflict."""
    owner, rex = make_owner_with_pet()
    owner.schedule_activity(rex, Activity("Busy", 60, "high", at(9, 0)))
    with pytest.raises(ScheduleConflict):
        owner.auto_schedule(
            rex, Activity("Squeeze", 30, "high", at(9, 0)), latest=at(9, 45)
        )


# ---------------------------------------------------------------------------
# Rolling repeat (complete_activity)
# ---------------------------------------------------------------------------

def test_complete_rolling_when_next_slot_taken_returns_none():
    """If the next-day slot is already booked, no new instance is spawned."""
    owner, rex = make_owner_with_pet()
    task = Activity("Vitamins", 10, "high", at(10, 0), repeat=Repeat.DAILY)
    owner.schedule_activity(rex, task)
    # Pre-book tomorrow at the same time so the rolling spawn would clash.
    owner.schedule_activity(rex, Activity("Blocker", 10, "high", at(10, 0, day_offset=1)))

    before = len(owner.activities())
    assert owner.complete_activity(task) is None
    assert len(owner.activities()) == before
    assert task.completed


def test_complete_rolling_keeps_time_of_day_not_original_date():
    """The next instance uses today+step, discarding the original date.

    Documents current behaviour: a rolling task completed today always rolls
    to today+1/+7 regardless of when the original was scheduled.
    """
    owner, rex = make_owner_with_pet()
    # Original scheduled 5 days ago, at 06:30.
    task = Activity("Feed", 10, "high", at(6, 30, day_offset=-5), repeat=Repeat.DAILY)
    book(owner, rex, task)  # bypass conflict check for the past-dated task
    nxt = owner.complete_activity(task)
    assert nxt is not None
    assert nxt.start.date() == TODAY + timedelta(days=1)
    assert nxt.start.time() == time(6, 30)


def test_complete_activity_rejects_activity_from_other_pet():
    """pet.complete_activity guards that the activity belongs to that pet."""
    owner, rex = make_owner_with_pet()
    mia = Pet(name="Mia", owned_by=owner, breed="Beagle", sex="F")
    owner.add_pet(mia)
    rex_task = Activity("Rex walk", 30, "high", at(8, 0))
    owner.schedule_activity(rex, rex_task)
    with pytest.raises(ValueError):
        mia.complete_activity(rex_task)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
