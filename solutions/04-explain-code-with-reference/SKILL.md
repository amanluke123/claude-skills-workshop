---
name: explain-code
description: Explain what a code file does in plain English for a beginner. Use when the user asks what a file, function or piece of code does, or asks for an explanation of code. Not for fixing bugs, writing tests or refactoring.
---

# Explain code

1. Run `python .claude/skills/explain-code/scripts/list_functions.py <file>` to get the exact list of functions.
2. Read the file the user points at.
3. Read `.claude/skills/explain-code/references/style.md` and follow it.
4. Write the explanation: one sentence on the file, one sentence per function from the list, then one analogy.

Reply with only the explanation.
