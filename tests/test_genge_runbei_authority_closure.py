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


def test_runbei_signal_digest_changes_when_similarity_band_changes() -> None:
    first = build_decision(_priority(similarity=84.999), _hourly())
    second = build_decision(_priority(similarity=85.0), _hourly())
    assert first["signal_digest"] != second["signal_digest"]


def test_success_archetype_workflow_uses_exact_runtime_resolver() -> None:
    text = Path(".github/workflows/genge-success-archetype-recall.yml").read_text(encoding="utf-8")
    assert 'requested="${{ github.event.workflow_run.id }}"' in text
    assert "terminal_producer_runtime" in text
    assert '--requested-run-id "$requested"' in text
    assert "TERMINAL_RESOLUTION_STATUS == 'SELECTED'" in text
    assert "TERMINAL_RESOLUTION_STATUS == 'NOT_FOUND'" in text
    assert "lineage_provenance.json" in text
    assert "stale_global_fallback_allowed" in text


def test_success_archetype_forbids_old_chronological_global_fallback() -> None:
    workflow = Path(".github/workflows/genge-success-archetype-recall.yml").read_text(encoding="utf-8")
    runtime = Path("src/strategies/genge_opportunity_discovery/terminal_producer_runtime.py").read_text(encoding="utf-8")
    pure = Path("src/strategies/genge_opportunity_discovery/terminal_producer_lineage.py").read_text(encoding="utf-8")

    assert 'fallback_reason="terminalize_skipped_noop_wrapper"' not in workflow
    assert '.created_at <= $cutoff' not in workflow
    assert 'RECALL_NOOP=true' not in workflow
    assert "latest successful run" in pure
    assert "There is deliberately no chronological" in pure
    assert "stale/global fallback forbidden" in runtime
    assert "MAX_LINEAGE_HOPS = 12" in runtime
    assert "MAX_INSPECTED_RUNS = 100" in runtime


def test_success_archetype_validates_terminal_artifact_schema_identity_and_provenance() -> None:
    runtime = Path("src/strategies/genge_opportunity_discovery/terminal_producer_runtime.py").read_text(encoding="utf-8")
    assert "candidate_terminal_decisions.csv" in runtime
    assert "candidate_terminal_summary.json" in runtime
    assert "terminal_lineage.json" in runtime
    assert "candidate count mismatch" in runtime
    assert "terminal CSV schema incomplete" in runtime
    assert "terminal lineage manifest does not match producing run metadata" in runtime
    assert "_candidate_identity" in runtime
    assert "formal_authority_unchanged" in runtime
    assert "hard_gate_unknown_is_pass" in runtime
    assert "no_auto_trade" in runtime


def test_success_archetype_not_found_is_explicit_resolution_not_fake_recall() -> None:
    text = Path(".github/workflows/genge-success-archetype-recall.yml").read_text(encoding="utf-8")
    assert "Publish exhausted-lineage resolution artifact" in text
    assert "genge-success-archetype-resolution-" in text
    assert "Upload success-archetype research artifact" in text
    assert "if: env.TERMINAL_RESOLUTION_STATUS == 'SELECTED'" in text
    assert "if: env.RECALL_NOOP != 'true'" not in text
    assert "'canonical_authority_unchanged': True" in text
    assert "'no_auto_trade': True" in text
