#!/usr/bin/env python3
"""Assert the exported site does not publish a server-side credential.

WHY THIS EXISTS
---------------
`next.config.js` uses ``output: 'export'``, so every ``NEXT_PUBLIC_*`` value is
inlined into a JS chunk under ``out/_next/static/chunks/`` at build time and
served to every visitor. That is fine for a Maps *browser* key, which Google's own
model treats as public and restricts by HTTP referrer. It is a disclosure for any
key that also authorizes server-side APIs.

Those two cases are indistinguishable by variable name alone, and this repo has a
specific trap: ``docs/provider-inventory.md`` records that `wecare/google/cloud`,
`wecare/google-api-key` and `wecare/google-maps` **all hold the same unified key**,
fingerprint ``sha256:0bd4beb6496a``. `wecare-whatsapp-templates` reads it
server-side for the Places proxy, under a comment saying it is "never exposed to
the browser". Pasting that one value into ``NEXT_PUBLIC_GOOGLE_MAPS_KEY`` would
publish the credential that authorizes Places, Geocoding and PageSpeed to every
visitor - and it is already one of the four historically exposed credentials
awaiting rotation (``.kiro/steering/secret-handling.md``).

`scripts/verify_no_secrets_in_tree.py` does not cover this: it scans a fixed list
of six source files and never looks at build output.

HOW IT DECIDES, WITHOUT EVER READING A SECRET
---------------------------------------------
Fingerprints are compared, never values. The unified key's fingerprint is already
committed in ``docs/provider-inventory.md``, so this check needs no Secrets Manager
read - which is prohibited anyway (``.kiro/steering/aws-agent-rules.md``).

  * A Google key whose fingerprint matches a known SERVER-SIDE key  -> FAIL.
  * Any other Google key                                            -> allowed,
    reported with its fingerprint. A browser key is public by design; this check
    deliberately does not pretend otherwise.
  * Any other issuer shape (Razorpay live, OpenAI, AWS, GitHub, Slack, Stripe
    live, PEM private key) -> FAIL. None of those has a legitimate reason to be
    in a browser bundle, so there is no fingerprint exception for them.

Values are never printed. Findings are reported as file + fingerprint + length,
the metadata set sanctioned by ``.kiro/steering/plaintext-source-policy.md``.

Usage
-----
    python scripts/verify_public_bundle_secrets.py            # scans out/
    python scripts/verify_public_bundle_secrets.py --dir out
    python scripts/verify_public_bundle_secrets.py --list-fingerprints

Exit codes: 0 clean, 1 a forbidden credential is present, 2 nothing to scan
(a missing export is a setup error, not a pass - see the note in main()).
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Matches scripts/env_manifest.py:fp() and the other fingerprint helpers in
# scripts/, so a value fingerprinted here is comparable with one fingerprinted
# there. Do not change the digest or the truncation independently of those.
def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


# Server-side keys that must never appear in the export. Fingerprints only - these
# are one-way and already public in the docs cited above, so this list discloses
# nothing. Add to it whenever another server-side key is recorded.
FORBIDDEN_FINGERPRINTS = {
    "0bd4beb6496a": (
        "the unified Google API key - one value shared by wecare/google/cloud, "
        "wecare/google-api-key and wecare/google-maps; read server-side by "
        "wecare-whatsapp-templates (docs/provider-inventory.md)"
    ),
}

# Issuer-anchored and long-tailed, so prose and placeholders do not register.
# `google` is handled separately because it is the one shape with a legitimate
# public form.
GOOGLE = re.compile(r"AIza[A-Za-z0-9_\-]{30,}")

NEVER_PUBLIC = {
    "razorpay live":    re.compile(r"rzp_live_[A-Za-z0-9]{8,}"),
    "openai":           re.compile(r"sk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{30,}"),
    "aws access key":   re.compile(r"(?:AKIA|ASIA)[0-9A-Z]{16}"),
    "github":           re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "slack":            re.compile(r"xox[abprs]-[A-Za-z0-9\-]{20,}"),
    "stripe live":      re.compile(r"sk_live_[A-Za-z0-9]{20,}"),
    "pem private key":  re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
}

# AWS's published documentation example, and runs of one repeated character used
# as synthetic filler in this repo's own hook tests.
AWS_DOC_EXAMPLE = "AKI" + "A" + "IOSFODNN7EXAMPLE"
FILLER = re.compile(r"(.)\1{19,}")

# Text-ish payloads only. Fonts, images and source maps of binary assets cannot
# carry a credential that a browser would read as configuration, and scanning
# them makes the check slow enough that someone will switch it off.
SCAN_SUFFIXES = {".js", ".mjs", ".cjs", ".json", ".html", ".css", ".txt", ".xml", ".map"}


def benign(match: str) -> bool:
    return match == AWS_DOC_EXAMPLE or bool(FILLER.search(match))


def scan_file(path: Path, rel: str) -> tuple[list[dict], list[dict]]:
    """Return (failures, allowed_google_keys) for one file."""
    failures: list[dict] = []
    allowed: list[dict] = []
    try:
        text = path.read_text(errors="replace")
    except OSError as exc:
        # Unreadable file in the export is itself worth surfacing, but it is a
        # build problem rather than a credential problem.
        print(f"  WARN  could not read {rel}: {type(exc).__name__}")
        return failures, allowed

    for label, rx in NEVER_PUBLIC.items():
        for m in rx.findall(text):
            if benign(m):
                continue
            failures.append({
                "file": rel, "kind": label,
                "fingerprint": fingerprint(m), "length": len(m),
                "why": f"{label} credentials have no legitimate public form",
            })

    for m in GOOGLE.findall(text):
        if benign(m):
            continue
        fp = fingerprint(m)
        if fp in FORBIDDEN_FINGERPRINTS:
            failures.append({
                "file": rel, "kind": "google (server-side)",
                "fingerprint": fp, "length": len(m),
                "why": FORBIDDEN_FINGERPRINTS[fp],
            })
        else:
            allowed.append({"file": rel, "fingerprint": fp, "length": len(m)})

    return failures, allowed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="out",
                    help="directory to scan, relative to the repo root (default: out)")
    ap.add_argument("--list-fingerprints", action="store_true",
                    help="print the forbidden fingerprints and exit")
    args = ap.parse_args()

    if args.list_fingerprints:
        print("Server-side key fingerprints that must never reach the export:\n")
        for fp, why in FORBIDDEN_FINGERPRINTS.items():
            print(f"  sha256:{fp}\n    {why}\n")
        return 0

    target = ROOT / args.dir
    if not target.is_dir():
        # Deliberately NOT exit 0. A gate that silently passes when the thing it
        # inspects is absent is the failure mode this repo has already been bitten
        # by (see the header of scripts/snapstart_publish.py).
        print(f"NOTHING TO SCAN: {args.dir}/ does not exist. Run `npm run build` first.")
        return 2

    files = [p for p in target.rglob("*")
             if p.is_file() and p.suffix.lower() in SCAN_SUFFIXES]

    failures: list[dict] = []
    allowed: list[dict] = []
    for p in files:
        f, a = scan_file(p, str(p.relative_to(ROOT)))
        failures += f
        allowed += a

    print(f"scanned {len(files)} text files under {args.dir}/")

    if allowed:
        # Grouped by fingerprint: one key inlined into one chunk is the expected
        # shape, and the count matters more than the file list.
        by_fp: dict[str, list[str]] = {}
        for a in allowed:
            by_fp.setdefault(a["fingerprint"], []).append(a["file"])
        print("\nPublic Google keys present (allowed - a browser key is public by design):")
        for fp, fs in by_fp.items():
            print(f"  sha256:{fp}  in {len(fs)} file(s): {', '.join(sorted(set(fs))[:3])}")
        print("  Restrict each in the Cloud console: HTTP referrers wecare.digital/* and")
        print("  *.wecare.digital/*, API restrictions Maps JavaScript API only.")

    if failures:
        print(f"\nFAIL: {len(failures)} forbidden credential occurrence(s) in the export\n")
        for f in failures:
            print(f"  {f['file']}")
            print(f"    kind        {f['kind']}")
            print(f"    fingerprint sha256:{f['fingerprint']}  (length {f['length']})")
            print(f"    why         {f['why']}")
        print("\nThe value is NOT printed. Do not echo it to find it - locate it by")
        print("fingerprint with scripts/env_manifest.py, remove it from the")
        print("NEXT_PUBLIC_* variable that carries it, and rebuild.")
        return 1

    print("\nPASS: the export publishes no server-side credential")
    return 0


if __name__ == "__main__":
    sys.exit(main())
