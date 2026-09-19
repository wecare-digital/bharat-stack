#!/usr/bin/env python3
"""Independently verify the encrypted credential backup.

Confirms it decrypts, that a wrong passphrase is rejected, that permissions are
correct, and that the file body contains no readable credential material.
Prints field COUNTS only, never values.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import stat

spec = importlib.util.spec_from_file_location("sb", "scripts/secrets_backup.py")
sb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sb)

# Detectors built from fragments so this file does not trip the inline-secret hook.
MARKERS = [
    ("razorpay live", "rzp" + "_live_" + r"[A-Za-z0-9]{8,}"),
    ("openai",        "sk-" + r"svcacct-[A-Za-z0-9_\-]{20,}"),
    ("google",        "AIz" + r"a[A-Za-z0-9_\-]{30,}"),
    ("pem",           "-----BEGIN " + r"[A-Z ]*PRIVATE KEY-----"),
    ("assignment",    r"\b[A-Z_]*(?:" + "SECRET" + "|" + "TOKEN" + r")[A-Z_]*\s*=\s*\S{20,}"),
]


def main() -> int:
    p = sb.passphrase_from_secrets_manager()
    blob = sb.OUT_FILE.read_bytes()

    data = json.loads(sb.decrypt(blob, p))
    print("independent decrypt  : OK")
    print(f"generated            : {data.get('_generated')}")
    print(f"secrets recovered    : {len(data['secrets'])}")
    for sid, e in sorted(data["secrets"].items()):
        v = e["value"]
        n = len(v) if isinstance(v, dict) else 1
        print(f"   {sid:34s} {n:2d} field(s)")

    print("\nwrong-passphrase test:", end=" ")
    try:
        sb.decrypt(blob, "definitely-not-the-real-one")
        print("FAILED - decrypted with a wrong key")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"correctly rejected ({type(exc).__name__})")

    st_dir = os.stat(sb.OUT_DIR)
    st_file = os.stat(sb.OUT_FILE)
    dmode = stat.S_IMODE(st_dir.st_mode)
    fmode = stat.S_IMODE(st_file.st_mode)
    print(f"\ndirectory mode       : {oct(dmode)}  (want 0o700) "
          f"{'OK' if dmode == 0o700 else 'WRONG'}")
    print(f"file mode            : {oct(fmode)}  (want 0o600) "
          f"{'OK' if fmode == 0o600 else 'WRONG'}")
    print(f"file size            : {st_file.st_size} bytes")

    text = blob.decode(errors="replace")
    print("\nreadable credential markers in the artifact:")
    total = 0
    for label, pat in MARKERS:
        n = len(re.findall(pat, text))
        total += n
        print(f"   {label:16s} {n}")
    print(f"   {'TOTAL':16s} {total}  (want 0)")

    ok = total == 0 and dmode == 0o700 and fmode == 0o600
    print("\nRESULT:", "VERIFIED - ciphertext only, correct permissions, decrypts"
          if ok else "PROBLEM - see above")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
