"""Check a Claude Code skill folder and explain any problem in plain words.
Usage: python scripts/validate_skill.py .claude/skills/my-skill
Exit code: 0 = PASS (maybe with warnings), 1 = FAIL."""
import re
import sys
from pathlib import Path


def check(folder):
    folder = Path(folder)
    fails, warns = [], []
    f = folder / "SKILL.md"
    if not f.is_file():
        return [f"There is no file called SKILL.md in {folder} (it must be exactly SKILL.md, capital letters)."], []
    text = f.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return ["SKILL.md must start with a line of three dashes (---), then name and description, then another --- line."], []
    meta = dict(re.findall(r"^([\w-]+):[ \t]*(.*)$", m.group(1), re.M))
    body = m.group(2).strip()

    name = meta.get("name", "").strip()
    if not name:
        fails.append("Missing 'name:' at the top. Add a line like  name: my-skill")
    else:
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
            fails.append(f"The name '{name}' should use only lowercase letters, numbers and single hyphens (like explain-code).")
        if len(name) > 64:
            fails.append("The name is longer than 64 characters. Shorten it.")
        if name != folder.resolve().name:
            fails.append(f"The name '{name}' must match the folder name '{folder.resolve().name}'. Rename one so they are the same.")

    desc = meta.get("description", "").strip()
    if not desc:
        fails.append("Missing 'description:' (or it is empty / spread over several lines). Put it on ONE line: what it does, when to use it, what it is not for.")
    else:
        if len(desc) > 1024:
            fails.append("The description is over 1024 characters. Shorten it.")
        if re.search(r"<[^>]+>", desc):
            fails.append("The description still has <placeholder text in angle brackets>. Replace it with real words.")
        words = len(desc.split())
        if words < 10:
            warns.append(f"The description is very short ({words} words), so Claude has little to match. Say what it does AND when to use it.")
        if not re.search(r"\b(use when|use this when|use for|when the user|when asked|when you)\b", desc, re.I):
            warns.append("The description doesn't say WHEN to use the skill. Add a sentence like: 'Use when the user asks for ...'.")
        if not re.search(r"\bnot for\b|\bnot when\b|\bdo not use\b|\bdon't use\b", desc, re.I):
            warns.append("The description doesn't say what the skill is NOT for. Add 'Not for ...' (near misses) so it stays quiet when it shouldn't run.")

    if not body:
        fails.append("The instructions below the --- lines are empty. Add numbered steps.")
    else:
        n = len(body.splitlines())
        if n > 500:
            fails.append(f"SKILL.md body is {n} lines. Keep it well under 500; move detail to references/.")
        elif n > 60:
            warns.append(f"SKILL.md body is {n} lines. Shorter is better: move long detail into references/.")
        if not re.search(r"^\s*\d+\.\s", body, re.M):
            warns.append("The instructions have no numbered steps. Steps (1. 2. 3.) are easier for Claude to follow.")
        if not re.search(r"reply with|respond with|output only|answer with", body, re.I):
            warns.append("Say what the final answer should look like, e.g. 'Reply with ONLY the commit message.'")
        # files mentioned in the instructions must exist
        for ref in sorted(set(re.findall(r"[\w./-]*\b((?:scripts|references)/[\w.\-/]+)", body))):
            ref = ref.rstrip(".,)`'\"")
            if not (folder / ref).exists():
                fails.append(f"The instructions mention '{ref}' but that file does not exist inside {folder.name}/.")
    return fails, warns


def main():
    if len(sys.argv) != 2:
        print(__doc__); return 2
    fails, warns = check(sys.argv[1])
    for x in fails:
        print("  FAIL  " + x)
    for x in warns:
        print("  WARN  " + x)
    print("RESULT: " + ("FAIL" if fails else "PASS" + (f" with {len(warns)} warning(s)" if warns else " (no warnings)")))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
