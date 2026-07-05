"""PawPal+ demo — build an owner with two pets and a day of scheduled tasks.

Run with:  python3 main.py

Activities are added deliberately OUT OF TIME ORDER so the printouts below prove
that sorting/filtering happen at query time (owner.activities), not insertion.
"""

from datetime import date, datetime, time, timedelta

from pawpal_system import (
    Activity,
    Owner,
    Pet,
    Recurrence,
    Repeat,
    ScheduleConflict,
    Status,
)

# All demo activities land on the same day; only the time-of-day varies.
TODAY = date.today()


def at(hour: int, minute: int = 0) -> datetime:
    """Build a datetime for TODAY at the given time-of-day."""
    return datetime.combine(TODAY, time(hour, minute))


def line(activity: Activity) -> str:
    """One-line rendering of an activity for the terminal."""
    mark = "✓" if activity.completed else " "
    pet_name = activity.pet.name if activity.pet else "?"
    return (
        f"  [{mark}] {activity.start:%m-%d %H:%M}  {activity.title:<14} "
        f"{pet_name:<4} ({activity.duration_minutes:>3} min, "
        f"{activity.priority} priority, {activity.status.value})"
    )


def show(title: str, activities) -> None:
    """Print a titled block of activities."""
    print(f"\n{title}")
    print("-" * len(title))
    if not activities:
        print("  (none)")
    for activity in activities:
        print(line(activity))


def try_schedule(owner: Owner, pet: Pet, activity: Activity) -> bool:
    """Attempt to schedule an activity, reporting success or a conflict.

    Wraps the conflict exception so a clash prints a warning and returns False
    instead of crashing the program. Returns True when the activity was booked.
    """
    try:
        owner.schedule_activity(pet, activity)
        print(f"  ✓ Booked {activity.title!r} at {activity.start:%H:%M}.")
        return True
    except ScheduleConflict as err:
        print(f"  ⚠️  Conflict — {activity.title!r} was NOT scheduled.")
        print(f"      {err}")
        return False


def build_schedule() -> Owner:
    """Create an owner, two pets, and tasks added OUT OF ORDER."""
    owner = Owner(name="Alex")

    rex = Pet(name="Rex", owned_by=owner, breed="Labrador", sex="M")
    mia = Pet(name="Mia", owned_by=owner, breed="Beagle", sex="F")
    owner.add_pet(rex)
    owner.add_pet(mia)

    # Intentionally NOT in chronological order, and pets interleaved.
    owner.schedule_activity(rex, Activity("Evening play", 45, "medium", at(18, 0)))
    owner.schedule_activity(mia, Activity("Bedtime treat", 5, "low", at(19, 0)))
    owner.schedule_activity(rex, Activity("Morning walk", 30, "high", at(7, 0)))
    owner.schedule_activity(mia, Activity("Afternoon walk", 30, "medium", at(13, 0)))
    owner.schedule_activity(rex, Activity("Lunch feeding", 15, "high", at(12, 0)))
    owner.schedule_activity(mia, Activity("Breakfast", 15, "high", at(8, 0)))

    return owner


def main() -> None:
    owner = build_schedule()
    rex, mia = owner.pets_owned

    print("PawPal+ Schedule Demo")
    print("=" * 40)

    # --- Sorting: inserted out of order, queried in time order -----------
    show("All activities, sorted by time", owner.activities())

    # --- Filtering by pet -------------------------------------------------
    show("Filter by pet: Rex", owner.activities(pet=rex))
    show("Filter by pet: Mia", owner.activities(pet=mia))

    # --- Filtering by status ---------------------------------------------
    owner.complete_activity(owner.activities(pet=rex)[0])  # Rex's first (Morning walk)
    show("Filter by status: completed", owner.activities(status=Status.COMPLETED))
    show("Filter by status: scheduled", owner.activities(status=Status.SCHEDULED))

    # --- Conflict handling: two activities competing for the same time ---
    print("\nConflict handling: two activities for overlapping times")
    print("-" * 55)
    before = len(owner.activities())
    # First one lands on a free 15:00 slot.
    try_schedule(owner, rex, Activity("Vet checkup", 30, "high", at(15, 0)))
    # Second one overlaps 15:00-15:30, so it is rejected (not added, no crash).
    try_schedule(owner, mia, Activity("Nail trim", 20, "low", at(15, 15)))
    after = len(owner.activities())
    print(f"  Activities before: {before}, after: {after} "
          f"(only the non-conflicting one was added)")

    # --- Recurrence: a daily med for the next 3 days ---------------------
    print("\nRecurring: 'Medication' daily at 09:00 for 3 days")
    print("-" * 48)
    scheduled, skipped = owner.schedule_recurring(
        rex,
        Activity("Medication", 10, "high", at(9, 0)),
        Recurrence(frequency="daily", count=3),
    )
    for occ in scheduled:
        print(line(occ))
    print(f"  -> {len(scheduled)} scheduled, {len(skipped)} skipped (conflicts)")

    # Show that filtering by date isolates one day of the series.
    tomorrow = TODAY + timedelta(days=1)
    show(f"Filter by date: {tomorrow:%Y-%m-%d}", owner.activities(on=tomorrow))

    # --- Auto-schedule around a conflict ---------------------------------
    print("\nAuto-schedule 'Grooming' (30 min) requested at 07:15 (clashes)")
    print("-" * 62)
    groom = owner.auto_schedule(rex, Activity("Grooming", 30, "medium", at(7, 15)))
    print(line(groom))
    print("  -> slid to the first free slot that fits")

    # --- Priority-based conflict resolution ------------------------------
    print("\nPriority resolve: high-priority 'Urgent meds' at 13:00 vs Mia's walk")
    print("-" * 68)
    owner.auto_schedule(
        rex,
        Activity("Urgent meds", 30, "high", at(13, 0)),
        resolve_by_priority=True,
    )
    show("Afternoon window after resolution", owner.activities(on=TODAY))

    # --- Rolling recurrence: completing one spawns the next --------------
    print("\nRolling recurrence: complete a task -> next instance auto-created")
    print("-" * 66)
    vitamins = Activity("Vitamins", 10, "high", at(10, 0), repeat=Repeat.DAILY)
    owner.schedule_activity(rex, vitamins)
    print("  Scheduled (daily):")
    print(line(vitamins))
    next_vitamins = owner.complete_activity(vitamins)
    print("  After completing it, the next instance appears:")
    print(line(next_vitamins))

    bath = Activity("Bath", 20, "medium", at(16, 0), repeat=Repeat.WEEKLY)
    owner.schedule_activity(mia, bath)
    next_bath = owner.complete_activity(bath)
    print("  Weekly task 'Bath' completed -> next instance:")
    print(line(next_bath))

    # --- Conflict report (should be clean now) ---------------------------
    conflicts = owner.find_conflicts()
    print(f"\nRemaining conflicts: {len(conflicts)}")
    for first, second in conflicts:
        print(f"  {first.title!r} overlaps {second.title!r}")

    # --- Prevention still rejects a hard clash without auto-move ---------
    print("\nDirect schedule over a booked slot is still rejected:")
    try_schedule(owner, rex, Activity("Vet call", 30, "high", at(18, 15)))


if __name__ == "__main__":
    main()
