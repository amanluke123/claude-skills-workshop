# Lesson 4: Add a reference file (20 min)

## Goal
Keep `SKILL.md` short by moving long details into a separate file that Claude reads only when needed.

## Why
`SKILL.md` is loaded whenever the skill triggers. If it is long, you waste Claude's attention every time. Put **short steps** in `SKILL.md` and the **long details** (style guides, templates, examples) in `references/`. Claude opens them only when a step says to.

```
.claude/skills/explain-code/
  SKILL.md             <- stays short
  scripts/list_functions.py
  references/style.md  <- new: the detail
```

## Do this

**1. Create `.claude/skills/explain-code/references/style.md`:**
```markdown
# Explanation style guide
- Write for someone who has never programmed. No jargon: say "a saved list" not "data structure".
- One sentence per function. Start with a verb: "Adds ...", "Works out ...", "Finds ...".
- Good analogies: recipes (steps), shops (buying/selling), post offices (sending things), libraries (storing things).
- Bad analogies: anything that needs technical knowledge to understand.
- If a function can fail or surprise you (empty list, division, rounding), add: "Watch out: ..."
- Never explain code that was not in the file.
```

**2. Point to it from `SKILL.md`** (replace steps 3-5 with):
```markdown
3. Read `.claude/skills/explain-code/references/style.md` and follow it.
4. Write the explanation: one sentence on the file, one sentence per function from the list, then one analogy.
```
Your `SKILL.md` should now be about 10-15 lines.

**3. Check and try:** validate, restart Claude Code, ask **"explain sample-project/grocery.py"**.

## Check
- [ ] Validator passes (it confirms `references/style.md` exists)
- [ ] The explanation avoids jargon and starts each function with a verb
- [ ] `cheapest` includes a "Watch out" about empty lists

## The rule of thumb
> `SKILL.md` = the recipe card. `references/` = the cookbook on the shelf. Don't paste the cookbook onto the card.

## If it doesn't work
- **Claude ignored the style guide:** make sure a numbered step says to read it, with the exact path.
- Peek: `solutions/04-explain-code-with-reference/`.
