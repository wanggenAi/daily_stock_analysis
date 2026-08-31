from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVENT_WORKFLOW = ROOT / ".github/workflows/genge-v311-event-driven-deep-review.yml"
HANDOFF_WORKFLOW = ROOT / ".github/workflows/genge-v311-event-driven-authority-handoff.yml"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_event_driver_delegates_to_explicit_authority_handoff() -> None:
    text = _text(EVENT_WORKFLOW)
    assert "genge-v311-event-driven-authority-handoff.yml" in text
    assert "REUSE_DISCOVERY_THEN_FULL_AUTHORITY_CHAIN" in text
    assert "FULL_DISCOVERY_AND_AUTHORITY_FALLBACK" in text
    assert "genge-v311-event-deep-review-v2-" in text
    assert "Every-Industry -> Production Finalizer -> Holding Continuity -> Hourly Refresh -> Operating Ledger" in text


def test_handoff_preserves_formal_authority_and_refresh_order() -> None:
    text = _text(HANDOFF_WORKFLOW)
    assert "actions: write" in text
    assert "genge-v31-industry-research.yml" in text
    assert "genge-v311-production-finalizer.yml" in text
    assert "genge-v311-continuity-state.yml" in text
    assert "genge-hourly-deep-overlay.yml" in text
    assert "genge-v311-operating-ledger.yml" in text
    assert "genge-v311-authoritative-canonical-${industry_run_id}" in text

    finalizer = text.index("finalizer_run_id=$(dispatch_and_resolve")
    continuity = text.index("continuity_run_id=$(dispatch_and_resolve")
    hourly = text.index("hourly_run_id=$(dispatch_and_resolve")
    ledger = text.index("ledger_run_id=$(dispatch_and_resolve")
    assert finalizer < continuity < hourly < ledger


def test_handoff_dispatch_parser_emits_only_the_resolved_run_id() -> None:
    text = _text(HANDOFF_WORKFLOW)
    assert 'gh workflow run "$workflow" --repo "$GITHUB_REPOSITORY" --ref main "$@" >/dev/null' in text
    assert 'printf \'%s\\n\' "$run_id"' in text


def test_handoff_fails_closed_on_required_artifacts_and_failed_runs() -> None:
    text = _text(HANDOFF_WORKFLOW)
    assert 'if [ "$conclusion" != "success" ]' in text
    assert 'require_artifact "$discovery_run_id" "genge-all-a-production-report"' in text
    assert 'require_artifact "$industry_run_id" "genge-v31-every-industry-research"' in text
    assert 'require_artifact "$finalizer_run_id" "genge-v311-authoritative-canonical-${industry_run_id}"' in text
    assert "Formal actions remain authorized only by Production Finalizer" in text
