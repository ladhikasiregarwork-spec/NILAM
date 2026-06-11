"""Guard: the orchestrator must not import ocr_match (single front door is HTTP).

Uses the AST so prose mentions of ``ocr_match`` in comments/docstrings (e.g.
matching.py's "imports nothing from ocr_match") don't trip a false positive — only
real ``import``/``from`` statements count.
"""
import ast
import pathlib
import unittest

_PKG = pathlib.Path(__file__).resolve().parent.parent


def _imports_ocr_match(source: str) -> bool:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            if any(a.name == "ocr_match" or a.name.startswith("ocr_match.")
                   for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "ocr_match" or mod.startswith("ocr_match."):
                return True
    return False


class TestNoOcrMatchImport(unittest.TestCase):
    def test_no_ocr_match_imports(self):
        offenders = [
            str(path.relative_to(_PKG))
            for path in _PKG.rglob("*.py")
            if "tests" not in path.parts
            and _imports_ocr_match(path.read_text(encoding="utf-8"))
        ]
        self.assertEqual(offenders, [], f"ocr_match imported in: {offenders}")


if __name__ == "__main__":
    unittest.main()
