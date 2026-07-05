# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Paste a sample of your app's CLI or Streamlit output here so a reader can see what a generated plan looks like:

```
# e.g.:
Today's Schedule
========================================

Rex (Labrador)
  [ ] 07:00  Morning walk (30 min, high priority)
  [ ] 12:00  Lunch feeding (15 min, high priority)
  [ ] 18:00  Evening play (45 min, medium priority)

Mia (Beagle)
  [ ] 08:00  Breakfast (15 min, high priority)
  [ ] 13:00  Afternoon walk (30 min, medium priority)
  [ ] 19:00  Bedtime treat (5 min, low priority)
```

## 🧪 Testing PawPal+

Run the full test suite from the project root:

```bash
python -m pytest
```

The suite lives in [`tests/`](tests/) and has two files:

- **`test_pawpal.py`** — happy-path coverage: activity completion and duration,
  scheduling and conflict rejection, owner-level conflicts across pets,
  chronological sorting and filtering, bounded `Recurrence` expansion,
  `auto_schedule` conflict resolution, and the rolling `Repeat` flow.
- **`test_pawpal_edge_cases.py`** — boundary conditions: interval edges
  (touching, 1-minute, full-containment, zero-duration), status semantics
  (cancelled frees a slot, completed still blocks it), degenerate collections
  (empty calendar, reverse/multi-day sorting, simultaneous starts), recurrence
  bounds (`until` inclusive/before-start, `interval`/`count` validation), and
  rolling-repeat edges (next slot taken, cross-pet guard).

Test output:

```
============================= test session starts ==============================
platform linux -- Python 3.13.14, pytest-9.0.3, pluggy-1.6.0
rootdir: .../ai110-module2show-pawpal-starter
plugins: anyio-4.13.0
collected 50 items

tests/test_pawpal.py .....................                               [ 42%]
tests/test_pawpal_edge_cases.py .............................            [100%]

============================== 50 passed in 0.03s ==============================
```

## 📐 Smarter Scheduling

PawPal+ models each activity as a real time interval — every `Activity` has a
`start: datetime` and derives its `end` from `duration_minutes` (`Activity.end`).
This interval model is what makes the behaviors below possible. All scheduling
logic lives in [`pawpal_system.py`](pawpal_system.py).

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Sorting | `Owner.activities()` | Returns activities sorted chronologically by `start`. Sorting happens at query time, so tasks added out of order still print in time order. |
| Filtering | `Owner.activities(pet=, status=, on=)` | One query filters by pet, by `Status` (scheduled/completed/cancelled/missed), and/or by date — then sorts. Backed by `Pet.activities` and the `Status` enum. |
| Conflict detection | `Calendar.find_conflicts()`, `Calendar.conflicts_for()`, `Activity.overlaps()` | Owner-level overlap detection: a single owner can't be two places at once, so overlaps are checked across *all* pets. |
| Recurring activities | `Owner.schedule_recurring()` + `Recurrence`; `Owner.complete_activity()` + `Repeat` | Two recurrence styles — a bounded batch series and a rolling repeat that spawns the next instance on completion. |

### Sorting behavior

`Owner.activities()` reads the calendar and returns the list sorted by each
activity's `start` datetime (`sorted(..., key=lambda a: a.start)`). Because the
sort happens on every call, activities inserted in any order are always returned
chronologically — no need to keep the underlying list ordered.

### Filtering behavior

`Owner.activities()` accepts three optional, composable filters:

- `pet=` — only that pet's activities (uses the `Pet.activities` view, filtered from the calendar so it can never drift out of sync).
- `status=` — filter by a `Status` enum value (`SCHEDULED`, `COMPLETED`, `CANCELLED`, `MISSED`).
- `on=` — only activities whose `start` falls on a given date.

Passing no filters returns the whole schedule, still sorted by time.

### Conflict detection

Conflicts are **owner-level**: because one owner can only do one thing at a
time, any two overlapping activities conflict even if they belong to different
pets.

- `Activity.overlaps(other)` — the primitive half-open interval test (`self.start < other.end and other.start < self.end`); touching edges do **not** conflict.
- `Calendar.conflicts_for(candidate)` — every existing activity that overlaps a candidate (used to reject a booking before it is added).
- `Calendar.find_conflicts()` — a **sweep-line** algorithm that returns every overlapping pair in `O(n log n + k)` (sort by start, then walk once tracking still-open intervals), exposed on the owner as `Owner.find_conflicts()`.

**Prevention vs. resolution.** `Owner.schedule_activity()` *rejects* a clashing
booking by raising `ScheduleConflict` (a `ValueError` subclass) with a clear
message and without mutating the schedule, so callers can catch it and warn the
user without crashing. Alternatively, `Owner.auto_schedule()` *works around* a
conflict — sliding the task to the earliest free slot (`Calendar.find_free_slot()`,
a greedy gap scan) or, with `resolve_by_priority=True`, bumping lower-priority
tasks to later slots.

### Recurring activities

Two complementary mechanisms:

- **Bounded batch** — `Owner.schedule_recurring(pet, template, Recurrence(...))` expands a `Recurrence` rule (`daily`/`weekly`, `interval`, `weekdays`, bounded by `count` or `until`) via `Recurrence.occurrences()` into distinct `Activity` objects sharing a `series_id`. Occurrences that clash are skipped, not aborted; returns `(scheduled, skipped)`.
- **Rolling repeat** — set `Activity.repeat` to `Repeat.DAILY` or `Repeat.WEEKLY`, and `Owner.complete_activity()` auto-creates the next instance when the current one is marked complete: **today + 1 day** for daily, **today + 7 days** for weekly, keeping the same time-of-day. It's idempotent (re-completing won't double-spawn) and skips creation if the target slot is already taken.

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
