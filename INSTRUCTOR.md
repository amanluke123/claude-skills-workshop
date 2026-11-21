# Instructor notes (about 3 hours, individual work)
| Time | Do |
|---|---|
| 0:00 | Lesson 0 together: show `commit-message` working live (stage a change, ask "write me a commit message"). |
| 0:15 | Lesson 1: everyone builds `explain-code`. Walk the room; the usual problem is "didn't restart Claude Code". |
| 0:45 | Lesson 2: the "aha" lesson. Let them see `notes-helper` fail first, then fix the description. |
| 1:15 | Break |
| 1:30 | Lessons 3-4 (script, then reference). Windows users may need `python` vs `python3` or `py`. |
| 2:00 | Lesson 5: test sheets. Pair up so each person writes near-miss prompts for the other's skill. |
| 2:25 | Lesson 6, then Lesson 7 (own skill) with a 3-minute show-and-tell each. |

## Common problems
- **Skill not picked up:** Claude Code not restarted, wrong folder (`.claude/skills/<name>/SKILL.md`), or `name` differs from the folder. `python scripts/validate_skill.py <folder>` finds all three.
- **Skill loads on everything:** description too broad; add "Not for ...".
- **Skill never loads:** description missing the words people really type.
- **Long SKILL.md:** push detail into `references/`.

## Success looks like
Everyone leaves with: a working `explain-code` (script + reference), a fixed `notes-helper`, a test sheet scoring 9/10, and one skill for their own work.

## Not covered on purpose (a good Day-2 follow-up)
Advanced frontmatter options, skills that take arguments, skills that call other tools or run in a separate context, and plugin packaging. See the official docs: https://code.claude.com/docs
