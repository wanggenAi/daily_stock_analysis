from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVENT_WORKFLOW = ROOT / ".github/workflows/genge-v311-event-driven-deep-review.yml"
HANDOFF_WORKFLOW = ROOT / ".github/workflows/genge-v311-event-driven-authority-handoff.yml"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_event_driver_delegates_both_paths_to_explicit_authority_handoff() -> None:
    text = _text(EVENT_WORKFLOW)
    assert "genge-v311-event-driven-authority-handoff.yml" in text
    assert "REUSE_DISCOVERY_THEN_FULL_AUTHORITY_CHAIN" in text
    assert "FULL_DISCOVERY_AND_AUTHORITY_FALLBACK" in text
    assert "ACTIVE_AUTHORITY_HANDOFF_DEFER" in text
    assert "authority_handoff_active" in text
    assert "Discovery -> Every-Industry -> Production Finalizer -> exact Authority Consumer Handoff" in text


def test_successful_research_repair_does_not_repeat_heavy_research() -> None:
    text = _text(EVENT_WORKFLOW)
    assert '-f industry_run_id="$success_run_id"' in text
    assert "authority_repair_dispatched" in text
    assert "without restarting heavy research" in text


def test_handoff_closes_upstream_authority_then_reuses_verified_consumer_handoff() -> None:
    text = _text(HANDOFF_WORKFLOW)
    assert "actions: write" in text
    assert "industry_run_id:" in text
    assert "REUSED_SUCCESSFUL_INDUSTRY_FOR_FINALIZER_REPAIR" in text
    assert "genge-v31-industry-research.yml" in text
    assert "-f explicit_finalizer=false" in text
    assert "genge-v311-production-finalizer.yml" in text
    assert "genge-v311-authority-consumer-handoff.yml" in text
    assert "genge-v311-authoritative-canonical-${industry_run_id}" in text

    industry = text.index("industry_run_id=$(dispatch_and_resolve")
    finalizer = text.index("finalizer_run_id=$(dispatch_and_resolve")
    consumers = text.index("consumer_handoff_run_id=$(dispatch_and_resolve")
    assert industry < finalizer < consumers


def test_handoff_reuses_automatic_consumer_before_explicit_fallback() -> None:
    text = _text(HANDOFF_WORKFLOW)
    lookup = text.index("find_success_or_active_named_run")
    reuse = text.index("REUSED_AUTOMATIC_CONSUMER_HANDOFF")
    explicit = text.index("EXPLICIT_CONSUMER_HANDOFF")
    assert lookup < reuse < explicit
    assert "for _ in $(seq 1 10)" in text
    assert "automatic consumer handoff is reused when present" in text


def test_event_handoff_does_not_duplicate_verified_downstream_consumer_orchestration() -> None:
    text = _text(HANDOFF_WORKFLOW)
    assert "genge-v311-continuity-state.yml" not in text
    assert "genge-hourly-deep-overlay.yml" not in text
    assert "genge-v311-operating-ledger.yml" not in text
    assert "Authority Consumer Handoff run" in text
    assert "Formal actions remain authorized only by Production Finalizer" in text
    assert "no auto trade" in text


def test_handoff_fails_closed_on_required_artifacts_and_run_identity() -> None:
    text = _text(HANDOFF_WORKFLOW)
    assert 'if [ "$name" != "$expected_name" ]' in text
    assert 'if [ "$conclusion" != "success" ]' in text
    assert 'require_artifact "$discovery_run_id" "genge-all-a-production-report"' in text
    assert 'require_artifact "$industry_run_id" "genge-v31-every-industry-research"' in text
    assert 'require_artifact "$finalizer_run_id" "genge-v311-authoritative-canonical-${industry_run_id}"' in text
