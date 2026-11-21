---
name: commit-message
description: Write a git commit message for the currently staged changes. Use when the user asks for a commit message, or says "commit this" or "what should I write for this commit". Not for pull request descriptions, code review, or release notes.
---

# Commit message writer

1. Run `git diff --staged` to see exactly what is staged. If nothing is staged, say so and stop.
2. Write the message in this shape:
   - Line 1: a summary of 50 characters or fewer, in the imperative ("Add", "Fix", not "Added").
   - A blank line.
   - 1-3 short lines saying WHY the change was made, if it is not obvious.
3. Reply with ONLY the commit message, ready to copy. No introduction.
