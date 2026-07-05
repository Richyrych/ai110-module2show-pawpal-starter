# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?

Three Core Actions:
    1. Add pet
    2. Schedule activity
    3. View Calendar

Objects:
    1. Owner
        attributes: a. pets_owned

        actions:    a. add pet
                    b. schedule activity
                    c. view calendar
                    d. edit pets, activity schedule             

    2. Pet
        attributes: a. owned_by
                    b. activities_scheduled
                    c. breed
                    d. sex

        actions:    a. complete_activity

    3. Calendar
        attributes: a. pet_activity
                    b. available_timeslots

        actions:    a. add_pet_activity
                    b. edit_pet_activity
                    c. remove_pet_activity

**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?
I decided to use an int value for the time instead of a string.  It was difficult to parse it out each itme and to make duration anything other than the predefined string values for whole or half hours.  This required most of the methods around scheduling to be rewritten, but it allowed for more robust sorting, filtering, and conflict resolution
---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
