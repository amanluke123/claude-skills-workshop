# Learn to build Claude Code skills

**A skill is a folder with a text file that teaches Claude how to do one job your way.**
You write plain English instructions once. Claude loads them automatically when your request matches. No coding needed for the basics.

You will build real skills in about 3 hours, one small step at a time.

## What you need
- [Claude Code](https://code.claude.com/docs) installed and signed in
- Git and Python 3.9+ (only for the checker script and one lesson)
- This repo, opened in your terminal: `cd claude-skills-workshop` then run `claude`

## The path (do them in order)
| # | Lesson | You will | Time |
|---|---|---|---|
| 0 | [What is a skill?](lessons/00-what-is-a-skill.md) | read, and look at a finished skill | 10 min |
| 1 | [Your first skill](lessons/01-your-first-skill.md) | build `explain-code` and see it work | 25 min |
| 2 | [The description is everything](lessons/02-description.md) | fix a skill that never triggers | 25 min |
| 3 | [Add a script](lessons/03-add-a-script.md) | let a script do the exact work | 25 min |
| 4 | [Add a reference file](lessons/04-add-a-reference.md) | keep the skill short and the details separate | 20 min |
| 5 | [Test it and improve it](lessons/05-test-and-improve.md) | check it triggers when it should and stays quiet when it shouldn't | 25 min |
| 6 | [Share it](lessons/06-share-it.md) | personal vs project skills, and git | 15 min |
| 7 | [Your own skill](lessons/07-your-own-skill.md) | build one for a task from your real work | 45 min |

One-page summary: [CHEATSHEET.md](CHEATSHEET.md). Stuck? Every lesson ends with "If it doesn't work", and finished versions are in [solutions/](solutions/) (try first, peek second).

## What is in this repo
- `lessons/` the steps
- `sample-project/` a tiny Python project your skills practise on
- `.claude/skills/` two ready-made skills: `commit-message` (a good one to study) and `notes-helper` (a broken one you fix in Lesson 2). Claude Code loads skills from here automatically.
- `templates/` a skill template and a test sheet
- `scripts/validate_skill.py` a checker that tells you what is wrong with a skill, in plain words
- `solutions/` finished versions of every lesson

## Check your work any time
```
python scripts/validate_skill.py .claude/skills/explain-code
```
