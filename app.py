from datetime import date, datetime, time

import streamlit as st

from pawpal_system import Activity, Owner, Pet, Repeat, Status

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to the PawPal+ starter app.

This file is intentionally thin. It gives you a working Streamlit app so you can start quickly,
but **it does not implement the project logic**. Your job is to design the system and build it.

Use this app as your interactive demo once your backend classes/functions exist.
"""
)

with st.expander("Scenario", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.

You will design and implement the scheduling logic and connect it to this Streamlit UI.
"""
    )

with st.expander("What you need to build", expanded=True):
    st.markdown(
        """
At minimum, your system should:
- Represent pet care tasks (what needs to happen, how long it takes, priority)
- Represent the pet and the owner (basic info and preferences)
- Build a plan/schedule for a day that chooses and orders tasks based on constraints
- Explain the plan (why each task was chosen and when it happens)
"""
    )

st.divider()

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
        st.rerun()

if owner.pets_owned:
    st.write("Current pets:")
    st.table(
        [
            {"name": pet.name, "breed": pet.breed, "sex": pet.sex,
             "activities": len(pet.activities)}
            for pet in owner.pets_owned
        ]
    )
else:
    st.info("No pets yet. Add one above.")

st.divider()

st.subheader("Tasks")
st.caption("Schedule an Activity for a pet. Pick any time — overlapping tasks are rejected.")

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

    if st.button("Add task"):
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
        try:
            # schedule_activity validates ownership, wires the pet back-ref, and
            # books the calendar — raising ScheduleConflict on any time overlap.
            owner.schedule_activity(pet, activity)
            st.success(
                f"Scheduled {task_title!r} for {pet.name} "
                f"at {activity.start:%Y-%m-%d %H:%M}."
            )
            st.rerun()
        except ValueError as err:
            st.error(str(err))

st.divider()

st.subheader("Today's Schedule")

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

schedule = owner.activities(pet=selected_pet, status=selected_status)

if not schedule:
    st.info("Nothing matches. Add a task above or loosen the filters.")
else:
    for activity in schedule:
        pet_label = activity.pet.name if activity.pet else "?"
        repeat_tag = f" 🔁 {activity.repeat.value}" if activity.repeat else ""
        label = (
            f"{activity.start:%m-%d %H:%M}  {activity.title} — {pet_label} "
            f"({activity.duration_minutes} min, {activity.priority} priority){repeat_tag}"
        )
        # Checking the box marks the Activity complete via the backend.
        done = st.checkbox(
            label,
            value=activity.completed,
            # id() is stable for the lifetime of the persisted object,
            # giving each activity a unique, rerun-safe widget key.
            key=f"done_{id(activity)}",
            disabled=activity.completed,
        )
        if done and not activity.completed:
            # complete_activity returns the auto-created next instance (or None
            # for a one-off task / if the next slot is already taken).
            next_instance = activity.pet.complete_activity(activity)
            if next_instance is not None:
                st.session_state.flash = (
                    f"Completed {activity.title!r}. Next {activity.repeat.value} "
                    f"instance scheduled for {next_instance.start:%Y-%m-%d %H:%M}."
                )
            st.rerun()

# --- Conflicts ----------------------------------------------------------
conflicts = owner.find_conflicts()
if conflicts:
    st.warning("⚠️ Scheduling conflicts detected:")
    for first, second in conflicts:
        st.write(
            f"- {first.title!r} ({first.start:%H:%M}-{first.end:%H:%M}) "
            f"overlaps {second.title!r} ({second.start:%H:%M}-{second.end:%H:%M})"
        )

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
