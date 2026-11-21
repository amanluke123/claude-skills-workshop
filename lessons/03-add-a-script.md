# Lesson 3: Add a script (25 min)

## Goal
Let a small script do the exact, repeatable work, so your skill is reliable.

## Why
Claude is great at explaining and writing. It is less reliable at counting or listing things exactly. If part of the job is **mechanical** (list every function, count lines, find all TODOs), put it in a **script** in the skill folder. Claude runs the script and uses the exact output.

```
.claude/skills/explain-code/
  SKILL.md
  scripts/
    list_functions.py      <- new
```

## Do this

**1. Create `.claude/skills/explain-code/scripts/list_functions.py`** with this content:
```python
"""Print every function in a Python file with its line number and first docstring line."""
import ast
import sys

path = sys.argv[1]
tree = ast.parse(open(path, encoding="utf-8").read())
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        doc = (ast.get_docstring(node) or "(no docstring)").splitlines()[0]
        print(f"line {node.lineno}: {node.name}() - {doc}")
```
Test it yourself first:
```
python .claude/skills/explain-code/scripts/list_functions.py sample-project/grocery.py
```
You should see five lines, one per function.

**2. Tell the skill to use it.** Edit `SKILL.md` so the steps start like this:
```markdown
1. Run `python .claude/skills/explain-code/scripts/list_functions.py <file>` to get the exact list of functions.
2. Read the file the user points at.
3. Start with ONE sentence: what the file is for.
4. Then explain each function from the list in one plain sentence. Do not skip any.
5. End with one everyday analogy.
```

**3. Check, restart, try:** `python scripts/validate_skill.py .claude/skills/explain-code`, restart Claude Code, then **"explain sample-project/grocery.py"**.

## Check
- [ ] The validator passes (it also checks that the script path you mention exists)
- [ ] Claude runs the script (you will see it in the activity)
- [ ] Every function is explained: none missing, none invented

## The rule of thumb
> If you could write it as code and it must be exactly right every time, put it in a script. Keep the **explaining and judging** in the instructions.

## If it doesn't work
- **Claude didn't run it:** make step 1 an explicit command in backticks, as above.
- **"python not found":** try `python3` in the command, in both the lesson and your SKILL.md.
- Peek: `solutions/03-explain-code-with-script/`.
