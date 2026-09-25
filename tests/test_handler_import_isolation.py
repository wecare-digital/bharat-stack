"""No test module may bind a bare `handler` at import time.

Why this file exists
--------------------
This repo has 64 files called `handler.py`, one per Lambda, and they are imported in
tests by putting the function's directory on `sys.path` and importing `handler`. That
makes `sys.modules["handler"]` a single slot contended by 64 different modules.

`conftest.isolate_handler_imports` mitigates it, but only partly. It is **function
scoped**, so it clears the slot between tests - which covers an import performed inside a
fixture or a test body. It cannot cover a module-level `import handler`, because that runs
at collection time, before any fixture exists.

The failure mode is the dangerous kind: nothing raises. The test module simply binds a
different Lambda's handler and goes on to assert against it. Depending on collection
order the assertions either fail for an incomprehensible reason or - worse - pass while
testing the wrong code.

This already happened twice in this repo:

* `test_secure_files.py` bound `messaging/outbound-whatsapp/handler.py` in the full suite
  and 20 tests failed on AttributeError, while the file passed when run alone. CI runs the
  full suite, so it was red there and green locally.
* `test_plivo_cdr_normalisation.py` had a module-level `import handler as plivo` that
  happened to resolve correctly only because of where it fell in collection order.

Both now load by path under a unique module name. This test stops a third one appearing,
which a code review would not reliably catch - the unsafe line looks completely ordinary.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

TESTS_DIR = pathlib.Path(__file__).resolve().parent

TEST_FILES = sorted(TESTS_DIR.glob("test_*.py"))


def _module_level_handler_imports(tree: ast.Module) -> list[str]:
    """Bare `handler` imports at module scope only.

    Walks direct children of the module body rather than using `ast.walk`, because an
    import nested inside a function or class is exactly the case that IS protected by the
    conftest fixture and must not be flagged.
    """
    offenders = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "handler" or alias.name.startswith("handler."):
                    offenders.append(f"line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and (
                node.module == "handler" or node.module.startswith("handler.")
            ):
                offenders.append(f"line {node.lineno}: from {node.module} import ...")
    return offenders


def test_there_are_test_files_to_check():
    """Guards the guard. A glob that silently matches nothing would make every
    assertion below vacuously true."""
    assert len(TEST_FILES) > 50


@pytest.mark.parametrize("path", TEST_FILES, ids=lambda p: p.name)
def test_no_module_level_bare_handler_import(path: pathlib.Path):
    tree = ast.parse(path.read_text(), filename=str(path))
    offenders = _module_level_handler_imports(tree)
    assert not offenders, (
        f"{path.name} imports a bare `handler` at module scope: {offenders}. "
        "Collection order decides which of this repo's 64 handler.py files that "
        "resolves to, and the wrong one binds silently. Load it by path instead:\n"
        '    spec = importlib.util.spec_from_file_location("wecare_<fn>_handler", FN / "handler.py")\n'
        "    module = importlib.util.module_from_spec(spec)\n"
        '    sys.modules["wecare_<fn>_handler"] = module\n'
        "    spec.loader.exec_module(module)"
    )
