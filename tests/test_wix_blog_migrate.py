"""Focused tests for the guarded Wix Blog migration manifest compiler."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wix_blog_migrate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("wix_blog_migrate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_markdown_compiles_to_image_free_ricos():
    module = load_module()
    ricos = module.markdown_to_rich_content(
        "First paragraph.\n\n"
        "**Bold distinction.**\n\n"
        "When we distinguish *honoring our word*, something becomes visible.\n\n"
        "> Closing line."
    )

    nodes = ricos["nodes"]
    types = [node["type"] for node in nodes]
    assert "IMAGE" not in types
    assert "GALLERY" not in types
    assert "VIDEO" not in types
    assert types.count("PARAGRAPH") >= 5

    text_nodes = list(module.walk_nodes(ricos))
    bold = [
        node for node in text_nodes
        if node.get("type") == "TEXT"
        and any(
            decoration.get("type") == "BOLD"
            for decoration in (node.get("textData") or {}).get("decorations", [])
        )
    ]
    italic = [
        node for node in text_nodes
        if node.get("type") == "TEXT"
        and any(
            decoration.get("type") == "ITALIC"
            for decoration in (node.get("textData") or {}).get("decorations", [])
        )
    ]
    assert [node["textData"]["text"] for node in bold] == ["Bold distinction."]
    assert [node["textData"]["text"] for node in italic] == ["honoring our word"]


def test_manifest_accepts_reviewable_markdown():
    module = load_module()
    post = module.normalize_manifest_post({
        "title": "Distinction",
        "slug": "distinction",
        "firstPublishedDate": "2026-04-25T13:41:04.110Z",
        "contentMarkdown": "**A distinction brings something into presence.**",
        "seoTitle": "Distinction | WECARE.DIGITAL",
        "metaDescription": "A concise distinction on how language brings something into presence.",
        "tags": ["Distinction", "Language"],
        "authorName": module.AUTHOR_NAME,
        "category": module.CATEGORY_LABEL,
    })
    assert post["richContent"]["nodes"]
    assert module.validate_manifest_post(post) == []


def test_manifest_rejects_media_nodes():
    module = load_module()
    post = {
        "title": "Bad",
        "slug": "bad",
        "firstPublishedDate": "2026-01-01T00:00:00Z",
        "richContent": {"nodes": [{"type": "IMAGE"}]},
        "seoTitle": "Bad",
        "metaDescription": "Bad media manifest.",
        "tags": ["Bad"],
    }
    errors = module.validate_manifest_post(post)
    assert any("forbidden rich-content media node" in error for error in errors)
