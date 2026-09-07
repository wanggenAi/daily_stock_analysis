from pathlib import Path


WORKFLOW = Path(".github/workflows/genge-candidate-terminal-review.yml")
HANDOFF = Path(".github/workflows/genge-v311-event-driven-authority-handoff.yml")
TRIGGER = Path(".github/workflows/genge-v311-explicit-production-trigger.yml")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_terminal_workflow_keeps_legacy_exact_postscan_lineage_fail_closed():
    text = _text(WORKFLOW)

    assert 'workflows: ["GenGe Postscan Research Pipeline"]' in text
    assert "upstream_run_id:" in text
    assert 'require_successful_main_run "$run_id" "GenGe Postscan Research Pipeline"' in text
    assert 'require_single_artifact "$run_id" "genge-postscan-research"' in text
    assert "selected exact postscan run ${run_id}; stale fallback forbidden" in text
    assert ".workflow_runs[0].id" not in text


def test_push_only_smoke_may_use_latest_successful_postscan_artifact():
    text = _text(WORKFLOW)

    assert "genge-postscan-research.yml/runs?branch=main&status=success&per_page=20" in text
    assert "Push-triggered code smoke has no production lineage" in text
    assert "selected smoke-validation postscan run ${candidate} with artifact ${artifact_id}" in text


def test_terminal_workflow_supports_exact_every_industry_plus_finalizer_lineage():
    text = _text(WORKFLOW)

    assert "research_run_id:" in text
    assert "finalizer_run_id:" in text
    assert 'require_successful_main_run "$INPUT_RESEARCH_RUN_ID" "GenGe V3.1.1 Every-Industry Research"' in text
    assert 'require_single_artifact "$INPUT_RESEARCH_RUN_ID" "genge-v31-every-industry-research"' in text
    assert 'require_successful_main_run "$INPUT_FINALIZER_RUN_ID" "GenGe V3.1.1 Production Finalizer"' in text
    assert 'require_single_artifact "$INPUT_FINALIZER_RUN_ID" "genge-v311-authoritative-canonical-${INPUT_RESEARCH_RUN_ID}"' in text
    assert "mode=EVERY_INDUSTRY_AUTHORIZED" in text
    assert "stale fallback forbidden" in text


def test_terminal_workflow_verifies_finalizer_authority_provenance():
    text = _text(WORKFLOW)

    assert "production_authority.json" in text
    assert "payload.get('authorized') is True" in text
    assert "canonical_source_run_id" in text
    assert "finalizer_run_id" in text
    assert "canonical_source_kind') == 'every-industry'" in text
    assert "source_workflow') == 'GenGe V3.1.1 Every-Industry Research'" in text
    assert "finalizer_authority_verified" in text


def test_terminalize_installs_runtime_dependencies_before_execution():
    text = _text(WORKFLOW)
    terminalize = text.split("\n  terminalize:\n", 1)[1]

    install_pos = terminalize.index("- name: Install repository runtime dependencies")
    resolve_pos = terminalize.index("- name: Resolve exact research lineage")
    execute_pos = terminalize.index("- name: Terminalize every surviving research candidate")
    assert install_pos < resolve_pos < execute_pos
    assert "python-version: \"3.11\"\n          cache: pip" in terminalize[:resolve_pos]
    assert "-r .github/requirements-ci.txt" in terminalize[install_pos:resolve_pos]


def test_modern_terminal_inputs_are_exact_and_formal_buy_is_mirror_only():
    text = _text(WORKFLOW)

    assert "v31_review_queue_enriched.csv" in text
    assert "production_decisions.csv ! -path '*/canonical_snapshot/*'" in text
    assert "terminal_formal_compat.csv" in text
    assert "long_term_formal_buy_eligible" in text
    assert "v31_buy_ready" in text
    assert "production_action" in text
    assert "valuation_confidence" in text
    assert "production_model_frozen" in text
    assert "decision_scope" in text
    assert "CANDIDATE" in text


def test_terminal_workflow_enforces_terminal_only_research_states():
    text = _text(WORKFLOW)

    assert "candidate_terminal_decision" in text
    assert "summary['research_limbo_count'] == 0" in text
    assert "summary['unauthorized_buy_count'] == 0" in text
    assert "{'BUY','WAIT_PRICE','REJECT'}" in text
    assert "formal_authority_unchanged" in text
    assert "no_auto_trade" in text
    assert "genge-candidate-terminal-decisions" in text


def test_event_handoff_orders_finalizer_terminal_then_fresh_consumer():
    text = _text(HANDOFF)

    finalizer_pos = text.index("genge-v311-production-finalizer.yml")
    terminal_pos = text.index("genge-candidate-terminal-review.yml", finalizer_pos)
    consumer_pos = text.index("genge-v311-authority-consumer-handoff.yml", terminal_pos)
    assert finalizer_pos < terminal_pos < consumer_pos
    assert '-f research_run_id="$industry_run_id"' in text
    assert '-f finalizer_run_id="$finalizer_run_id"' in text
    assert 'require_artifact "$terminal_run_id" "genge-candidate-terminal-decisions"' in text
    assert 'consumer_dispatch_path="EXPLICIT_POST_TERMINAL_CONSUMER_HANDOFF"' in text
    assert "REUSED_AUTOMATIC_CONSUMER_HANDOFF" not in text
    assert "Finalizer -> exact Candidate Terminal -> fresh Authority Consumer Handoff" in text


def test_run_production_marker_launches_full_authority_handoff():
    text = _text(TRIGGER)

    assert "contains(github.event.head_commit.message, '[run-production]')" in text
    assert "gh workflow run genge-v311-event-driven-authority-handoff.yml" in text
    assert "gh workflow run genge-opportunity-discovery.yml" not in text
