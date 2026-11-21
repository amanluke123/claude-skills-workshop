# Lesson 6: Share it (15 min)

## Goal
Know where to put a skill so the right people get it, and share yours.

## Two homes
| Home | Folder | Who gets it | Use for |
|---|---|---|---|
| **Project skill** | `.claude/skills/<name>/` inside the repo | everyone who clones that repo | team rules: commit style, how we review, our report format |
| **Personal skill** | `~/.claude/skills/<name>/` (your home folder) | only you, in every project | your own habits and shortcuts |

(On Windows, `~` is `C:\Users\<you>`.)

## Do this

**1. Make `explain-code` a personal skill.** Copy the whole folder:
```
cp -r .claude/skills/explain-code ~/.claude/skills/
```
(On Windows PowerShell: `Copy-Item -Recurse .claude\skills\explain-code $HOME\.claude\skills\`)
Open a different project folder, run `claude`, and ask "explain this file". Your skill works there too.

**2. Share the project version with git.** In this repo:
```
git add .claude/skills/explain-code
git commit -m "Add explain-code skill"
```
Anyone who clones the repo and starts Claude Code now has it.

**3. Write a tiny README** for your skill (`.claude/skills/explain-code/README.md`, 5 lines): what it does, example prompts, what it needs (Python), and who to ask. Future-you will thank you.

**4. Try the "colleague test".** Ask a neighbour to use your skill with only your README. If they get stuck, improve the README (or the description).

## Check
- [ ] The skill works in a second project (personal copy)
- [ ] The skill is committed in this repo
- [ ] A colleague used it from the README alone

## Good habits
- One job per skill. If a skill does three things, make three skills.
- Name skills by the job: `explain-code`, `commit-message`, not `helper`.
- Never put passwords or keys in a skill. Skills are plain text and get shared.
- Review someone else's skill before installing it: it is instructions your Claude will follow, and may run scripts.

## If it doesn't work
- **Not found in the other project:** check the folder is `~/.claude/skills/explain-code/SKILL.md` (not nested one level deeper). Restart Claude Code.
