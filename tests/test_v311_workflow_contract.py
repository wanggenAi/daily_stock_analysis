"""Static workflow contract for the frozen V3.1.1 production entrypoint."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def _workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_all_a_v311_one_shot_uses_strict_pit_bridge() -> None:
    text = _workflow("genge-all-a-v31-once.yml")

    assert "src.strategies.genge_opportunity_discovery.v311_production_bridge" in text
    assert "--source-csv reports/v31_review_enriched/v31_review_queue_enriched.csv" in text
    assert "v311_current_expectation_inputs.csv" in text
    assert "fresh_production_decision_authority" in text
    assert "src.strategies.genge_opportunity_discovery.production_decision_scan" not in text


def test_premarket_dispatches_authoritative_v311_workflow() -> None:
    text = _workflow("genge-opportunity-premarket.yml")

    assert "gh workflow run genge-all-a-v31-once.yml" in text
    assert "gh workflow run genge-opportunity-discovery.yml" not in text
    assert "V3.1.1 strict-PIT production bridge" in text


def test_legacy_discovery_is_explicitly_not_the_premarket_production_target() -> None:
    premarket = _workflow("genge-opportunity-premarket.yml")
    discovery = _workflow("genge-opportunity-discovery.yml")

    assert "legacy GenGe Opportunity Discovery remains research-only upstream" in premarket
    assert "name: GenGe Opportunity Discovery" in discovery


def test_legacy_risk_capped_signals_are_manual_research_only() -> None:
    text = _workflow("genge-risk-capped-opportunity-discovery.yml")

    assert "name: GenGe Legacy Risk-Capped Research (Manual)" in text
    assert "\n  schedule:" not in text
    assert "if: github.event_name == 'workflow_dispatch'" in text
    assert "not an authoritative GenGe V3.1.1 production signal source" in text
