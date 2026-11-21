# Lesson 0: What is a skill? (10 min)

## The idea
Imagine you hire a helpful new colleague. Every time you want a report written *your* way, you have to explain the format again. A **skill** is you writing that explanation down once, in a folder, so Claude reads it automatically whenever it is needed.

## What a skill looks like
A skill is just a folder with a file called `SKILL.md`:

```
.claude/skills/commit-message/
  SKILL.md
```

`SKILL.md` has two parts:

```markdown
---
name: commit-message                      <- the skill's name (same as the folder)
description: Write a git commit message for the staged changes. Use when the user asks for a commit message...   <- WHEN to use it
---

# Commit message writer                   <- the instructions (plain English)
1. Run `git diff --staged` ...
```

- The top part (between the `---` lines) is the **name** and **description**.
- Below it are the **instructions**: steps Claude follows.

## How Claude uses it
1. At the start, Claude sees only every skill's **name and description** (a short list).
2. When your request matches a description, Claude **loads the instructions** and follows them.
3. You can also call a skill yourself by typing `/commit-message`.

That is why the **description is the most important line you write**. It is how Claude decides.

## Try it: look at a finished skill
Open `.claude/skills/commit-message/SKILL.md` and read it. It is short. Notice:
- The description says what it does, **when to use it**, and what it is **not** for.
- The steps are numbered and concrete.
- The last line says exactly what the answer should look like.

Now see it work:
1. In a terminal in this repo, run `claude`.
2. Make a tiny change: add a blank comment line to `sample-project/grocery.py`, then run `git add sample-project/grocery.py` in another terminal.
3. Ask Claude: **"write me a commit message"**.

## Check
Claude should run `git diff --staged` and reply with just a short commit message. You just used a skill!

## If it doesn't work
- Nothing staged? Claude will tell you. Run `git add` first.
- Claude didn't use the skill? Ask again with `/commit-message`. (We will fix "didn't trigger" in Lesson 2.)
- Make sure you started `claude` from inside this repo folder, so it can see `.claude/skills/`.
