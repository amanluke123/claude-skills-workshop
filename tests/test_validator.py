import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from validate_skill import check


def skill(name, content, extra=None):
    d = Path(tempfile.mkdtemp()) / name
    d.mkdir()
    (d / "SKILL.md").write_text(content, encoding="utf-8")
    for rel, text in (extra or {}).items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(text)
    return d


GOOD = "---\nname: demo\ndescription: Explain things clearly in plain English. Use when the user asks what something does. Not for writing code.\n---\n\n1. Read it.\n2. Explain it.\n\nReply with only the explanation.\n"


class Validator(unittest.TestCase):
    def test_good_skill_passes_clean(self):
        self.assertEqual(check(skill("demo", GOOD)), ([], []))

    def test_missing_file(self):
        d = Path(tempfile.mkdtemp()) / "x"; d.mkdir()
        self.assertTrue(check(d)[0])

    def test_name_must_match_folder(self):
        f, _ = check(skill("other", GOOD))
        self.assertTrue(any("match the folder" in x for x in f))

    def test_bad_name_characters(self):
        f, _ = check(skill("Bad_Name", GOOD.replace("name: demo", "name: Bad_Name")))
        self.assertTrue(any("lowercase" in x for x in f))

    def test_missing_description(self):
        f, _ = check(skill("demo", "---\nname: demo\n---\n1. Do it.\n"))
        self.assertTrue(any("description" in x for x in f))

    def test_vague_description_warns(self):
        _, w = check(skill("demo", GOOD.replace(GOOD.split("description: ")[1].split("\n")[0], "Helps with notes.")))
        self.assertTrue(any("short" in x for x in w) and any("WHEN" in x for x in w))

    def test_placeholder_description_fails(self):
        f, _ = check(skill("demo", GOOD.replace("Explain things clearly in plain English.", "<What it does>.")))
        self.assertTrue(any("placeholder" in x for x in f))

    def test_missing_referenced_file_fails(self):
        f, _ = check(skill("demo", GOOD.replace("1. Read it.", "1. Run `scripts/run.py`.")))
        self.assertTrue(any("scripts/run.py" in x for x in f))
        f, _ = check(skill("demo", GOOD.replace("1. Read it.", "1. Run `scripts/run.py`."), {"scripts/run.py": "print(1)"}))
        self.assertEqual(f, [])

    def test_workshop_skills(self):
        # finished example is clean; the broken one is flagged
        self.assertEqual(check(ROOT / ".claude/skills/commit-message"), ([], []))
        self.assertTrue(check(ROOT / ".claude/skills/notes-helper")[1], "notes-helper should warn until fixed in Lesson 2")

    def test_every_solution_passes(self):
        for d in sorted((ROOT / "solutions").iterdir()):
            if d.is_dir():
                # solutions are named NN-skill; validate under their real skill name
                text = (d / "SKILL.md").read_text()
                real = text.split("name: ")[1].splitlines()[0].strip()
                tmp = Path(tempfile.mkdtemp()) / real
                import shutil
                shutil.copytree(d, tmp)
                self.assertEqual(check(tmp)[0], [], d.name)
                warns = check(tmp)[1]
                if d.name.startswith("01-"):          # Lesson 1 teaches the NOT-for clause later (Lesson 2)
                    self.assertTrue(all("NOT for" in w for w in warns), warns)
                else:
                    self.assertEqual(warns, [], d.name)

    def test_cli_exit_codes(self):
        ok = subprocess.run([sys.executable, str(ROOT / "scripts/validate_skill.py"), str(ROOT / ".claude/skills/commit-message")], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0)
        self.assertIn("PASS", ok.stdout)
        bad = subprocess.run([sys.executable, str(ROOT / "scripts/validate_skill.py"), str(ROOT / "templates")], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)


if __name__ == "__main__":
    unittest.main()
