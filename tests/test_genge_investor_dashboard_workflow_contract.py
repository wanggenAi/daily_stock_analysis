from pathlib import Path


def _workflow() -> str:
    return Path(".github/workflows/genge-investor-decision-dashboard.yml").read_text(encoding="utf-8")


def test_market_context_selects_latest_usable_artifact_even_during_rerun() -> None:
    workflow = _workflow()
    block = workflow.split("- name: Download latest usable full-A market context", 1)[1].split(
        "- name: Download event context when applicable", 1
    )[0]

    assert "genge-opportunity-discovery.yml/runs?per_page=60" in block
    assert "genge-opportunity-discovery.yml/runs?status=success" not in block
    assert 'select(.event == "schedule" or .event == "workflow_dispatch")' in block
    assert '.expired == false and .name == "genge-all-a-production-report"' in block
    assert "sort_by(.created_at) | reverse | .[0].id // empty" in block
    assert "actions/artifacts/${artifact_id}/zip" in block
    assert "MARKET_ARTIFACT_ID=${artifact_id}" in block


def test_stale_hourly_overlay_is_skipped_before_dashboard_and_live_overlay() -> None:
    workflow = _workflow()
    block = workflow.split("- name: Build and persist investor-first action dashboard", 1)[1].split(
        "- name: Publish investor-first summary", 1
    )[0]

    assert "canonical.get('snapshot_id')" in block
    assert "canonical.get('source_run_id')" in block
    assert "hourly.get('canonical_snapshot_id')" in block
    assert "hourly.get('canonical_source_run_id')" in block
    assert "actual_snapshot != expected_snapshot or actual_source != expected_source" in block
    assert "hourly_overlay=\"\"" in block
    assert '[ -z "$hourly_overlay" ] || args+=(--hourly "$hourly_overlay")' in block
    assert 'if [ -n "$hourly_overlay" ]; then' in block
    assert "Skipping stale/unverifiable optional hourly overlay; frozen Canonical remains authoritative." in block
    assert "investor_live_execution_overlay" in block


def test_manual_broker_quote_overlay_is_wired_as_execution_only_fallback() -> None:
    workflow = _workflow()
    block = workflow.split("- name: Build and persist investor-first action dashboard", 1)[1].split(
        "- name: Publish investor-first summary", 1
    )[0]

    assert "data/manual_execution_quotes/latest.json" in workflow
    assert "investor_manual_execution_quote_overlay" in workflow
    assert "tests/test_genge_investor_manual_execution_quote_overlay.py" in workflow
    assert 'if [ -s data/manual_execution_quotes/latest.json ]; then' in block
    assert "USER_CONFIRMED_BROKER_INTRADAY_QUOTE" in block
    assert "USER_CONFIRMED_BROKER_SCREENSHOT" in block
    assert "assert live['formal_trading_authority'] is False" in block
    assert "assert live['automatic_formal_buy_allowed'] is False" in block


def test_dashboard_capital_operation_sources_accept_only_authorized_mirrors() -> None:
    workflow = _workflow()
    block = workflow.split("- name: Build and persist investor-first action dashboard", 1)[1].split(
        "- name: Publish investor-first summary", 1
    )[0]

    assert "AUTHORIZED_CANONICAL_HOLDING_ACTION" in block
    assert "AUTHORIZED_CANONICAL_HOLDING_STAGED_ADD" in block
    assert "TERMINAL_FORMAL_BUY_MIRROR" in block
    assert "assert all(x['source'] in allowed_sources for x in c['operations'])" in block
    assert "assert all(x.get('authorization_proven') is True for x in c['operations'])" in block


def test_dashboard_consumes_reconciliation_from_same_authorized_artifact_and_fails_closed() -> None:
    workflow = _workflow()
    authority = workflow.split("- name: Locate latest successful authorized Canonical", 1)[1].split(
        "- name: Download latest usable Terminal BUY WAIT_PRICE REJECT truth", 1
    )[0]
    build = workflow.split("- name: Build and persist investor-first action dashboard", 1)[1].split(
        "- name: Publish investor-first summary", 1
    )[0]

    assert "holdings_reconciliation.json" in authority
    assert "canonical_sha256" in authority
    assert "GEN_GE_V31_HOLDINGS_RECONCILIATION_V1" in authority
    assert "HOLDINGS_IN_SYNC" in authority and "HOLDINGS_OUT_OF_SYNC" in authority
    assert "formal_holding_actions_currently_usable" in authority
    assert "HOLDINGS_RECONCILIATION=$reconciliation" in authority
    assert '--holdings-reconciliation "$HOLDINGS_RECONCILIATION"' in build
    assert "p['formal_holding_actions_currently_usable']" in build
    assert "assert all(not x.get('formal_action') for x in p['stock_portfolio']['rows'])" in build
    assert "AUTHORIZED_CANONICAL_HOLDING_STAGED_ADD" in build
    assert "tests/test_v311_dynamic_holding_profit_protection.py" in workflow
