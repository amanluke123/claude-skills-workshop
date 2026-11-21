# Lesson 2: The description is everything (25 min)

## Goal
Learn why a good skill sometimes never runs, and fix one.

## Why this matters
Claude picks a skill by reading its **description** only. If the description is vague, the skill is skipped, or loads at the wrong time. A good description has three parts:

1. **What it does** (one sentence)
2. **When to use it** ("Use when the user asks for ..."), with the words people actually say
3. **What it is NOT for** (near misses), so it stays quiet when it should

## Do this

**1. See the problem.** The repo has a skill that works but never triggers: `.claude/skills/notes-helper/SKILL.md`. Its description is:
> `Helps with notes.`

Restart Claude Code, then ask: **"Summarise sample-project/notes.md and list the action items."**
Did it use `notes-helper`? (Probably not, or not reliably.) The description gives Claude almost nothing to match.

**2. Fix it.** Rewrite the `description:` line. Use the three parts:
```
description: Turn meeting notes into a one-sentence summary, a list of decisions and a list of action items. Use when the user shares meeting notes, a standup, or asks "what were the actions/decisions". Not for emails, essays or general summarising of articles.
```
Keep it on ONE line. Do not change anything else.

**3. Check the format**
```
python scripts/validate_skill.py .claude/skills/notes-helper
```
It should now PASS with no "too vague" warning.

**4. Test again.** Restart Claude Code and try these four prompts. Write down which ones load the skill:
| Prompt | Should it load? |
|---|---|
| "What actions came out of sample-project/notes.md?" | yes |
| "Summarise the meeting notes in sample-project/notes.md" | yes |
| "Summarise this news article for me" | **no** |
| "Draft an email to the team about the delay" | **no** |

## Check
- [ ] Validator passes with no warnings
- [ ] Both "yes" prompts used the skill
- [ ] Both "no" prompts did NOT use it

## The rule of thumb
> Write the description for the **moment of choosing**, not for a manual. Use the words your user would really type, and say what is *not* included.

## If it doesn't work
- **Still not loading:** add more of the user's real words ("meeting", "notes", "action items", "decisions").
- **Loading too much** (even for emails): add or sharpen the "Not for ..." part.
- Peek: `solutions/02-notes-helper/SKILL.md`.
