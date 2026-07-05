from datetime import date, datetime, time

import pandas as pd
import streamlit as st

from pawpal_system import Activity, Owner, Pet, Repeat, ScheduleConflict, Status

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")
st.caption(
    "Plan your pets' daily care — tasks are sorted chronologically, filtered on "
    "demand, and checked for scheduling conflicts."
)

# Visual vocabulary shared by the schedule table so priority and status read at
# a glance instead of as plain text.
PRIORITY_BADGE = {"high": "🔴 High", "medium": "🟡 Medium", "low": "🟢 Low"}
STATUS_BADGE = {
    Status.SCHEDULED: "⏳ Scheduled",
    Status.COMPLETED: "✅ Completed",
    Status.CANCELLED: "🚫 Cancelled",
    Status.MISSED: "⚠️ Missed",
}

# --- Backend state -------------------------------------------------------
# The Owner (and, through it, every Pet and Activity) lives in the session
# vault. It is created ONCE on first load; every later rerun reuses the same
# object, so pets and activities added in the browser stay in memory.
if "owner" not in st.session_state:
    st.session_state.owner = Owner(name="Jordan")

owner = st.session_state.owner


st.subheader("Owner")
# Keep the persisted Owner's name in sync with the input on every rerun.
owner.name = st.text_input("Owner name", value=owner.name)

st.divider()

st.subheader("Pets")
st.caption("Add a pet. It becomes a Pet object owned by the Owner and persists in memory.")

pcol1, pcol2, pcol3 = st.columns(3)
with pcol1:
    pet_name = st.text_input("Pet name", value="Mochi")
with pcol2:
    breed = st.selectbox("Species / breed", ["dog", "cat", "other"])
with pcol3:
    sex = st.selectbox("Sex", ["M", "F", "unknown"])

if st.button("Add pet"):
    existing_names = [pet.name for pet in owner.pets_owned]
    if not pet_name.strip():
        st.error("Please enter a pet name.")
    elif pet_name in existing_names:
        st.error(f"{owner.name} already owns a pet named {pet_name!r}.")
    else:
        # owner.add_pet appends the Pet and wires up its owned_by back-reference.
        owner.add_pet(Pet(name=pet_name, owned_by=owner, breed=breed, sex=sex))
        st.success(f"Added {pet_name}.")

if owner.pets_owned:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Pet": pet.name,
                    "Breed": pet.breed,
                    "Sex": pet.sex,
                    "Activities": len(pet.activities),
                }
                for pet in owner.pets_owned
            ]
        ),
        hide_index=True,
        width="stretch",
    )
else:
    st.info("No pets yet. Add one above.")

st.divider()

st.subheader("Schedule a Task")
st.caption("Pick any time — PawPal+ checks the whole calendar for overlaps before booking.")

if not owner.pets_owned:
    st.info("Add a pet first, then you can schedule tasks.")
else:
    tcol1, tcol2, tcol3 = st.columns(3)
    with tcol1:
        target_pet_name = st.selectbox(
            "For pet", [pet.name for pet in owner.pets_owned]
        )
    with tcol2:
        task_date = st.date_input("Date", value=date.today())
    with tcol3:
        task_time = st.time_input("Start time", value=time(8, 0))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        task_title = st.text_input("Task title", value="Morning walk")
    with col2:
        duration = st.number_input(
            "Duration (minutes)", min_value=1, max_value=240, value=20
        )
    with col3:
        priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)
    with col4:
        # "One-off" maps to no repeat; Daily/Weekly make it a rolling task that
        # re-creates itself when completed.
        repeat_choice = st.selectbox("Repeat", ["One-off", "Daily", "Weekly"])

    # When on, a clash slides the task to the next free slot instead of being
    # rejected — surfacing the free-slot scheduling logic to the user.
    auto_resolve = st.checkbox(
        "Auto-schedule around conflicts",
        help="If the chosen time clashes, move the task to the earliest free slot "
        "instead of rejecting it.",
    )

    if st.button("Add task", type="primary"):
        # Find the persisted Pet object the user selected.
        pet = next(p for p in owner.pets_owned if p.name == target_pet_name)
        repeat = None if repeat_choice == "One-off" else Repeat(repeat_choice.lower())
        activity = Activity(
            title=task_title,
            duration_minutes=int(duration),
            priority=priority,
            start=datetime.combine(task_date, task_time),
            repeat=repeat,
        )
        if auto_resolve:
            # auto_schedule slides the task to the first slot that fits. It
            # mutates activity.start in place, so remember the requested time
            # first to tell whether it actually had to move.
            requested_start = activity.start
            placed = owner.auto_schedule(pet, activity)
            if placed.start == requested_start:
                st.success(
                    f"Scheduled {task_title!r} for {pet.name} "
                    f"at {placed.start:%Y-%m-%d %H:%M}."
                )
            else:
                st.info(
                    f"⏱️ {task_title!r} clashed at {requested_start:%H:%M} — "
                    f"moved to the next free slot at {placed.start:%Y-%m-%d %H:%M}."
                )
        else:
            try:
                # schedule_activity validates ownership, wires the pet back-ref,
                # and books the calendar — raising ScheduleConflict on any overlap.
                owner.schedule_activity(pet, activity)
                st.success(
                    f"Scheduled {task_title!r} for {pet.name} "
                    f"at {activity.start:%Y-%m-%d %H:%M}."
                )
            except ScheduleConflict as clash:
                # A dedicated warning: the requested booking overlaps an existing
                # task and was NOT added. (Separate from the calendar-wide
                # conflict report shown lower down.)
                st.warning(
                    f"⚠️ **Scheduling conflict — {task_title!r} was not added.**\n\n"
                    f"{clash}\n\n"
                    "Pick a different time, or tick *Auto-schedule around "
                    "conflicts* to place it in the next free slot."
                )
            except ValueError as err:
                st.error(str(err))

st.divider()

st.subheader("Today's Schedule")

# --- Summary metrics ----------------------------------------------------
all_activities = owner.activities()
scheduled_count = sum(1 for a in all_activities if a.status is Status.SCHEDULED)
completed_count = sum(1 for a in all_activities if a.status is Status.COMPLETED)
conflicts = owner.find_conflicts()

mcol1, mcol2, mcol3, mcol4 = st.columns(4)
mcol1.metric("Total tasks", len(all_activities))
mcol2.metric("Scheduled", scheduled_count)
mcol3.metric("Completed", completed_count)
mcol4.metric("Conflicts", len(conflicts))

# --- Filters: by pet and by status --------------------------------------
fcol1, fcol2 = st.columns(2)
with fcol1:
    pet_filter = st.selectbox(
        "Filter by pet", ["All pets"] + [pet.name for pet in owner.pets_owned]
    )
with fcol2:
    status_filter = st.selectbox(
        "Filter by status", ["All"] + [s.value for s in Status]
    )

selected_pet = next(
    (p for p in owner.pets_owned if p.name == pet_filter), None
)
selected_status = None if status_filter == "All" else Status(status_filter)

# A one-shot message set when completing a task spawns its next instance.
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

# owner.activities() returns the matching rows already sorted by start time.
schedule = owner.activities(pet=selected_pet, status=selected_status)

if not schedule:
    st.info("Nothing matches. Add a task above or loosen the filters.")
else:
    st.caption("Sorted by start time. Tick **Done** to complete a task.")

    # Build one row per activity, preserving the backend's chronological order.
    table = pd.DataFrame(
        [
            {
                "Done": a.completed,
                "When": a.start,
                "Task": a.title,
                "Pet": a.pet.name if a.pet else "?",
                "Min": a.duration_minutes,
                "Priority": PRIORITY_BADGE.get(a.priority.lower(), a.priority),
                "Status": STATUS_BADGE.get(a.status, a.status.value),
                "Repeat": f"🔁 {a.repeat.value}" if a.repeat else "—",
            }
            for a in schedule
        ]
    )

    edited = st.data_editor(
        table,
        hide_index=True,
        width="stretch",
        # Only the Done checkbox is editable; the rest is read-only display.
        disabled=["When", "Task", "Pet", "Min", "Priority", "Status", "Repeat"],
        column_config={
            "Done": st.column_config.CheckboxColumn("Done", width="small"),
            "When": st.column_config.DatetimeColumn(
                "When", format="ddd MMM D, HH:mm", width="medium"
            ),
            "Task": st.column_config.TextColumn("Task", width="medium"),
            "Min": st.column_config.NumberColumn("Min", format="%d min"),
        },
        # Reset the editor's widget state when the filter changes.
        key=f"schedule_editor_{pet_filter}_{status_filter}",
    )

    # Detect a newly-ticked Done box and complete that activity. Row order in
    # `edited` matches `schedule`, so we can zip them positionally.
    for pos, activity in enumerate(schedule):
        newly_done = bool(edited.iloc[pos]["Done"]) and not activity.completed
        if newly_done and activity.pet is not None:
            # complete_activity returns the auto-created next instance (or None
            # for a one-off task / if the next slot is already taken).
            next_instance = activity.pet.complete_activity(activity)
            if next_instance is not None:
                st.session_state.flash = (
                    f"Completed {activity.title!r}. Next {activity.repeat.value} "
                    f"instance scheduled for {next_instance.start:%Y-%m-%d %H:%M}."
                )
            st.rerun()

# --- Calendar-wide conflict report --------------------------------------
# Distinct from the booking-time warning above: this flags overlaps already
# present on the calendar (e.g. created via auto-schedule edits or imports).
if conflicts:
    st.warning(f"⚠️ {len(conflicts)} scheduling conflict(s) on the calendar:")
    for first, second in conflicts:
        st.write(
            f"- {first.title!r} ({first.start:%H:%M}-{first.end:%H:%M}) "
            f"overlaps {second.title!r} ({second.start:%H:%M}-{second.end:%H:%M})"
        )
else:
    st.success("✅ No scheduling conflicts.")

st.divider()

# --- Debug: inspect the session "vault" ---------------------------------
# Streamlit reruns the whole script on every interaction. Anything stored in
# st.session_state survives those reruns; anything else is rebuilt each time.
# This panel shows what is currently living in the vault so you can watch
# state persist (or reset) as you click around.
with st.expander("🔍 Debug: session_state", expanded=False):
    st.caption(f"{len(st.session_state)} key(s) currently in the session vault.")

    if len(st.session_state) == 0:
        st.info("The vault is empty. Interact with the widgets above to populate it.")
    else:
        # A dict comprehension turns each stored value into a readable string,
        # since objects like Owner/Pet don't display cleanly on their own.
        st.write({key: repr(value) for key, value in st.session_state.items()})

    if st.button("Reset session (clear the vault)"):
        st.session_state.clear()
        st.rerun()
