# Skills cheat sheet

**Where skills live**
| Place | Folder | Who gets it |
|---|---|---|
| This project | `.claude/skills/<name>/SKILL.md` | everyone who clones the repo |
| Just you | `~/.claude/skills/<name>/SKILL.md` | you, in every project |

**Smallest possible skill**
```
.claude/skills/my-skill/
  SKILL.md
```
```markdown
---
name: my-skill
description: What it does. Use when the user asks for X, Y or Z. Not for W.
---

# My skill
1. First do this.
2. Then do that.
3. Reply with ONLY the result.
```

**Optional extras (a skill folder can grow)**
```
my-skill/
  SKILL.md          short instructions (the only required file)
  scripts/          code for exact, repeatable work
  references/       longer notes Claude reads only when needed
```

**The rules that matter**
1. `name` = the folder name: lowercase letters, numbers, hyphens.
2. **The description decides when the skill loads.** Say what it does AND when to use it. Add what it is NOT for.
3. Keep `SKILL.md` short (a page or two). Move long detail to `references/`.
4. Put exact, repeatable work in `scripts/`, not in prose.
5. Write instructions as steps. Say what the final answer should look like.
6. Test with real prompts: some that should trigger it, some that should not.

**Use a skill**
- Just ask naturally: Claude loads it when your request matches the description.
- Or type `/name` to call it directly.

**Check it**: `python scripts/validate_skill.py .claude/skills/my-skill`
