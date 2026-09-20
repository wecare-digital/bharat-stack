"""Shared shell-parsing helpers for the PreToolUse guard hooks.

Extracted 2026-09-20 after ``block_catastrophic.py`` refused a ``git commit``
whose *message* documented the guard itself. The heredoc body contained the
prose::

    rm/shred/truncate on / $HOME ~/.aws ~/.ssh ~/.kiro

and the guard read ``truncate`` as a program with ``/``, ``$HOME`` and the rest as
its arguments. Nothing was going to be truncated; the words were documentation.

That exposed two distinct defects, both fixed here:

1. **A heredoc body is data, not argv.** Everything between ``<<TAG`` and the
   closing ``TAG`` must be removed before any command analysis. Commit messages,
   Python scripts and YAML are routinely passed that way, and scanning them for
   command shapes produces nonsense.

2. **A program name only counts in command position.** The old loop scanned every
   token in the segment, so any occurrence of ``rm`` or ``truncate`` anywhere -
   in a filename, a flag value, a sentence - looked like an invocation. A command
   name is the first word of a segment, optionally behind environment
   assignments and pass-through wrappers such as ``sudo`` or ``xargs``.

Both guards are deliberately high-precision. The reasoning is in
``block_inline_secrets.py``: a noisy guard gets switched off, and a switched-off
guard protects nothing. A false positive on a commit message is exactly the kind
of friction that gets a hook deleted, which would then take the justification for
this workspace's wide-open permissions with it.

The trade is explicit: restricting to command position means
``find . -exec rm -rf {} \\;`` is not detected. These are backstops against the
obvious catastrophe, not a sandbox.
"""

from __future__ import annotations

import re
import shlex

# Operators that end one command and start another. A pipe is included because
# the right-hand side is a fresh command position.
SPLIT_RX = re.compile(r"&&|\|\||;|\||\n")

# Wrappers that run another command, so the real program is further right.
PASSTHROUGH = {
    "sudo", "env", "nohup", "time", "xargs", "nice", "ionice", "command",
    "exec", "eval", "timeout", "stdbuf", "setsid", "doas",
}

# Shell keywords that can precede a command inside a compound statement.
KEYWORDS = {
    "if", "then", "else", "elif", "fi", "do", "done", "while", "until", "for",
    "case", "esac", "in", "{", "}", "!", "(", ")",
}

# Flags on passthrough wrappers that consume the following token as a value.
WRAPPER_VALUE_FLAGS = {"-u", "-i", "-C", "-n", "-I", "-P", "-s", "--signal"}


def strip_heredocs(command: str) -> str:
    """Remove heredoc bodies, keeping the command line that introduced them.

    Handles ``<<TAG``, ``<<'TAG'``, ``<<\"TAG\"`` and the indented ``<<-TAG``
    form. Without this, a commit message or an inlined script is parsed as if it
    were a sequence of commands.
    """
    lines = command.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)

        tags = re.findall(r"<<-?\s*(?:'([^']+)'|\"([^\"]+)\"|([A-Za-z_][A-Za-z0-9_]*))",
                          line)
        if not tags:
            i += 1
            continue

        # Consume body lines until every opened tag has been closed.
        pending = [next(t for t in tag if t) for tag in tags]
        i += 1
        while i < len(lines) and pending:
            stripped = lines[i].strip()
            if stripped == pending[0]:
                pending.pop(0)
            i += 1
    return "\n".join(out)


def segments(command: str) -> list[str]:
    """Split into command-position segments, heredoc bodies already removed."""
    return [s.strip() for s in SPLIT_RX.split(strip_heredocs(command)) if s.strip()]


def split_args(segment: str) -> list[str]:
    try:
        return shlex.split(segment)
    except ValueError:
        # Unbalanced quotes: fall back to whitespace rather than failing open.
        return segment.split()


def program_and_args(segment: str) -> tuple[str | None, list[str], bool]:
    """Resolve a segment to (program_basename, args, went_through_sudo).

    Skips leading shell keywords, ``VAR=value`` assignments and pass-through
    wrappers so that ``sudo rm -rf /`` resolves to ``rm`` while a bare mention of
    ``rm`` inside a later argument does not resolve to anything.
    """
    argv = split_args(segment)
    sudo = False
    i = 0
    while i < len(argv):
        tok = argv[i]

        if tok in KEYWORDS:
            i += 1
            continue

        # VAR=value prefix assignments.
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tok):
            i += 1
            continue

        base = tok.rsplit("/", 1)[-1]

        if base in PASSTHROUGH:
            if base == "sudo":
                sudo = True
            i += 1
            # Step over the wrapper's own flags, honouring value-taking ones.
            while i < len(argv) and argv[i].startswith("-"):
                takes_value = argv[i] in WRAPPER_VALUE_FLAGS
                i += 1
                if takes_value and i < len(argv):
                    i += 1
            # `env -u FOO cmd` style: skip bare VAR=value after the wrapper too.
            while i < len(argv) and re.fullmatch(
                    r"[A-Za-z_][A-Za-z0-9_]*=.*", argv[i]):
                i += 1
            continue

        return base, argv[i + 1:], sudo

    return None, [], sudo


def redirect_targets(segment: str) -> list[str]:
    """Files a segment would truncate or append to via shell redirection.

    Scans the raw segment because ``>`` is unambiguous and cannot be confused
    with prose the way a program name can.
    """
    out: list[str] = []
    for m in re.finditer(r"(?<![0-9<>])>{1,2}\|?\s*([^\s;|&<>]+)", segment):
        out.append(m.group(1))
    return out
