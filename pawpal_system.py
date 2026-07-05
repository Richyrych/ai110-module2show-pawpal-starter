"""PawPal+ — class skeleton generated from diagrams/uml.md.

Owner, Pet, Activity, and Calendar model a simple pet-activity scheduler.
Relationships (from the UML):
    Owner  "1" --> "*" Pet       : owns
    Pet    "1" --> "*" Activity  : has scheduled
    Owner  "1" --> "1" Calendar  : views / manages
    Calendar "1" o-- "*" Activity : contains
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Activity:
    """A single scheduled activity for a pet (e.g. walk, vet visit, feeding)."""

    title: str
    duration_minutes: int
    priority: str
    timeslot: str
    completed: bool = False

    def mark_complete(self) -> None:
        """Mark this activity as completed."""
        ...


@dataclass
class Pet:
    """A pet owned by an Owner, with a list of scheduled activities."""

    name: str
    owned_by: "Owner"
    breed: str
    sex: str
    activities_scheduled: List[Activity] = field(default_factory=list)

    def complete_activity(self, activity: Activity) -> None:
        """Mark one of this pet's activities complete."""
        ...


@dataclass
class Calendar:
    """Holds all pet activities and the timeslots available for scheduling."""

    pet_activity: List[Activity] = field(default_factory=list)
    available_timeslots: List[str] = field(default_factory=list)

    def add_pet_activity(self, activity: Activity) -> None:
        """Add an activity to the calendar."""
        ...

    def edit_pet_activity(self, activity: Activity) -> None:
        """Edit an existing activity on the calendar."""
        ...

    def remove_pet_activity(self, activity: Activity) -> None:
        """Remove an activity from the calendar."""
        ...


@dataclass
class Owner:
    """A pet owner who manages pets, their activities, and a calendar."""

    name: str
    pets_owned: List[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner's list of pets."""
        ...

    def schedule_activity(self, pet: Pet, activity: Activity) -> None:
        """Schedule an activity for one of this owner's pets."""
        ...

    def view_calendar(self) -> Calendar:
        """Return the owner's calendar."""
        ...

    def edit_pet(self, pet: Pet) -> None:
        """Edit details of one of this owner's pets."""
        ...

    def edit_schedule(self, activity: Activity) -> None:
        """Edit a scheduled activity."""
        ...
