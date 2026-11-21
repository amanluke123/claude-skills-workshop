# Lesson 5: Test it and improve it (25 min)

## Goal
Prove your skill triggers when it should and stays quiet when it shouldn't. Then improve it using evidence.

## Why
"It worked once" is not testing. Real skills fail in two ways:
- **Misses:** it should have triggered and didn't.
- **False alarms:** it triggered on something else.

A quick test sheet finds both.

## Do this

**1. Copy `templates/trigger-tests.md`** to `my-tests-explain-code.md` and fill in:
- **5 prompts that SHOULD trigger** `explain-code`. Vary the wording! For example: "what does this file do", "I don't understand grocery.py", "walk me through apply_coupon", ...
- **5 prompts that should NOT.** Include **near misses**: things that sound similar but are a different job. For example: "fix the bug in total_cost", "write tests for grocery.py", "add a docstring", "make this faster", "write a commit message".

**2. Run each prompt** in a fresh Claude Code session (type `/clear` between prompts), and mark whether `explain-code` loaded.

**3. Score it.** Goal: 9/10 or better.

**4. Improve ONE thing at a time, then re-run:**
- Missed a "should" prompt? Add the user's words to the description ("walk me through", "I don't understand").
- False alarm on a near miss? Add it to the "Not for ..." part ("Not for fixing bugs, writing tests or refactoring").
- The answer was right but formatted badly? Fix the instructions (step wording or the last "Reply with ONLY ..." line).

**5. Record before and after** at the bottom of your test sheet:
```
Before: 7/10  Change: added "walk me through, I don't understand" and "Not for fixing bugs..."  After: 9/10
```

## Check
- [ ] Test sheet with 5 + 5 prompts (at least 3 near misses)
- [ ] A score before and a score after
- [ ] You changed only one thing at a time

## The rule of thumb
> Fix the **description** when the skill loads at the wrong times. Fix the **instructions** when it loads but does the job badly.

## If it doesn't work
- **Results are inconsistent between runs:** that is normal. Run risky prompts twice and count it as a pass only if it works both times.
- **Can't think of near misses:** ask Claude: "give me 5 requests that sound like explaining code but are a different job".
