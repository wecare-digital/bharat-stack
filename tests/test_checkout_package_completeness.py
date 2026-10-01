"""Every module the checkout path can reach must be IN the deployment ZIP.

The failure this guards against is specific and silent: a handler whose imports all resolve in
the repository, packaged without one of them, deploys cleanly and then fails on the first real
request with `Unable to import module 'handler'`. No build step catches it, because the build
step is the thing that dropped the file.

It also pins the inverse - what must NOT ship. Tests, `__pycache__` and dev dependencies in a
Lambda package are dead weight at best, and at worst a test fixture carrying a credential shape
inside a production artifact.

These assertions run against the WORKING TREE, which is the right scope for a test: it asks
"would a package built from this repository today be complete", not "what did one deploy ship".
The deployed-revision evidence lives in docs/execution/checkout-deployment-20261001.md.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "provision_checkout.py"

#: Everything the two coexisting checkout flows can reach. The website Razorpay path
#: (`website_checkout`, `razorpay_orders`, `checkout_pricing`, `order_creation`,
#: `customer_receipt`, `customer_session`) is NOT imported by the handler today - it ships ahead
#: of the owner's architecture decision. It is listed anyway, deliberately: the day that decision
#: lands, wiring it must not also require discovering that the package was incomplete.
#:
#: Checked only for modules that EXIST under the source root being packaged, and that caveat is
#: load-bearing rather than a loophole. Five of these files exist only on `origin/stack`; a local
#: checkout 25 commits behind simply does not have them, which is a git position, not a packaging
#: defect. What this list catches is the real bug: a module present in the tree and left out of
#: the ZIP - an `EXCLUDE_DIRS` entry, a suffix filter, a renamed package directory.
#: `test_every_import_resolves` is the assertion that has no escape hatch.
REQUIRED = (
    "handler.py",
    "lambda_utils/customer_auth.py",
    "lambda_utils/customer_session.py",
    "lambda_utils/payment_readiness.py",
    "lambda_utils/payment_status.py",
    "lambda_utils/wix_ecom.py",
    "lambda_utils/response.py",
    "lambda_utils/logging.py",
    "lambda_utils/media_paths.py",
    "lambda_utils/ecommerce/order_keys.py",
    "lambda_utils/ecommerce/payment_attempt.py",
    "lambda_utils/ecommerce/website_checkout.py",
    "lambda_utils/ecommerce/checkout_pricing.py",
    "lambda_utils/ecommerce/order_creation.py",
    "lambda_utils/ecommerce/customer_receipt.py",
    "lambda_utils/integrations/razorpay_orders.py",
)

SHARED = ROOT / "amplify" / "functions" / "shared"


def _on_disk(arcname: str) -> bool:
    if arcname == "handler.py":
        return (ROOT / "amplify" / "functions" / "ecommerce" / "checkout"
                / "handler.py").is_file()
    return (SHARED / arcname).is_file()


@pytest.fixture(scope="module")
def built():
    spec = importlib.util.spec_from_file_location("provision_checkout", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["provision_checkout"] = module
    spec.loader.exec_module(module)
    try:
        yield module.build_package(ROOT)
    finally:
        sys.modules.pop("provision_checkout", None)


def test_no_module_present_on_disk_is_dropped_from_the_zip(built):
    """The packaging bug this file exists for: a file in the tree, missing from the artifact."""
    _, members, _, _ = built
    dropped = [name for name in REQUIRED if _on_disk(name) and name not in members]
    assert not dropped, ("present on disk but absent from the ZIP:\n  "
                         + "\n  ".join(dropped))


def test_the_whole_shared_tree_is_packaged(built):
    """Stated as a count rather than a list, so an exclusion rule that starts skipping a
    subdirectory is caught even for modules nobody thought to enumerate above."""
    _, members, _, _ = built
    on_disk = {f"lambda_utils/{p.relative_to(SHARED / 'lambda_utils').as_posix()}"
               for p in (SHARED / "lambda_utils").rglob("*.py")
               if "__pycache__" not in p.parts and "tests" not in p.parts}
    assert on_disk - set(members) == set()


def test_every_import_resolves(built):
    """Static, so it cannot fail falsely on a missing env var the way a real import would.
    `provided` is empty because this function has no layers: everything must come from the
    package, the python3.12 runtime, or the stdlib."""
    _, _, errors, _ = built
    assert not errors, "unresolved imports:\n  " + "\n  ".join(errors)


def test_the_configured_handler_symbol_exists(built):
    """A package can have every import satisfied and still be unbootable, because AWS is
    configured to call a symbol that does not exist - `Runtime.HandlerNotFound` on first
    invocation. Two functions in this fleet define `lambda_handler` rather than `handler`."""
    spec = importlib.util.spec_from_file_location("provision_checkout", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    dal = module._deploy_module(ROOT)
    _, members = dal.build_zip(
        dal.Spec("wecare-checkout", "ecommerce/checkout"))
    assert dal.validate_handler(members, "handler.handler") == []


def test_no_tests_or_caches_ship(built):
    _, members, _, _ = built
    junk = [name for name in members
            if "__pycache__" in name
            or name.endswith((".pyc", ".pyo"))
            or Path(name).name.startswith("test_")
            or "/tests/" in name]
    assert not junk, "shipped in the Lambda package:\n  " + "\n  ".join(junk)


def test_the_package_is_python_only(built):
    """No template, font or data file is read from disk anywhere in the checkout path, so a
    non-.py member would be an accident. Stated as an assertion rather than a comment, because
    "we don't need templates" is exactly the kind of claim that silently stops being true."""
    _, members, _, _ = built
    assert sorted(n for n in members if not n.endswith(".py")) == []


def test_source_root_actually_packages_from_that_root(tmp_path):
    """A `--source-root` that is silently ignored is worse than not having one: the operator
    believes reviewed bytes shipped while the dirty tree shipped instead. Proven against a
    synthetic tree, so it does not depend on this checkout's git position.
    """
    spec = importlib.util.spec_from_file_location("provision_checkout", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    shared = tmp_path / "amplify" / "functions" / "shared" / "lambda_utils"
    (shared / "ecommerce").mkdir(parents=True)
    (shared / "__init__.py").write_text("")
    (shared / "ecommerce" / "__init__.py").write_text("")
    (shared / "only_in_the_synthetic_root.py").write_text("MARKER = 'synthetic'\n")
    (shared / "b.py").write_text("x = 1\n")
    (shared / "c.py").write_text("y = 2\n")
    handler_dir = tmp_path / "amplify" / "functions" / "ecommerce" / "checkout"
    handler_dir.mkdir(parents=True)
    (handler_dir / "handler.py").write_text(
        "from lambda_utils import only_in_the_synthetic_root\n\n\ndef handler(e, c):\n"
        "    return only_in_the_synthetic_root.MARKER\n")

    _, members, errors, _ = module.build_package(tmp_path)
    assert errors == []
    assert "lambda_utils/only_in_the_synthetic_root.py" in members
    assert b"synthetic" in members["lambda_utils/only_in_the_synthetic_root.py"]
    # And nothing leaked in from the real repository.
    assert "lambda_utils/customer_auth.py" not in members


def test_a_source_root_without_a_checkout_handler_is_refused(tmp_path):
    """Fails loudly rather than falling back to the working tree, which would reintroduce the
    exact hazard --source-root exists to remove."""
    spec = importlib.util.spec_from_file_location("provision_checkout", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(FileNotFoundError):
        module.build_package(tmp_path)


def test_the_package_is_deterministic(built):
    """Two builds of the same bytes must produce the same CodeSha256, or every dry run reports a
    spurious `WOULD UPDATE` and the comparison stops meaning anything."""
    zip_bytes, _, _, _ = built
    spec = importlib.util.spec_from_file_location("provision_checkout", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    again, _, _, _ = module.build_package(ROOT)
    assert module.package_sha(zip_bytes) == module.package_sha(again)


def test_the_handler_reads_its_payment_credential_lazily(built):
    """A module-scope `get_secret_value` caches the value for the life of the execution
    environment, so a rotation does not take effect until every warm sandbox recycles. The
    razorpay-webhook function was fixed for exactly this on 2026-09-19."""
    _, members, _, _ = built
    import ast
    checked = [n for n in ("lambda_utils/integrations/razorpay_orders.py", "handler.py")
               if n in members]
    assert "handler.py" in checked, "the handler itself must always be packaged"
    for name in checked:
        tree = ast.parse(members[name].decode("utf-8"), filename=name)
        for node in tree.body:  # module scope only
            if not isinstance(node, (ast.Assign, ast.Expr, ast.AnnAssign)):
                continue
            for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
                rendered = ast.unparse(call.func)
                assert "get_secret_value" not in rendered, \
                    f"{name}:{call.lineno} reads a secret at import time"


def test_no_float_arithmetic_on_the_money_path(built):
    """R6.1. `0.1 + 0.2` is not `0.3` in binary floating point, and a one-paise mismatch against
    the checkout total must fail closed - so a rounding artefact becomes a refused order."""
    _, members, _, _ = built
    import ast
    money = ("lambda_utils/ecommerce/checkout_pricing.py",
             "lambda_utils/ecommerce/money.py",
             "lambda_utils/integrations/razorpay_orders.py",
             "lambda_utils/wix_ecom.py")
    for name in money:
        if name not in members:
            continue
        tree = ast.parse(members[name].decode("utf-8"), filename=name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == "float":
                pytest.fail(f"{name}:{node.lineno} calls float() on the money path")
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                pytest.fail(f"{name}:{node.lineno} holds a float literal "
                            f"({node.value!r}) on the money path")
