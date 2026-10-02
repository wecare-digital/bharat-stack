"""The first release can change named public presentation components only."""
import re

ALLOWED = {
    "src/components/Header.tsx", "src/components/Footer.tsx",
    "src/components/HeaderCart.tsx", "src/components/BrandBadge.tsx",
    "src/components/BrandLockup.tsx", "src/components/BrandMark.tsx",
    "src/components/Breadcrumbs.tsx", "src/components/ErrorState.tsx",
}


def validate_patch(patch):
    if not isinstance(patch, str) or len(patch.encode()) > 32768:
        raise ValueError("Patch exceeds the limit")
    if any(s in patch for s in ("GIT binary patch", "new file mode", "deleted file mode", "old mode", "new mode", "rename from", "rename to", "copy from", "copy to")):
        raise ValueError("Only existing text files can be patched")
    chunks = re.split(r"(?m)^diff --git ", patch)
    if chunks[0].strip() or len(chunks) < 2:
        raise ValueError("A git-format patch is required")
    seen = set()
    for chunk in chunks[1:]:
        lines = chunk.splitlines()
        if not lines:
            raise ValueError("Empty patch chunk")
        header = lines[0]
        match = re.fullmatch(r"a/(\S+) b/(\S+)", header)
        if not match or match[1] != match[2] or match[1] not in ALLOWED or match[1] in seen:
            raise ValueError("Patch path is outside the public-component allowlist")
        path = match[1]
        seen.add(path)
        # git apply trusts the ---/+++ header, so check both as well as diff --git.
        old = re.findall(r"(?m)^--- (.*)$", chunk)
        new = re.findall(r"(?m)^\+\+\+ (.*)$", chunk)
        if old != ["a/" + path] or new != ["b/" + path] or "@@ " not in chunk:
            raise ValueError("Patch headers do not match")
    return sorted(seen)
