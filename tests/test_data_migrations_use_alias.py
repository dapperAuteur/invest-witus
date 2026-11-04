"""Every data step in a migration must use the database being migrated.

The migrate workflow runs `manage.py migrate --database direct` with no DATABASE_URL, so the
"default" alias is an empty SQLite file there. A RunPython function that reads `Model.objects`
without `.using(schema_editor.connection.alias)` hits that file and fails (2026-11-04, migration
methods 0006). This test reads every migration's source and refuses a RunPython function that
never names the alias.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "invest_witus_site"


def _run_python_functions(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "RunPython"
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            names.add(node.args[0].id)
    return names


def test_every_run_python_step_uses_the_migrated_database() -> None:
    offenders: list[str] = []
    for path in sorted(SRC.glob("*/migrations/[0-9]*.py")):
        tree = ast.parse(path.read_text())
        wanted = _run_python_functions(tree)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in wanted:
                body = ast.get_source_segment(path.read_text(), node) or ""
                if "connection.alias" not in body:
                    offenders.append(f"{path.relative_to(SRC)}:{node.name}")
    assert offenders == [], f"RunPython steps not using schema_editor.connection.alias: {offenders}"
