"""The published-corpus index, and the estimator that makes it small enough to commit.

WHAT WAS WRONG BEFORE THIS EXISTED.

`blog_quality_v2.CorpusIndex` loaded from committed manifests only. Measured 2026-09-29:
383 manifest records against a live corpus of 1,165 published posts, so 782 published posts
were invisible to section 28. The gate compared a new article against a third of the corpus
and returned `PASS` on NON_DUPLICATION. A duplication gate that reports success on an
unchecked corpus is worse than no gate, because it is believed.

The load-bearing tests here are:

- `test_a_republished_article_is_caught` — the actual defect, end to end.
- `test_the_estimator_is_not_the_naive_ratio` — the naive sketch formula is biased downward
  exactly when documents differ in length, which is the common case.
- `test_the_gate_says_when_it_has_no_index` — a silent absence would restore the original
  problem while looking healthy.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import blog_corpus_index as ci  # noqa: E402
import blog_quality_v2 as q  # noqa: E402

REAL_INDEX = ROOT / "content" / "conversations" / "corpus-index.json"


# ── Sketching and the estimator ─────────────────────────────────────────────────

def _exact_jaccard(left: str, right: str) -> float:
    a, b = q.shingle_hashes(left), q.shingle_hashes(right)
    return len(a & b) / len(a | b) if (a | b) else 0.0


def _prose(words: int, seed: int = 0) -> str:
    rng = random.Random(seed)
    vocabulary = [f"w{index}" for index in range(400)]
    return " ".join(rng.choice(vocabulary) for _ in range(words))


def test_an_identical_body_estimates_one():
    text = _prose(600, seed=1)
    assert q.sketch_jaccard(q.sketch(text), q.sketch(text)) == pytest.approx(1.0)


def test_unrelated_bodies_estimate_near_zero():
    assert q.sketch_jaccard(q.sketch(_prose(600, 1)), q.sketch(_prose(600, 2))) < 0.05


@pytest.mark.parametrize("kept,total", [(570, 600), (420, 600), (240, 600)])
def test_the_estimate_tracks_exact_jaccard(kept, total):
    rng = random.Random(99)
    vocabulary = [f"w{index}" for index in range(400)]
    base = _prose(total, seed=1)
    other = " ".join(base.split()[:kept]) + " " + " ".join(
        rng.choice(vocabulary) for _ in range(total - kept))
    exact = _exact_jaccard(base, other)
    estimate = q.sketch_jaccard(q.sketch(base), q.sketch(other))
    # 128 samples gives a standard error around 4-5%; allow a generous band so this is a
    # correctness test rather than a flakiness generator.
    assert abs(exact - estimate) < 0.08, f"exact {exact:.3f} vs estimate {estimate:.3f}"


def test_the_estimator_is_not_the_naive_ratio():
    """The naive form is biased downward when documents differ in length.

    Each sketch holds only its OWN k smallest hashes, so a shingle present in both
    documents can survive in one sketch and be cut from the other purely because that
    document is longer. A 300-word distinction against a 1,400-word article is the common
    case here, not the edge.
    """
    short = _prose(150, seed=5)
    long_body = short + " " + _prose(1400, seed=6)
    left, right = q.sketch(short), q.sketch(long_body)

    exact = _exact_jaccard(short, long_body)
    unbiased = q.sketch_jaccard(left, right)
    naive = len(set(left) & set(right)) / len(set(left) | set(right))

    assert abs(unbiased - exact) < abs(naive - exact), (
        f"exact {exact:.3f}  unbiased {unbiased:.3f}  naive {naive:.3f}")


def test_an_empty_sketch_compares_to_zero():
    assert q.sketch_jaccard([], q.sketch(_prose(300))) == 0.0
    assert q.sketch_jaccard(q.sketch(_prose(300)), []) == 0.0


def test_a_sketch_is_capped_and_sorted():
    values = q.sketch(_prose(5000, seed=3))
    assert len(values) == q.SKETCH_K
    assert values == sorted(values), "an unsorted sketch churns the committed diff"


def test_a_short_body_still_sketches():
    assert q.sketch("only a handful of words here") != []


def test_encoding_round_trips_exactly():
    values = q.sketch(_prose(600, seed=4))
    assert q.decode_sketch(q.encode_sketch(values)) == values


def test_a_legacy_integer_array_still_decodes():
    """An index written by an earlier version must not become unreadable."""
    assert q.decode_sketch([1, 2, 3]) == [1, 2, 3]


def test_the_packed_form_is_smaller_than_a_json_array():
    """Packing helps, but it is the SMALLER of the two savings — worth stating precisely.

    The real index went 3.7 MB -> 1.4 MB, and most of that came from narrowing the hash from
    64 to 32 bits, not from hex packing. A 32-bit decimal array is ~1,344 characters against
    ~1,026 packed, a 1.3x saving; a 64-bit array is ~2,500. Asserting a 1.5x packing win
    conflated the two and failed on arithmetic rather than on a defect.
    """
    values = q.sketch(_prose(600, seed=8))
    packed = len(json.dumps(q.encode_sketch(values)))
    array = len(json.dumps(values))
    assert packed < array, f"packed {packed} vs array {array}"

    # The saving that actually shrank the index: a 64-bit array would be far larger.
    wide = json.dumps([value * 2 ** 32 + value for value in values])
    assert packed < len(wide) / 2, f"packed {packed} vs 64-bit array {len(wide)}"


@pytest.mark.skipif(not REAL_INDEX.exists(), reason="corpus index not built")
def test_the_committed_index_stays_within_a_reviewable_size():
    """A committed index nobody will look at is a committed index nobody maintains.

    2 MB is the working ceiling: the real file is 1.4 MB for 1,165 posts, and sketches are
    sorted so publishing 25 posts changes 25 lines rather than churning the file.
    """
    size = REAL_INDEX.stat().st_size
    assert size < 2 * 1024 * 1024, f"{size / 1024 / 1024:.1f} MB"


def test_the_two_modules_agree_on_the_sketch():
    """`blog_corpus_index` re-exports rather than reimplementing; two sketchers would produce
    two incompatible indexes."""
    text = _prose(400, seed=11)
    assert ci.sketch(text) == q.sketch(text)
    assert ci.jaccard(ci.sketch(text), q.sketch(text)) == pytest.approx(1.0)


# ── Loading into the gate ───────────────────────────────────────────────────────

def _write_index(path: Path, posts) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "version": ci.INDEX_VERSION, "builtAt": "2026-09-29T00:00:00+00:00",
        "sketchK": q.SKETCH_K, "shingleSize": q.SHINGLE_SIZE,
        "hashBits": q.SKETCH_HASH_BITS,
        "listingCount": len(posts), "indexedCount": len(posts), "missing": [],
        "posts": posts,
    }), encoding="utf-8")


def _index_post(slug: str, title: str, body: str, category: str = "Conversations"):
    return {"slug": slug, "title": title,
            "normalizedTitle": q._normalize_title(title), "category": category,
            "publishedDate": "2026-01-01T00:00:00.000Z", "words": q.word_count(body),
            "sketch": q.encode_sketch(q.sketch(body))}


def test_loading_the_index_populates_the_corpus(tmp_path):
    path = tmp_path / "corpus-index.json"
    _write_index(path, [_index_post("a", "Title A", _prose(400, 1)),
                        _index_post("b", "Title B", _prose(400, 2))])
    corpus = q.CorpusIndex()
    assert corpus.load_published_index(path) == 2
    assert len(corpus) == 2


def test_a_missing_index_loads_zero_rather_than_raising(tmp_path):
    """Every unit test that builds a two-record corpus would otherwise need the 1.4 MB file."""
    corpus = q.CorpusIndex()
    assert corpus.load_published_index(tmp_path / "absent.json") == 0


def test_a_corrupt_index_loads_zero_rather_than_raising(tmp_path):
    path = tmp_path / "corpus-index.json"
    path.write_text("{not json", encoding="utf-8")
    assert q.CorpusIndex().load_published_index(path) == 0


def test_the_index_does_not_overwrite_a_manifest_entry(tmp_path):
    """A wave record already in the corpus keeps its richer entry, including its distinction."""
    body = _prose(400, 1)
    corpus = q.CorpusIndex()
    corpus.add({"slug": "a", "title": "Title A", "contentMarkdown": body,
                "centralDistinction": "D" * 80}, origin="wave")
    path = tmp_path / "corpus-index.json"
    _write_index(path, [_index_post("a", "Title A", body)])
    assert corpus.load_published_index(path) == 0
    assert corpus.entries[0].distinction != ""


def test_a_republished_article_is_caught(tmp_path):
    """THE DEFECT, end to end: the same body under a new title and slug.

    This returned `PASS` before the index existed, because the published post was not in
    the corpus the gate compared against.
    """
    body = "\n\n".join(_prose(180, seed=index) for index in (21, 22, 23))
    path = tmp_path / "corpus-index.json"
    _write_index(path, [_index_post("the-original-slug", "The Original Title", body)])

    corpus = q.CorpusIndex()
    corpus.load_published_index(path)
    findings = corpus.findings({
        "slug": "a-completely-different-slug",
        "title": "A Completely Different Title Entirely",
        "contentMarkdown": body,
    })
    codes = {finding.code for finding in findings}
    assert "EXACT_BODY_DUPLICATE" in codes, [str(f) for f in findings]
    assert any("the-original-slug" in str(f) for f in findings), "must name the match"


def test_a_genuinely_new_article_is_not_flagged(tmp_path):
    path = tmp_path / "corpus-index.json"
    _write_index(path, [_index_post("the-original", "The Original", _prose(500, 31))])
    corpus = q.CorpusIndex()
    corpus.load_published_index(path)
    findings = corpus.findings({
        "slug": "something-else-entirely", "title": "Something Else Entirely",
        "contentMarkdown": _prose(500, 32),
    })
    assert [f for f in findings if f.severity == "BLOCK"] == []


def test_a_slug_that_is_already_published_collides(tmp_path):
    path = tmp_path / "corpus-index.json"
    _write_index(path, [_index_post("taken-slug", "Taken", _prose(400, 41))])
    corpus = q.CorpusIndex()
    corpus.load_published_index(path)
    findings = corpus.findings({"slug": "taken-slug", "title": "Different Title",
                                "contentMarkdown": _prose(400, 42)})
    assert "EXACT_SLUG_COLLISION" in {f.code for f in findings}


# ── Health reporting ────────────────────────────────────────────────────────────

def test_the_gate_says_when_it_has_no_index(tmp_path):
    health = q.published_index_health(tmp_path / "absent.json")
    assert health["present"] is False
    assert "blog_corpus_index.py build" in health["note"]


def test_health_reports_the_count_and_build_time(tmp_path):
    path = tmp_path / "corpus-index.json"
    _write_index(path, [_index_post("a", "A", _prose(400, 51))])
    health = q.published_index_health(path)
    assert health["present"] is True
    assert health["indexed"] == 1
    assert health["builtAt"]


def test_health_flags_an_incomplete_index(tmp_path):
    path = tmp_path / "corpus-index.json"
    document = json.loads(
        (lambda p: (_write_index(p, [_index_post("a", "A", _prose(400, 61))]),
                    p.read_text(encoding="utf-8"))[1])(path))
    document["listingCount"] = 100
    path.write_text(json.dumps(document), encoding="utf-8")
    assert "unindexed" in q.published_index_health(path)["note"]


def test_verify_rejects_an_empty_index(tmp_path):
    path = tmp_path / "corpus-index.json"
    _write_index(path, [])
    problems = ci.verify(path, live_count=-1)
    assert any("holds no posts" in problem for problem in problems)


def test_verify_rejects_a_mismatched_sketch_size(tmp_path):
    path = tmp_path / "corpus-index.json"
    _write_index(path, [_index_post("a", "A", _prose(400, 71))])
    document = json.loads(path.read_text(encoding="utf-8"))
    document["sketchK"] = 7
    path.write_text(json.dumps(document), encoding="utf-8")
    assert any("sketchK" in problem for problem in ci.verify(path, live_count=-1))


def test_verify_rejects_an_entry_with_no_sketch(tmp_path):
    path = tmp_path / "corpus-index.json"
    post = _index_post("a", "A", _prose(400, 81))
    post["sketch"] = ""
    _write_index(path, [post])
    assert any("no sketch" in problem for problem in ci.verify(path, live_count=-1))


def test_verify_flags_a_stale_index(tmp_path):
    """An index complete last month reports PASS exactly as misleadingly as no index."""
    path = tmp_path / "corpus-index.json"
    _write_index(path, [_index_post("a", "A", _prose(400, 91))])
    problems = ci.verify(path, live_count=500)
    assert any("unindexed" in problem for problem in problems)


def test_verify_accepts_a_complete_index(tmp_path):
    path = tmp_path / "corpus-index.json"
    _write_index(path, [_index_post("a", "A", _prose(400, 92))])
    assert ci.verify(path, live_count=1) == []


# ── The committed index ─────────────────────────────────────────────────────────

@pytest.mark.skipif(not REAL_INDEX.exists(), reason="corpus index not built")
def test_the_committed_index_is_structurally_sound():
    document = json.loads(REAL_INDEX.read_text(encoding="utf-8"))
    assert document["version"] == ci.INDEX_VERSION
    assert document["sketchK"] == q.SKETCH_K
    assert document["hashBits"] == q.SKETCH_HASH_BITS
    assert document["indexedCount"] == len(document["posts"])
    assert document["missing"] == []
    slugs = [post["slug"] for post in document["posts"]]
    assert len(slugs) == len(set(slugs)), "duplicate slug in the index"
    for post in document["posts"]:
        assert post["slug"]
        assert post["sketch"], post["slug"]
        assert len(post["sketch"]) % (q.SKETCH_HASH_BITS // 4) == 0


@pytest.mark.skipif(not REAL_INDEX.exists(), reason="corpus index not built")
def test_the_committed_index_covers_both_categories():
    document = json.loads(REAL_INDEX.read_text(encoding="utf-8"))
    categories = {post["category"] for post in document["posts"]}
    assert set(q.CATEGORIES).issubset(categories), categories


@pytest.mark.skipif(not REAL_INDEX.exists(), reason="corpus index not built")
def test_the_committed_index_is_far_larger_than_the_manifests():
    """The whole point: the manifests were 383 records against a corpus of 1,165."""
    import glob
    manifest_records = sum(
        len(json.load(open(path)).get("posts", []))
        for path in glob.glob(str(ROOT / "content/gastronomy/batches/*.json"))
        + glob.glob(str(ROOT / "migration/blog/batch-*.json")))
    indexed = json.loads(REAL_INDEX.read_text(encoding="utf-8"))["indexedCount"]
    assert indexed > manifest_records * 2, f"{indexed} indexed vs {manifest_records} manifest"


@pytest.mark.skipif(not REAL_INDEX.exists(), reason="corpus index not built")
def test_the_default_corpus_load_includes_the_published_index():
    corpus = q._build_corpus(q.DEFAULT_CORPUS, published=True)
    assert len(corpus) > 1000, f"only {len(corpus)} entries"


@pytest.mark.skipif(not REAL_INDEX.exists(), reason="corpus index not built")
def test_the_published_index_can_be_skipped_for_unit_work():
    small = q._build_corpus([], published=False)
    assert len(small) == 0
