#!/usr/bin/env python3
"""CI gate: the design contract in .kiro/steering/grahak-os-design.md is the source.

The contract was calibrated by measuring the live public pages, not by eye, and it
names five retired colours explicitly. This gate stops them coming back, and stops the
semantic state colours collapsing into each other again.

What it found on 2026-09-23, before it existed
----------------------------------------------
* `--warning` and `--info` were both `#1a3a2a` — the same value as `--success`. So a
  warning rendered identically to a success at all 3 live `var(--warning)` call sites.
  A state colour that cannot be told from another state is not a state colour.
* `--text-secondary` and `--color-grey-600` were `#4b5563`, which the contract retires
  by name: "the only blue-tinted grey in the page's own copy", reading cooler than the
  neutral body text beside it. 25 live uses.
* `src/lib/design-tokens.ts` declares itself the single source of truth, mirrors
  `tokens.css` "MIRRORS" in its own docstring, contradicts it in several places, and has
  **zero importers**. 172 lines nobody uses, which is why ~1,500 border-radius
  declarations across `src/` use twelve different values against a contract that
  specifies one.

Comments are stripped before matching
-------------------------------------
`src/pages/grahak-os/index.tsx` names all five retired colours in comments that explain
why each was retired — that is the documentation working, not a violation. Reporting it
would be reporting the record of the fix as the defect, which is a mistake this
repository's tests have had to correct three times now.

Usage
-----
    python scripts/check_design_drift.py
    python scripts/check_design_drift.py --gate
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TOKENS_CSS = SRC / "styles/tokens.css"

# Retired by name in the design contract. None may appear in real CSS or in a style
# object; a comment explaining the retirement is fine.
RETIRED_COLOURS = {
    "#2f6b52": "retired brand green",
    "#075e54": "retired WhatsApp green",
    "#f2fbf6": "retired lime wash",
    "#fbfff0": "retired lime wash",
    "#1e293b": "retired slate, specifically as a code-panel body",
    "#4b5563": "retired blue-tinted grey; use rgba(0,0,0,.54)",
    "#0f172a": "rest of the retired slate ramp",
    "#94a3b8": "rest of the retired slate ramp",
    "#1e1e1e": "retired code-panel background; both panels are #000",
}

# State tokens that must stay visually distinct from one another.
STATE_TOKENS = ("--success", "--warning", "--info", "--danger")


def strip_comments(text: str, suffix: str) -> str:
    """Blank comments, preserving line numbers so reported locations are usable."""
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text,
                  flags=re.S)
    if suffix in (".ts", ".tsx"):
        text = "\n".join(re.sub(r"(?<!:)//.*$", "", ln) for ln in text.splitlines())
    return text


def scan_retired():
    violations = []
    for path in sorted(list(SRC.rglob("*.tsx")) + list(SRC.rglob("*.ts"))
                       + list(SRC.rglob("*.css"))):
        if "node_modules" in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel.endswith((".test.tsx", ".test.ts")):
            continue
        code = strip_comments(path.read_text(encoding="utf-8", errors="ignore"),
                              path.suffix)
        for colour, why in RETIRED_COLOURS.items():
            for match in re.finditer(re.escape(colour), code, re.I):
                violations.append({
                    "rule": "retired_colour", "file": rel,
                    "line": code[:match.start()].count("\n") + 1,
                    "match": colour, "why": why,
                })
    return violations


def scan_state_collision():
    """Two state tokens resolving to the same colour is a defect, not a preference."""
    if not TOKENS_CSS.exists():
        return [{"rule": "tokens_missing", "file": "src/styles/tokens.css",
                 "line": 0, "match": "", "why": "token file not found"}]

    text = strip_comments(TOKENS_CSS.read_text(encoding="utf-8"), ".css")
    values = {}
    for token in STATE_TOKENS:
        m = re.search(rf"{re.escape(token)}:\s*([^;]+);", text)
        if m:
            values[token] = m.group(1).strip().lower()

    violations = []
    seen = {}
    for token, value in values.items():
        if value in seen:
            violations.append({
                "rule": "state_colour_collision",
                "file": "src/styles/tokens.css", "line": 0, "match": value,
                "why": (f"{token} and {seen[value]} are both {value}; a state that "
                        f"cannot be distinguished from another state is not a state"),
            })
        seen[value] = token
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    violations = scan_retired() + scan_state_collision()

    if args.json:
        print(json.dumps({"violations": violations}, indent=2))
    elif not violations:
        print("DESIGN DRIFT OK - no retired colours, no state-colour collisions.")
    else:
        by_rule = {}
        for v in violations:
            by_rule.setdefault(v["rule"], []).append(v)
        for rule, items in sorted(by_rule.items()):
            print(f"\n  {rule}  ({len(items)})")
            for v in items[:12]:
                loc = f"{v['file']}:{v['line']}" if v["line"] else v["file"]
                print(f"     {loc}  {v['match']}  — {v['why']}")
            if len(items) > 12:
                print(f"     ... and {len(items) - 12} more")
        print(f"\n{len(violations)} violation(s). The contract is "
              f".kiro/steering/grahak-os-design.md; it was calibrated by measuring the "
              f"live pages, so change it deliberately rather than incidentally.")

    if args.gate and violations:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
