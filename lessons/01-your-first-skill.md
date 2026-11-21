# Lesson 1: Your first skill (25 min)

## Goal
Build a skill called **explain-code** that explains a code file in plain language for a beginner.

## Do this

**1. Make the folder and file**
```
mkdir -p .claude/skills/explain-code
```
(On Windows PowerShell: `mkdir .claude\skills\explain-code`)

Create the file `.claude/skills/explain-code/SKILL.md`. Start from the template in `templates/SKILL.template.md`, or copy this and fill in the blanks:

```markdown
---
name: explain-code
description: Explain what a code file does in plain English for a beginner. Use when the user asks what a file, function or piece of code does, or asks for an explanation of code.
---

# Explain code

1. Read the file the user points at.
2. Start with ONE sentence: what the file is for.
3. Then explain each function in one plain sentence. No jargon.
4. End with one everyday analogy (like a recipe, a shop, a postal service).

Reply with only the explanation.
```

**2. Check the format**
```
python scripts/validate_skill.py .claude/skills/explain-code
```
Fix anything marked FAIL. (It tells you what is wrong in plain words.) A WARN about "what the skill is NOT for" is fine for now: you add that in Lesson 2.

**3. Restart Claude Code** (type `/exit`, then run `claude` again) so it notices the new skill.

**4. Use it.** Try both ways:
- Naturally: **"What does sample-project/grocery.py do?"**
- Directly: **`/explain-code sample-project/grocery.py`**

## Check
- [ ] The validator says PASS (one warning about "NOT for" is OK)
- [ ] Claude's answer starts with one sentence about the file
- [ ] There is one sentence per function (five functions)
- [ ] It ends with an everyday analogy

## Make it yours
Change step 4 to something else (for example "end with a one-line summary of what could go wrong"). Save, ask again. You just edited behaviour with plain English.

## If it doesn't work
- **Claude doesn't use it:** you probably didn't restart Claude Code, or the folder name doesn't match `name:`. Run the validator.
- **The answer ignores your format:** make the steps more specific and end with "Reply with ONLY ...".
- **Validator says the file is missing:** the file must be named exactly `SKILL.md` (capital letters).
- Stuck? Peek at `solutions/01-explain-code/SKILL.md`.
