"""Build a minimal, valid, text-layer PDF in memory.

Needed because the ingestion tests have to exercise real `pypdf` extraction. Mocking the
extractor would test the mock: the interesting failures in this pipeline are hard-wrapped
lines, hyphens split across a break, and running headers, and none of those exist unless
a real PDF is parsed. Hand-rolled rather than pulled from a PDF-writing dependency, which
would be a second package added for test fixtures alone.
"""
from __future__ import annotations

from typing import List, Sequence


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def make_pdf(pages: Sequence[Sequence[str]], leading: int = 14) -> bytes:
    """`pages` is a list of pages, each a list of already-wrapped text lines."""
    objects: List[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_ids: List[int] = []
    content_ids: List[int] = []
    for lines in pages:
        stream_parts = [f"BT /F1 11 Tf {leading} TL 56 760 Td".encode("latin-1")]
        for index, line in enumerate(lines):
            operator = b"Td" if index == 0 else b"'"
            if index == 0:
                stream_parts.append(b"(" + _escape(line).encode("latin-1") + b") Tj")
            else:
                stream_parts.append(b"(" + _escape(line).encode("latin-1") + b") '")
        stream_parts.append(b"ET")
        stream = b"\n".join(stream_parts)
        content_ids.append(add(b"<< /Length " + str(len(stream)).encode()
                               + b" >>\nstream\n" + stream + b"\nendstream"))
        page_ids.append(0)  # placeholder, filled once the pages tree id is known

    pages_id = len(objects) + len(pages) + 1

    real_page_ids: List[int] = []
    for content_id in content_ids:
        real_page_ids.append(add(
            b"<< /Type /Page /Parent " + str(pages_id).encode()
            + b" /MediaBox [0 0 612 792] /Resources << /Font << /F1 "
            + str(font_id).encode() + b" 0 R >> >> /Contents "
            + str(content_id).encode() + b" 0 R >>"))

    kids = b" ".join(str(pid).encode() + b" 0 R" for pid in real_page_ids)
    actual_pages_id = add(b"<< /Type /Pages /Kids [" + kids + b"] /Count "
                          + str(len(real_page_ids)).encode() + b" >>")
    assert actual_pages_id == pages_id, "pages tree id must match the /Parent references"
    catalog_id = add(b"<< /Type /Catalog /Pages " + str(pages_id).encode() + b" 0 R >>")
    info_id = add(b"<< /Title (Fixture Source Document) >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets: List[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(index).encode() + b" 0 obj\n" + body + b"\nendobj\n"

    xref_at = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (b"trailer\n<< /Size " + str(len(objects) + 1).encode()
            + b" /Root " + str(catalog_id).encode() + b" 0 R"
            + b" /Info " + str(info_id).encode() + b" 0 R >>\n"
            + b"startxref\n" + str(xref_at).encode() + b"\n%%EOF\n")
    return bytes(out)


def wrap(paragraph: str, width: int = 62) -> List[str]:
    """Hard-wrap a paragraph the way a print source does, hyphenating long words."""
    words = paragraph.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) <= width:
            current = candidate
            continue
        if len(word) > 9 and len(current) < width - 4:
            room = width - len(current) - 2
            if room >= 3:
                lines.append((current + " " + word[:room] + "-").strip())
                current = word[room:]
                continue
        lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines
