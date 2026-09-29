"""Root pytest configuration: refuse to run on an interpreter this suite does not support.

WHY THIS FILE EXISTS, and it is a real hour lost rather than a hypothetical one.

Run on Python 3.9, this suite reports:

    5 failed, 3529 passed, 1 skipped, 110 errors

and every one of those 115 problems is the interpreter, not the code. On 3.12 the same tree is
`3715 passed`. The failures look exactly like a broken repository:

  * the 5 failures are `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'` -
    PEP 604 annotations (`str | None`) evaluated at runtime in modules that do not import
    `from __future__ import annotations`. Valid since 3.10, a TypeError before it.
  * the 110 errors are collection failures for optional dependencies that are not installed
    because `requirements-dev.txt` was never installed for that interpreter.

requirements-dev.txt already says what to use, at the top of the file:

    python3.12 -m venv .venv
    .venv/bin/python -m pip install -r requirements-dev.txt

and all fourteen CI workflows pin `python-version: '3.12'`. So the instruction was there and the
enforcement was not, which is the gap this closes. The cost of leaving it open is not a broken
build - CI is pinned and always was - it is a reader, or an agent, taking a bare `python3` from
`$PATH`, believing the 115 problems, and reporting a baseline that does not exist. That happened.

A UsageError rather than an assert or a raise in module scope: pytest prints it as a single ERROR
line with no traceback, which is the whole point - one sentence naming the version you have, the
version you need and the command to get there, instead of 115 tracebacks about `|`.

This does NOT pin a patch version and there is deliberately no `.python-version` file alongside
it. pyenv does not prefix-match, so a `.python-version` of `3.12` fails outright on a machine
whose 3.12 is registered as `3.12.13`, and pinning the patch means every contributor whose
interpreter moved on gets a hard stop for no reason. A floor is the correct constraint: the suite
needs 3.10+ syntax and CI proves 3.12, so 3.12 is what it asks for.
"""

import sys

import pytest

# The version every workflow pins. Kept as a tuple so the comparison is version-aware rather
# than a string compare that would read "3.9" as newer than "3.12".
REQUIRED = ( 3, 12 )


def pytest_configure( config ):
    if sys.version_info >= REQUIRED:
        return
    have = '.'.join( str( part ) for part in sys.version_info[ :3 ] )
    want = '.'.join( str( part ) for part in REQUIRED )
    raise pytest.UsageError(
        f'This suite needs Python {want} or newer and is running on {have} '
        f'({sys.executable}). On an older interpreter it reports around 115 failures that are '
        f'all the interpreter and none of them the code - PEP 604 annotations raise TypeError '
        f'before 3.10, and the optional dependencies are absent. Every CI workflow pins '
        f'{want}. Set up the environment the way requirements-dev.txt describes:\n'
        f'    python{want} -m venv .venv\n'
        f'    .venv/bin/python -m pip install -r requirements-dev.txt\n'
        f'    .venv/bin/python -m pytest'
    )
