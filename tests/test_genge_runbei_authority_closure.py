from __future__ import annotations

from pathlib import Path

from src.strategies.genge_opportunity_discovery.event_driven_deep_review_trigger import build_decision


def _hourly() -> dict:
    return {
        "canonical_snapshot_id": "snap-runbei",
        "canonical_source_run_id": "9001",
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "formal_action_eligible": False,
        "no_auto_trade": True,
        "rows": [{
            "code": "000526",
            "name": "学大教育",
            "hourly_research_conclusion": "FORMAL_ACTION_UNCHANGED",
            "price_evidence_status": "",
            "latest_change_pct": 0.5,
            "latest_price_observed_at": "2026-09-07T10:20:00+08:00",
            "latest_evidence": [],
        }],
    }


def _priority(*, similarity: float = 85.9134, coverage: float = 1.0, quant_status: str = "PRIORITY_RESEARCH") -> dict:
    return {
        "canonical_snapshot_id": "snap-runbei",
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "formal_action_eligible": False,
        "no_auto_trade": True,
        "queue": [{
            "code": "000526",
            "name": "学大教育",
            "formal_action": "",
            "priority": "P2",
            "priority_score": 40,
            "research_tier": "PENDING",
            "thesis_status": "NO_NEW_MATERIAL_EVIDENCE",
            "hourly_research_conclusion": "FORMAL_ACTION_UNCHANGED",
            "reason_codes": [
                "MAPPING_GAP",
                "NEAR_BUY_EVIDENCE_RECOVERY_B",
                "SUCCESS_ARCHETYPE_RECALL",
                "ARCHETYPE:RUNBEI_001316_20260826_V1",
            ],
            "success_archetype_id": "RUNBEI_001316_20260826_V1",
            "success_archetype_similarity_score": similarity,
            "success_archetype_evidence_coverage": coverage,
            "success_archetype_source_quant_status": quant_status,
            "near_buy_evidence_recovery_tier": "B",
        }],
    }


def test_high_similarity_runbei_external_candidate_forces_authority_research_only() -> None:
    decision = build_decision(_priority(), _hourly())
    assert decision["dispatch_required"] is True
    assert decision["trigger_codes"] == ["000526"]
    assert decision["holding_trigger_count"] == 0
    assert decision["external_trigger_count"] == 1
    trigger = decision["triggers"][0]
    assert "SUCCESS_ARCHETYPE_RECALL_REUNDERWRITE_REQUIRED" in trigger["trigger_reasons"]
    assert trigger["success_archetype_similarity_score"] == 85.9134
    assert trigger["success_archetype_evidence_coverage"] == 1.0
    assert decision["formal_action_source"] == "FINALIZED_CANONICAL_ONLY"
    assert decision["formal_action_recomputed"] is False
    assert decision["formal_action_eligible"] is False
    assert decision["direct_formal_action_change_allowed"] is False
    assert decision["no_auto_trade"] is True


def test_runbei_similarity_alone_does_not_trigger_without_complete_evidence() -> None:
    decision = build_decision(_priority(coverage=0.75), _hourly())
    assert decision["dispatch_required"] is False
    assert decision["external_trigger_count"] == 0


def test_runbei_low_similarity_does_not_trigger_expensive_authority_research() -> None:
    decision = build_decision(_priority(similarity=69.999), _hourly())
    assert decision["dispatch_required"] is False


def test_runbei_non_priority_quant_status_does_not_trigger() -> None:
    decision = build_decision(_priority(quant_status="LOW_PRIORITY"), _hourly())
    assert decision["dispatch_required"] is False


def test_runbei_signal_digest_changes_when_material_recall_state_changes() -> None:
    first = build_decision(_priority(similarity=85.9134), _hourly())
    second = build_decision(_priority(similarity=87.0), _hourly())
    assert first["signal_digest"] != second["signal_digest"]


def test_success_archetype_workflow_run_is_exact_terminal_lineage_only() -> None:
    text = Path(".github/workflows/genge-success-archetype-recall.yml").read_text(encoding="utf-8")
    assert 'preferred="${{ github.event.workflow_run.id }}"' in text
    assert 'if [ "${{ github.event_name }}" = "workflow_run" ]; then' in text
    assert 'candidates+=("$preferred")' in text
    assert 'mapfile -t runs' in text
    assert 'else' in text
    # The fallback query must live only in the non-workflow_run branch.
    exact_block = text.split('if [ "${{ github.event_name }}" = "workflow_run" ]; then', 1)[1].split('else', 1)[0]
    assert 'actions/workflows/genge-candidate-terminal-review.yml/runs' not in exact_block
    assert 'test "$selected_run" = "$preferred"' in text
    assert 'test "$selected_artifact" != ""' in text
