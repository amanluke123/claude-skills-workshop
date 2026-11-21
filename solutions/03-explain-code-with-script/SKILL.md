---
name: explain-code
description: Explain what a code file does in plain English for a beginner. Use when the user asks what a file, function or piece of code does, or asks for an explanation of code. Not for fixing bugs, writing tests or refactoring.
---

# Explain code

1. Run `python .claude/skills/explain-code/scripts/list_functions.py <file>` to get the exact list of functions.
2. Read the file the user points at.
3. Start with ONE sentence: what the file is for.
4. Then explain each function from the list in one plain sentence. Do not skip any.
5. End with one everyday analogy (like a recipe, a shop, a postal service).

Reply with only the explanation.
