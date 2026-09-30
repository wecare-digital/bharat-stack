import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "conversations_archive_triage.py"
spec = importlib.util.spec_from_file_location("triage", SCRIPT)
triage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(triage)

def base(**kw):
    row = {
        "original_title": "Example",
        "title_pass_route": "HOLD",
        "revised_decision": "HOLD (TITLE PASS)",
        "historical_decision": "",
        "title_level_opportunity": "APPARENTLY DISTINCT",
        "title_similarity": "0.30",
        "public_name_dependency": "NO",
        "program_dependency": "NO",
        "research_requirement": "",
    }
    row.update(kw)
    return row

def test_strong_overlap_wins():
    bucket, *_ = triage.classify(base(title_similarity="0.70"), "Example Ordinary text")
    assert bucket == "LIKELY_EXISTING_COVERAGE"

def test_program_dependency_routes_to_attribution():
    bucket, *_ = triage.classify(base(program_dependency="YES"), "Example Ordinary text")
    assert bucket == "ATTRIBUTION_REVIEW"

def test_public_name_dependency_routes_to_attribution():
    bucket, *_ = triage.classify(base(public_name_dependency="YES"), "Example Ordinary text")
    assert bucket == "ATTRIBUTION_REVIEW"


def test_research_routes_to_fact_check():
    bucket, *_ = triage.classify(base(research_requirement="health"), "Example Ordinary text")
    assert bucket == "FACT_CHECK_REQUIRED"

def test_medium_similarity_routes_to_dedupe():
    bucket, *_ = triage.classify(base(title_similarity="0.50"), "Example Ordinary text")
    assert bucket == "DEDUPE_REVIEW"

def test_clean_distinct_candidate():
    bucket, *_ = triage.classify(base(), "Example Ordinary text")
    assert bucket == "CANDIDATE_NEW_ARTICLE"

def test_common_archive_header_is_not_attribution_signal():
    text = (
        "Conversations For Transformation Essays By X "
        "Inspired By The Ideas Of Werner Erhard And More "
        "Example Ordinary article text."
    )
    bucket, *_ = triage.classify(base(), text)
    assert bucket == "CANDIDATE_NEW_ARTICLE"
