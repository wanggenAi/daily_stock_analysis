from pathlib import Path


def _workflow() -> str:
    return Path(".github/workflows/genge-all-a-v31-once.yml").read_text(encoding="utf-8")


def test_all_a_production_bridge_consumes_same_run_price_evidence() -> None:
    workflow = _workflow()

    production_step = workflow.split(
        "- name: Build GenGe V3.1.1 strict-PIT production candidate and holding decisions",
        1,
    )[1].split("- name: Build native canonical V3.1.1 snapshot", 1)[0]

    assert (
        "--source-csv reports/v31_review_enriched/v31_review_queue_enriched.csv"
        in production_step
    )
    assert (
        "--evidence-csv reports/final_valuation_source/all_a_quant_screen.csv"
        in production_step
    )
    assert "--holdings-md CURRENT_HOLDINGS.md" in production_step


def test_all_a_merges_specialized_execution_before_v31_authority() -> None:
    workflow = _workflow()

    specialized = workflow.index("- name: Execute specialized models")
    bank = workflow.index("- name: Execute bank residual-income valuation")
    insurance = workflow.index("- name: Execute insurance appraisal")
    resource = workflow.index("- name: Execute four-scenario resource NAV")
    authoritative_merge = workflow.index(
        "- name: Merge specialized valuation facts into authoritative research"
    )
    v31 = workflow.index("- name: Build frozen V3.1 queue")

    assert specialized < authoritative_merge
    assert bank < authoritative_merge
    assert insurance < authoritative_merge
    assert resource < authoritative_merge < v31
    assert (
        "python -m src.strategies.genge_opportunity_discovery."
        "specialized_valuation_authoritative_merge "
        "--report-root reports/valuation_research_queue"
        in workflow
    )
