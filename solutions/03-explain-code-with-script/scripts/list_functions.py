"""Print every function in a Python file with its line number and first docstring line."""
import ast
import sys

path = sys.argv[1]
tree = ast.parse(open(path, encoding="utf-8").read())
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        doc = (ast.get_docstring(node) or "(no docstring)").splitlines()[0]
        print(f"line {node.lineno}: {node.name}() - {doc}")
