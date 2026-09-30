"""The two service-api copies must diverge only where the divergence is the point.

`amplify/functions/core/service-api/handler.py` and
`amplify/functions/messaging/whatsapp-business-api/service_api.py` are near-copies of one
another - roughly 1000 lines of the same order, document, FAQ, appointment, rx-slot,
enterprise-assist and review logic. That is a maintenance hazard with a proven cost: the
unconditional `put_item` that silently replaced an existing order had to be fixed in BOTH,
and finding the second copy was luck rather than process.

What this test exists to stop
-----------------------------
The two copies had drifted on **authentication**. The `core/service-api` router calls
`require_auth`; the `service_api.py` router did not. That was latent rather than live - the
Lambda's configured entry point is `handler.handler`, which imports 35 named functions from
`service_api` and never its router, so the unguarded copy was unreachable - but it was a trap
of a specific kind: a dead function that looks exactly like a live entry point is what
somebody wires up later, inheriting the gap along with it.

So the unguarded router was deleted, and the rule is now asserted in both directions:

  service_api.py            is a LIBRARY  -> must define no `handler` at all
  core/service-api/handler  is an ENTRY POINT -> must define `handler`, and it must
                                                authenticate before dispatching

A test that only checked "both routers call require_auth" would have been satisfied by
copying the guard into dead code, which is the worse fix.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FUNCTIONS = ROOT / "amplify" / "functions"

LIBRARY = FUNCTIONS / "messaging" / "whatsapp-business-api" / "service_api.py"
ENTRY_POINT = FUNCTIONS / "core" / "service-api" / "handler.py"
IMPORTER = FUNCTIONS / "messaging" / "whatsapp-business-api" / "handler.py"


def top_level_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def imported_from_service_api(path: Path) -> set[str]:
    """Names `handler.py` pulls out of `service_api`, resolved from the AST."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "service_api":
            names.update(alias.name for alias in node.names)
    return names


def test_the_library_copy_defines_no_entry_point():
    """`service_api.py` is imported, never invoked. A `handler` there is dead by
    construction - the Lambda's configured entry point is `handler.handler` - and a dead
    entry point is the thing that drifts out of sync unnoticed."""
    assert "handler" not in top_level_functions(LIBRARY), (
        "service_api.py has regained a `handler`. It is not an entry point: this Lambda is "
        "configured as `handler.handler`. Delete it rather than adding auth to it - a dead "
        "router that looks live is how the authentication gap got in."
    )


def test_the_real_entry_point_authenticates_before_dispatching():
    """The live router must guard, and must guard BEFORE routing.

    Order matters and is checked rather than assumed: a `require_auth` call that sits after
    the dispatch block would satisfy a naive "does it call require_auth" test while leaving
    every route open.
    """
    source = ENTRY_POINT.read_text(encoding="utf-8")
    tree = ast.parse(source)

    handler = next((node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "handler"), None)
    assert handler is not None, f"{ENTRY_POINT.name} must define `handler`"

    auth_lines = [node.lineno for node in ast.walk(handler)
                  if isinstance(node, ast.Call) and (
                      (isinstance(node.func, ast.Name) and node.func.id == "require_auth")
                      or (isinstance(node.func, ast.Attribute)
                          and node.func.attr == "require_auth"))]
    assert auth_lines, "the live service-api router must call require_auth"

    # The first route test is an `in path` comparison; the guard must precede it.
    route_lines = [node.lineno for node in ast.walk(handler)
                   if isinstance(node, ast.Compare)
                   and any(isinstance(op, ast.In) for op in node.ops)
                   and any(isinstance(c, ast.Constant) and isinstance(c.value, str)
                           and c.value.startswith("/") for c in node.comparators + [node.left])]
    if route_lines:
        assert min(auth_lines) < min(route_lines), (
            f"require_auth at line {min(auth_lines)} runs AFTER the first route test at "
            f"line {min(route_lines)}; the routes would be open")


def test_every_name_the_importer_needs_still_exists():
    """The deletion must not have taken a used helper with it.

    `_extract_path_param` sat immediately after the dead router and IS imported (as
    `_svc_path_param`), which is exactly the kind of neighbour a line-range deletion eats.
    """
    wanted = imported_from_service_api(IMPORTER)
    assert wanted, "handler.py should import from service_api; the wiring has changed"

    defined = top_level_functions(LIBRARY)
    missing = sorted(name for name in wanted if name not in defined)
    assert not missing, f"handler.py imports names service_api.py no longer defines: {missing}"

    assert "_extract_path_param" in wanted and "_extract_path_param" in defined, (
        "the helper that sat next to the deleted router must remain, and remain imported")


def test_the_importer_never_takes_the_library_router():
    """If this ever starts importing a router, the two copies are back to two entry points."""
    assert "handler" not in imported_from_service_api(IMPORTER)


def test_the_twins_still_share_their_business_logic():
    """Guards the premise. These tests are only worth having while the two files really are
    near-copies; if they diverge wholesale, the shared-logic hazard is gone and so is the
    reason for this file.

    Deliberately a floor rather than an exact count, so ordinary edits to either file do not
    fail it - it is measuring "still twins", not "still identical".
    """
    shared = top_level_functions(LIBRARY) & top_level_functions(ENTRY_POINT)
    assert len(shared) >= 30, (
        f"only {len(shared)} functions are common to the two copies. If they have genuinely "
        f"separated, delete this test file and say so; if not, something was lost."
    )


def test_the_library_router_removal_is_explained_in_place():
    """A deletion with no note reads as an accident to the next person, who restores it."""
    source = LIBRARY.read_text(encoding="utf-8")
    assert "NO ROUTER HERE" in source, (
        "the comment recording why service_api.py has no handler has gone; without it the "
        "obvious reading is that one is missing")
    assert "handler.handler" in source, (
        "the note should name the actual entry point, so the claim is checkable")
