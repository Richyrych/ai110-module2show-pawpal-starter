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

## ✨ Features

- **Owner & pet management** — add an owner and any number of pets (name, breed, sex); each pet is wired to its owner and persists in the Streamlit session.
- **Interval-based scheduling** — every task has a real `start` datetime and a duration, so the system reasons about actual time ranges rather than fixed slots.
- **Chronological sorting** — the schedule is always returned in start-time order, regardless of the order tasks were added.
- **Composable filtering** — narrow the view by pet, by status (scheduled / completed / cancelled / missed), and/or by date in a single query.
- **Owner-level conflict detection** — overlaps are flagged across *all* pets (one owner can't be two places at once), using an efficient sweep-line pass.
- **Conflict prevention & resolution** — bookings that clash are rejected with a clear warning, or optionally auto-scheduled into the next free slot, with higher-priority tasks able to bump lower-priority ones.
- **Recurring tasks** — bounded series (daily/weekly with intervals, selected weekdays, and a `count`/`until` bound) plus rolling repeats that spawn the next instance when a task is completed.
- **Task lifecycle** — mark tasks complete or cancelled; cancelling frees the slot for rebooking.
- **Professional Streamlit UI** — summary metrics, an interactive sorted/filtered table with priority and status badges, and distinct conflict warnings.
- **Tested** — a 50-test `pytest` suite covering happy paths and edge cases (see [Testing PawPal+](#-testing-pawpal)).

## 📸 Demo Walkthrough

### What a user can do in the app

The Streamlit UI ([`app.py`](app.py)) is organized top to bottom as a single page:

1. **Set the owner** — type an owner name; it persists for the whole session.
2. **Add pets** — enter a name, pick a species/breed and sex, and click **Add pet**. Each pet appears in a table showing its breed, sex, and current activity count. Duplicate names are rejected.
3. **Schedule a task** — choose the pet, date, and start time; give it a title, duration, priority, and a repeat mode (**One-off**, **Daily**, or **Weekly**). Click **Add task** to book it.
4. **Let the app resolve conflicts** — tick **Auto-schedule around conflicts** before adding a task, and a clashing task slides to the next free slot instead of being rejected.
5. **Read the schedule at a glance** — a metrics row shows **Total / Scheduled / Completed / Conflicts**, and the schedule renders as a sorted, interactive table with 🔴/🟡/🟢 priority and ⏳/✅/🚫/⚠️ status badges.
6. **Filter the view** — narrow the table by pet and/or by status; it stays sorted by start time.
7. **Complete tasks** — tick the **Done** box on a row to mark it complete. A rolling (daily/weekly) task automatically spawns its next instance and confirms the new date.
8. **See conflict warnings** — a booking that clashes triggers a dedicated warning, and any overlaps already on the calendar are listed under the schedule (or a green "no conflicts" note when clean).
9. **Inspect state** — the **🔍 Debug: session_state** panel shows what is persisted in memory, with a button to reset the session.

### Example workflow

1. Launch the app and set the owner to *Jordan*.
2. Add two pets: **Rex** (dog) and **Mia** (cat).
3. Schedule *Morning walk* for Rex at **07:00** (30 min, high) and *Breakfast* for Mia at **08:00** (15 min, high).
4. Try to schedule *Vet call* for Rex at **07:15** — a conflict warning appears and it is **not** added.
5. Re-add *Vet call* with **Auto-schedule around conflicts** ticked — it slides to **07:30**, the first free slot.
6. Add *Vitamins* for Rex at **10:00** with repeat = **Daily**, then tick its **Done** box — it completes and the next day's instance is created automatically.
7. Filter by **Rex** and status **Scheduled** to see just his upcoming tasks, still in time order.

### Key scheduling behaviors

- **Sorting happens at query time** — tasks added out of order are always returned chronologically.
- **Conflicts are owner-level** — one owner can't be in two places at once, so overlaps count even across different pets.
- **Touching edges don't conflict** — a task starting exactly when another ends is allowed (half-open intervals).
- **Prevention or resolution** — a clash is either rejected with a clear message, or auto-scheduled into the next free slot (optionally bumping lower-priority tasks).
- **Two recurrence styles** — a bounded batch series (`count`/`until`), and a rolling repeat that spawns the next instance on completion (today + 1 day for daily, + 7 for weekly).
- **Cancelling frees a slot** — a cancelled task no longer blocks its time; a completed one still occupies it.

### Sample CLI output

Running the scripted demo prints the scheduling logic end to end (activities are added **out of order** to prove sorting happens at query time):

```console
$ python main.py
PawPal+ Schedule Demo
========================================

All activities, sorted by time
------------------------------
  [ ] 07-05 07:00  Morning walk   Rex  ( 30 min, high priority, scheduled)
  [ ] 07-05 08:00  Breakfast      Mia  ( 15 min, high priority, scheduled)
  [ ] 07-05 12:00  Lunch feeding  Rex  ( 15 min, high priority, scheduled)
  [ ] 07-05 13:00  Afternoon walk Mia  ( 30 min, medium priority, scheduled)
  [ ] 07-05 18:00  Evening play   Rex  ( 45 min, medium priority, scheduled)
  [ ] 07-05 19:00  Bedtime treat  Mia  (  5 min, low priority, scheduled)

Filter by status: completed
---------------------------
  [✓] 07-05 07:00  Morning walk   Rex  ( 30 min, high priority, completed)

Conflict handling: two activities for overlapping times
-------------------------------------------------------
  ✓ Booked 'Vet checkup' at 15:00.
  ⚠️  Conflict — 'Nail trim' was NOT scheduled.
      'Nail trim' (15:15-15:35) conflicts with 'Vet checkup' (15:00-15:30).
  Activities before: 6, after: 7 (only the non-conflicting one was added)

Recurring: 'Medication' daily at 09:00 for 3 days
------------------------------------------------
  [ ] 07-05 09:00  Medication     Rex  ( 10 min, high priority, scheduled)
  [ ] 07-06 09:00  Medication     Rex  ( 10 min, high priority, scheduled)
  [ ] 07-07 09:00  Medication     Rex  ( 10 min, high priority, scheduled)
  -> 3 scheduled, 0 skipped (conflicts)

Auto-schedule 'Grooming' (30 min) requested at 07:15 (clashes)
--------------------------------------------------------------
  [ ] 07-05 07:30  Grooming       Rex  ( 30 min, medium priority, scheduled)
  -> slid to the first free slot that fits

Rolling recurrence: complete a task -> next instance auto-created
------------------------------------------------------------------
  Scheduled (daily):
  [ ] 07-05 10:00  Vitamins       Rex  ( 10 min, high priority, scheduled)
  After completing it, the next instance appears:
  [ ] 07-06 10:00  Vitamins       Rex  ( 10 min, high priority, scheduled)
  Weekly task 'Bath' completed -> next instance:
  [ ] 07-12 16:00  Bath           Mia  ( 20 min, medium priority, scheduled)

Remaining conflicts: 0

Direct schedule over a booked slot is still rejected:
  ⚠️  Conflict — 'Vet call' was NOT scheduled.
      'Vet call' (18:15-18:45) conflicts with 'Evening play' (18:00-18:45).
```

> The output above is trimmed for readability; run `python main.py` to see every section (per-pet filters, date filtering, and priority-based resolution).

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
