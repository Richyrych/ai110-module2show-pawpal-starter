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

I used Claude Code at every level.  Starting with the UML diagram, this informed the structure or at least the starting point.  From there I paraphrased each instruction from the prompt and assked Claude to explain anything I was not familiar with.  For example, I did not know how Streamlit handled state, and why if the data was recorded in the session anyway, it was built to re-run the entire app with each interaaction.  Claude said that Streamlit was built for data scientists, and that makes sense becasue stale data would be the worst thing to have.  I used Claude to generate and run tests, to build algorithmic features, and to look for bugs.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

Claude wanted to build a .venv and install pytest.  I know I have all that set up already, so I had to broaden the scope and let it look a level above the project.  If I hadn't been reading what Claude was sayingf in the context window, I would have missed it.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

I tested the happy path for using adding pets, scheduling activities, and such.  I then tested edge cases, which I sougth Claude's advice for.  I tested for overlapping activities as well as zero-time duration activities.  These tests are important because the app is only as good as the edge cases in how resilient it is, and for an app that re-renders it can crash if errors are nto handled properly

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

I am 4/5 confident- I wish I was 5/5, but I am still learning and if i wasn't using AI I would not have been able to build this app.  So a lot of it is still over my head.

Next time I would test a wider range of edge cases with Extremely large numbers, negative numbers, infinity, incorrect data types, the usual list.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?
The actual building went really smooth, I think becasue of the quality of the instructions.  I also learned more about how Python methods and tests work.

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?
I would spend more time on the UI to make the app look  really nice and more feature-rich

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

I learned to separate concerns with the AI.  My instinct might have been to instruct several commands into  one prompt but now I am more inclined to prompt one thing at a time.  Similarly, using separate context windows (instances of Claude), for UI vs backend logic, is not something I would have thought to do, but in hindsight it makes total sense.