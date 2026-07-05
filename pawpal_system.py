"""PawPal+ — class skeleton generated from diagrams/uml.md.

Owner, Pet, Activity, and Calendar model a simple pet-activity scheduler.
Relationships (from the UML):
    Owner  "1" --> "*" Pet       : owns
    Pet    "1" --> "*" Activity  : has scheduled
    Owner  "1" --> "1" Calendar  : views / manages
    Calendar "1" o-- "*" Activity : contains

Design notes
------------
Time is modelled as a real interval: every Activity has a ``start`` datetime and
derives its ``end`` from ``duration_minutes``. This lets us sort chronologically,
detect true overlaps, and reason about duration — none of which a fixed list of
"HH:MM" slot tokens could do.

The Calendar is the single source of truth for scheduled activities. A Pet's
activities are a *view* (``Pet.activities``) filtered from the owner's calendar,
so the two can never drift out of sync.

Conflicts are owner-level: a single owner can only do one thing at a time, so an
overlap between *any* two of the owner's activities (even across different pets)
is a conflict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Iterator, List, Optional, Tuple

# Priority strings ranked low -> high, used for conflict resolution.
PRIORITY_RANK = {"low": 0, "medium": 1, "high": 2}


def priority_rank(activity: "Activity") -> int:
    """Numeric rank of an activity's priority (unknown priorities rank lowest)."""
    return PRIORITY_RANK.get(activity.priority.lower(), 0)


class Status(str, Enum):
    """Lifecycle state of an activity.

    Subclassing ``str`` keeps the values JSON/print friendly (``Status.SCHEDULED``
    prints and compares as ``"scheduled"``), which is handy for the Streamlit UI.
    """

    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    MISSED = "missed"


class Repeat(str, Enum):
    """How a *rolling* recurring activity repeats.

    Unlike a bounded :class:`Recurrence` (which materialises a fixed series up
    front), a Repeat rolls forward: completing one instance auto-creates the
    next one. DAILY steps by 1 day, WEEKLY by 7.
    """

    DAILY = "daily"
    WEEKLY = "weekly"


# Days to advance from *today* when spawning the next rolling instance.
REPEAT_STEP_DAYS = {Repeat.DAILY: 1, Repeat.WEEKLY: 7}


class ScheduleConflict(ValueError):
    """Raised when an activity would overlap an existing one.

    Subclasses ``ValueError`` so existing ``except ValueError`` handlers (e.g. in
    the Streamlit app) keep working.
    """


@dataclass
class Recurrence:
    """A repeat rule for an activity (RRULE-lite).

    ``frequency`` is "daily" or "weekly". ``interval`` skips periods (every 2nd
    day/week). ``weekdays`` (Mon=0 .. Sun=6) restricts a weekly rule to specific
    days; empty means "same weekday as the first occurrence". The rule MUST be
    bounded by ``count`` (number of occurrences) or ``until`` (last date), so
    expansion always terminates.
    """

    frequency: str
    interval: int = 1
    weekdays: List[int] = field(default_factory=list)
    count: Optional[int] = None
    until: Optional[date] = None

    def occurrences(self, first_start: datetime) -> Iterator[datetime]:
        """Yield each occurrence's start datetime, beginning at ``first_start``.

        Walks forward one day at a time from the first occurrence's date and
        emits the days that satisfy the rule, carrying ``first_start``'s
        time-of-day. The day-count cap is a runaway guard, not a real limit —
        ``count``/``until`` stop it long before then.
        """
        if self.count is None and self.until is None:
            raise ValueError("A Recurrence needs a count or an until date.")
        if self.frequency not in ("daily", "weekly"):
            raise ValueError(f"Unsupported frequency {self.frequency!r}.")

        anchor = first_start.date()
        tod = first_start.time()
        weekdays = sorted(self.weekdays) if self.weekdays else [anchor.weekday()]
        anchor_monday = anchor - timedelta(days=anchor.weekday())

        yielded = 0
        day = anchor
        for _ in range(3660):  # ~10 years of days; a guard against misconfig.
            if self.until is not None and day > self.until:
                return
            if self.frequency == "daily":
                matches = (day - anchor).days % self.interval == 0
            else:  # weekly
                week_offset = (day - anchor_monday).days // 7
                matches = day.weekday() in weekdays and week_offset % self.interval == 0
            if matches:
                when = datetime.combine(day, tod)
                if when >= first_start:
                    yield when
                    yielded += 1
                    if self.count is not None and yielded >= self.count:
                        return
            day += timedelta(days=1)


@dataclass
class Activity:
    """A single scheduled activity for a pet (e.g. walk, vet visit, feeding)."""

    title: str
    duration_minutes: int
    priority: str
    start: datetime
    status: Status = Status.SCHEDULED
    # Back-reference to the owning Pet. repr/compare are disabled to avoid
    # infinite recursion (Pet -> Activity -> Pet) and identity surprises.
    pet: Optional["Pet"] = field(default=None, repr=False, compare=False)
    # Links occurrences generated from the same recurring rule; None if one-off.
    series_id: Optional[int] = None
    # Rolling repeat rule: when set, completing this instance auto-creates the
    # next one (see Owner.complete_activity). None means a one-off activity.
    repeat: Optional[Repeat] = None

    @property
    def end(self) -> datetime:
        """When the activity finishes (start + duration)."""
        return self.start + timedelta(minutes=self.duration_minutes)

    @property
    def completed(self) -> bool:
        """Backwards-compatible flag: True when status is COMPLETED."""
        return self.status is Status.COMPLETED

    def overlaps(self, other: "Activity") -> bool:
        """True if this activity's interval intersects ``other``'s.

        Uses the standard half-open interval test: two intervals overlap iff
        each starts before the other ends. Touching edges (one ends exactly when
        the next begins) do NOT count as an overlap.
        """
        return self.start < other.end and other.start < self.end

    def mark_complete(self) -> None:
        """Mark this activity as completed."""
        self.status = Status.COMPLETED

    def cancel(self) -> None:
        """Mark this activity as cancelled (frees its time for others)."""
        self.status = Status.CANCELLED


@dataclass
class Pet:
    """A pet owned by an Owner. Its activities are a view of the calendar."""

    name: str
    owned_by: "Owner"
    breed: str
    sex: str

    @property
    def activities(self) -> List[Activity]:
        """This pet's activities, read from the owner's calendar (source of truth)."""
        if self.owned_by is None:
            return []
        return [a for a in self.owned_by.calendar.pet_activity if a.pet is self]

    def complete_activity(self, activity: Activity) -> Optional[Activity]:
        """Mark one of this pet's activities complete.

        Delegates to the owner so a rolling recurring activity spawns its next
        instance. Returns that new instance (or None).
        """
        if activity.pet is not self:
            raise ValueError(f"{activity.title!r} is not scheduled for {self.name}.")
        if self.owned_by is None:
            activity.mark_complete()
            return None
        return self.owned_by.complete_activity(activity)


@dataclass
class Calendar:
    """Holds all pet activities and answers scheduling questions about them."""

    pet_activity: List[Activity] = field(default_factory=list)

    @staticmethod
    def _is_active(activity: Activity) -> bool:
        """Cancelled activities no longer occupy time, so they can't conflict."""
        return activity.status is not Status.CANCELLED

    def conflicts_for(self, candidate: Activity) -> List[Activity]:
        """Return existing activities that overlap ``candidate`` (excluding itself)."""
        return [
            a
            for a in self.pet_activity
            if a is not candidate and self._is_active(a) and a.overlaps(candidate)
        ]

    def find_conflicts(self) -> List[Tuple[Activity, Activity]]:
        """Return every overlapping pair of scheduled activities.

        Sweep-line algorithm: sort by start time, then walk once keeping a list
        of intervals that are still "open" (haven't ended yet). Each new activity
        conflicts with exactly the still-open ones. This is O(n log n + k) for k
        conflicting pairs — far cheaper than the naive O(n^2) all-pairs check.
        """
        active = sorted(
            (a for a in self.pet_activity if self._is_active(a)),
            key=lambda a: a.start,
        )
        conflicts: List[Tuple[Activity, Activity]] = []
        ongoing: List[Activity] = []
        for activity in active:
            # Drop anything that finished before this one starts.
            ongoing = [o for o in ongoing if o.end > activity.start]
            conflicts.extend((o, activity) for o in ongoing)
            ongoing.append(activity)
        return conflicts

    def find_free_slot(
        self,
        duration_minutes: int,
        earliest: datetime,
        latest: Optional[datetime] = None,
    ) -> Optional[datetime]:
        """Return the earliest start >= ``earliest`` where ``duration`` fits.

        Greedy gap scan: walk the booked intervals in time order, advancing a
        cursor past each one until a gap large enough to hold the activity opens
        up. Returns None if nothing fits before ``latest`` (an open-ended search,
        ``latest=None``, always succeeds after the last booking).
        """
        need = timedelta(minutes=duration_minutes)
        booked = sorted(
            (a for a in self.pet_activity if self._is_active(a) and a.end > earliest),
            key=lambda a: a.start,
        )
        cursor = earliest
        for a in booked:
            if a.start - cursor >= need:
                break  # the gap [cursor, a.start) is big enough
            cursor = max(cursor, a.end)
        if latest is not None and cursor + need > latest:
            return None
        return cursor

    def add_pet_activity(self, activity: Activity) -> None:
        """Add an activity to the calendar, rejecting time conflicts."""
        if activity in self.pet_activity:
            return
        clashes = self.conflicts_for(activity)
        if clashes:
            other = clashes[0]
            raise ScheduleConflict(
                f"{activity.title!r} ({activity.start:%H:%M}-{activity.end:%H:%M}) "
                f"conflicts with {other.title!r} "
                f"({other.start:%H:%M}-{other.end:%H:%M})."
            )
        self.pet_activity.append(activity)

    def edit_pet_activity(self, activity: Activity) -> None:
        """Ensure an activity is present on the calendar (add if missing)."""
        if activity not in self.pet_activity:
            self.add_pet_activity(activity)

    def remove_pet_activity(self, activity: Activity) -> None:
        """Remove an activity from the calendar."""
        if activity not in self.pet_activity:
            raise ValueError(f"{activity.title!r} is not on the calendar.")
        self.pet_activity.remove(activity)


@dataclass
class Owner:
    """A pet owner who manages pets, their activities, and a calendar."""

    name: str
    pets_owned: List[Pet] = field(default_factory=list)
    calendar: Calendar = field(default_factory=Calendar)
    _series_counter: int = field(default=0, repr=False)

    def _next_series_id(self) -> int:
        """Allocate a fresh, monotonically increasing id for a recurring series."""
        self._series_counter += 1
        return self._series_counter

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner's list of pets and set its back-reference."""
        if pet not in self.pets_owned:
            self.pets_owned.append(pet)
            pet.owned_by = self

    def schedule_activity(self, pet: Pet, activity: Activity) -> None:
        """Schedule an activity for one of this owner's pets.

        Wires the activity to its pet, then adds it to the calendar, which
        rejects the activity if it overlaps any existing one (owner-level).
        """
        if pet not in self.pets_owned:
            raise ValueError(f"{pet.name} is not owned by {self.name}.")
        activity.pet = pet
        self.calendar.add_pet_activity(activity)

    def schedule_recurring(
        self, pet: Pet, template: Activity, recurrence: Recurrence
    ) -> Tuple[List[Activity], List[Activity]]:
        """Expand a recurring rule into concrete occurrences and schedule each.

        Each occurrence is its own Activity object (so completing one leaves the
        rest untouched) sharing a ``series_id``. Occurrences that would clash are
        skipped rather than aborting the whole series. Returns
        ``(scheduled, skipped)``.
        """
        if pet not in self.pets_owned:
            raise ValueError(f"{pet.name} is not owned by {self.name}.")
        series_id = self._next_series_id()
        scheduled: List[Activity] = []
        skipped: List[Activity] = []
        for when in recurrence.occurrences(template.start):
            occurrence = Activity(
                title=template.title,
                duration_minutes=template.duration_minutes,
                priority=template.priority,
                start=when,
                series_id=series_id,
            )
            occurrence.pet = pet
            try:
                self.calendar.add_pet_activity(occurrence)
                scheduled.append(occurrence)
            except ScheduleConflict:
                skipped.append(occurrence)
        return scheduled, skipped

    def auto_schedule(
        self,
        pet: Pet,
        activity: Activity,
        latest: Optional[datetime] = None,
        resolve_by_priority: bool = False,
    ) -> Activity:
        """Schedule ``activity`` at its desired time, working around conflicts.

        - No clash: booked as-is.
        - Clash, and ``resolve_by_priority`` and the new activity outranks *every*
          conflict: the lower-priority activities are bumped to the next free
          slots after it, and the new one keeps its desired time.
        - Otherwise: the new activity slides to the earliest free slot that fits.

        Returns the scheduled activity (with its final ``start``).
        """
        if pet not in self.pets_owned:
            raise ValueError(f"{pet.name} is not owned by {self.name}.")
        activity.pet = pet
        clashes = self.calendar.conflicts_for(activity)
        if not clashes:
            self.calendar.add_pet_activity(activity)
            return activity

        if resolve_by_priority and all(
            priority_rank(activity) > priority_rank(c) for c in clashes
        ):
            # New activity wins its slot; displaced ones are re-placed after it.
            for loser in clashes:
                self.calendar.remove_pet_activity(loser)
            self.calendar.add_pet_activity(activity)
            for loser in clashes:
                loser.start = self.calendar.find_free_slot(
                    loser.duration_minutes, activity.end
                )
                self.calendar.add_pet_activity(loser)
            return activity

        slot = self.calendar.find_free_slot(
            activity.duration_minutes, activity.start, latest
        )
        if slot is None:
            raise ScheduleConflict(
                f"No free slot for {activity.title!r} before {latest:%H:%M}."
            )
        activity.start = slot
        self.calendar.add_pet_activity(activity)
        return activity

    def complete_activity(self, activity: Activity) -> Optional[Activity]:
        """Mark ``activity`` complete and, if it is a rolling recurring task,
        create its next instance in the calendar.

        The next instance is scheduled for **today + 1 day** (DAILY) or
        **today + 7 days** (WEEKLY), keeping the same time-of-day. Returns the
        newly created Activity, or None if the activity is one-off, was already
        completed, or the target slot is already taken.
        """
        if activity.completed:
            return None  # idempotent: don't spawn a second "next" instance.
        activity.mark_complete()

        if activity.repeat is None:
            return None

        step = REPEAT_STEP_DAYS[activity.repeat]
        next_start = datetime.combine(
            date.today() + timedelta(days=step), activity.start.time()
        )
        next_instance = Activity(
            title=activity.title,
            duration_minutes=activity.duration_minutes,
            priority=activity.priority,
            start=next_start,
            series_id=activity.series_id,
            repeat=activity.repeat,
        )
        next_instance.pet = activity.pet
        try:
            self.calendar.add_pet_activity(next_instance)
        except ScheduleConflict:
            # A future instance already occupies that slot — nothing to do.
            return None
        return next_instance

    def activities(
        self,
        *,
        pet: Optional[Pet] = None,
        status: Optional[Status] = None,
        on: Optional[date] = None,
    ) -> List[Activity]:
        """Return activities matching the given filters, sorted by start time.

        Every filter is optional; passing none returns the whole schedule sorted
        chronologically. This single query replaces ad-hoc nested loops in the
        UI/CLI.
        """
        result = self.calendar.pet_activity
        if pet is not None:
            result = [a for a in result if a.pet is pet]
        if status is not None:
            result = [a for a in result if a.status is status]
        if on is not None:
            result = [a for a in result if a.start.date() == on]
        return sorted(result, key=lambda a: a.start)

    def find_conflicts(self) -> List[Tuple[Activity, Activity]]:
        """Return every overlapping pair across all of this owner's activities."""
        return self.calendar.find_conflicts()

    def view_calendar(self) -> Calendar:
        """Return the owner's calendar."""
        return self.calendar

    def edit_pet(self, pet: Pet) -> None:
        """Edit details of one of this owner's pets (adds it if new)."""
        if pet not in self.pets_owned:
            self.add_pet(pet)

    def edit_schedule(self, activity: Activity) -> None:
        """Edit a scheduled activity on the owner's calendar."""
        self.calendar.edit_pet_activity(activity)
