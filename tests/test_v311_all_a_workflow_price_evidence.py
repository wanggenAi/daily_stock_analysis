from pathlib import Path


def test_all_a_production_bridge_consumes_same_run_price_evidence() -> None:
    workflow = Path(".github/workflows/genge-all-a-v31-once.yml").read_text(encoding="utf-8")

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
