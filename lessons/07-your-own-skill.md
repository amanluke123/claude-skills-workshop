# Lesson 7: Your own skill (45 min)

## Goal
Build a skill for something **you** do repeatedly at work.

## Do this

**1. Pick the job (5 min).** Good candidates: something you explain or format the same way often.
- a report, status update or email in a fixed shape
- reviewing something against a checklist
- turning raw material into a standard format (notes, tickets, logs)
- a project convention ("how we name branches", "how we write release notes")

Pick **one small, clear job**. If it takes more than one sentence to describe, it is probably two skills.

**2. Fill in this before you write anything (5 min):**
- The job in one sentence: ____
- 3 things a user might type to ask for it: ____
- 2 similar-sounding jobs it should NOT do: ____
- What does a perfect answer look like? (paste an example)

**3. Write the skill (15 min).** Use `templates/SKILL.template.md`. Description first (what / when / not for), then the shortest steps that work. End with "Reply with ONLY ...".

**4. Make it robust (10 min).** Ask yourself:
- Is part of it **mechanical**? Move that to `scripts/` (Lesson 3).
- Is there **long detail** (a style guide, a template)? Move it to `references/` (Lesson 4).

**5. Test it (10 min).** Make a trigger test sheet (Lesson 5): 5 should + 5 should-not (with near misses). Aim for 9/10.

## Check (your finished skill)
- [ ] `python scripts/validate_skill.py <your skill folder>` passes with no warnings
- [ ] Description says what it does, when to use it, and what it is NOT for
- [ ] `SKILL.md` is short (under about 40 lines)
- [ ] Test sheet scores 9/10 or better
- [ ] A colleague used it successfully
- [ ] No secrets in the folder

## Show and tell
Present your skill in 3 minutes: the job, the description you wrote, one prompt that triggers it, one near miss that doesn't, and one thing you changed after testing.

## If it doesn't work
Go back to the lesson for the symptom: not triggering -> Lesson 2. Wrong answers -> Lessons 3-4. Inconsistent -> Lesson 5.
