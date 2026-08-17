import inspect

import pytest

from src.strategies.genge_opportunity_discovery.real_estate_nav_valuation import (
    assess_developer_horizon_liquidity,
    bridge_developer_equity_nav,
    collect_developer_evidence,
    reverse_implied_project_recovery,
    value_project_equity_cash_flows,
)


def _project(project_id="project-a", ownership=0.6):
    return value_project_equity_cash_flows(
        project_id=project_id,
        annual_project_equity_cash_flows_100pct={1: -20.0, 2: 80.0, 3: 100.0},
        economic_ownership=ownership,
        required_return=0.10,
    )


def test_project_nav_discounts_explicit_remaining_equity_cash_flows_and_ownership():
    result = _project()

    expected_100pct = -20.0 / 1.10 + 80.0 / (1.10**2) + 100.0 / (1.10**3)
    assert result.pv_100pct_project_equity_cash_flows == pytest.approx(expected_100pct)
    assert result.attributable_project_nav == pytest.approx(expected_100pct * 0.6)
    assert result.status == "OK"


def test_project_nav_allows_negative_early_cash_flow_but_has_no_terminal_value_shortcut():
    signature = inspect.signature(value_project_equity_cash_flows)

    assert "terminal_value" not in signature.parameters
    assert "inventory_book_value" not in signature.parameters
    assert "inventory_haircut" not in signature.parameters

    result = value_project_equity_cash_flows(
        project_id="development",
        annual_project_equity_cash_flows_100pct={1: -100.0, 2: -20.0, 3: 180.0},
        economic_ownership=1.0,
        required_return=0.10,
    )
    assert result.valuation_model_applicable is True


def test_project_nav_requires_explicit_ownership_and_required_return():
    signature = inspect.signature(value_project_equity_cash_flows)

    assert signature.parameters["economic_ownership"].default is inspect._empty
    assert signature.parameters["required_return"].default is inspect._empty


def test_project_nav_rejects_invalid_ownership():
    result = value_project_equity_cash_flows(
        project_id="a",
        annual_project_equity_cash_flows_100pct={1: 100.0},
        economic_ownership=1.2,
        required_return=0.10,
    )

    assert result.valuation_model_applicable is False
    assert result.status == "INVALID_OR_MISSING_ECONOMIC_OWNERSHIP"


def test_developer_equity_bridge_sums_unique_project_nav_and_only_unallocated_corporate_items():
    first = _project("a", 0.6)
    second = _project("b", 0.8)

    result = bridge_developer_equity_nav(
        project_results=[first, second],
        unrestricted_cash=30.0,
        non_project_asset_value=20.0,
        corporate_interest_bearing_debt_not_in_projects=15.0,
        corporate_liability_pv_not_in_projects=5.0,
        explicit_equity_adjustment=2.0,
        current_market_cap=100.0,
        total_common_shares=10.0,
    )

    expected_project_nav = first.attributable_project_nav + second.attributable_project_nav
    expected_equity = expected_project_nav + 30.0 + 20.0 - 15.0 - 5.0 + 2.0
    assert result.attributable_project_nav == pytest.approx(expected_project_nav)
    assert result.fair_equity_nav == pytest.approx(expected_equity)
    assert result.fair_nav_per_share == pytest.approx(expected_equity / 10.0)
    assert result.margin_of_safety == pytest.approx(expected_equity / 100.0 - 1.0)
    assert result.status == "OK"


def test_developer_equity_bridge_rejects_duplicate_project_ids():
    result = bridge_developer_equity_nav(
        project_results=[_project("same"), _project("same")],
        unrestricted_cash=30.0,
        non_project_asset_value=20.0,
        corporate_interest_bearing_debt_not_in_projects=15.0,
        corporate_liability_pv_not_in_projects=5.0,
    )

    assert result.valuation_model_applicable is False
    assert result.fair_equity_nav is None
    assert result.status == "DUPLICATE_PROJECT_ID"


def test_developer_bridge_does_not_accept_raw_inventory_as_nav_input():
    signature = inspect.signature(bridge_developer_equity_nav)

    assert "inventory_book_value" not in signature.parameters
    assert "inventory_haircut" not in signature.parameters
    assert "project_results" in signature.parameters


def test_reverse_project_recovery_preserves_discount_or_negative_market_message():
    ratio, status = reverse_implied_project_recovery(
        current_market_cap=60.0,
        reference_attributable_project_nav=100.0,
        non_project_net_asset_value=20.0,
    )
    negative, negative_status = reverse_implied_project_recovery(
        current_market_cap=10.0,
        reference_attributable_project_nav=100.0,
        non_project_net_asset_value=20.0,
    )

    assert ratio == pytest.approx(0.4)
    assert status == "OK"
    assert negative == pytest.approx(-0.1)
    assert negative_status == "OK"


def test_horizon_liquidity_counts_expected_collections_not_contract_sales_face_value():
    result = assess_developer_horizon_liquidity(
        unrestricted_cash=50.0,
        expected_cash_collections_within_horizon=80.0,
        debt_principal_due_within_horizon=60.0,
        committed_land_and_construction_outflows_within_horizon=50.0,
        other_committed_cash_outflows_within_horizon=10.0,
    )

    assert result.horizon_liquidity_surplus == pytest.approx(10.0)
    assert result.coverage_of_committed_outflows == pytest.approx(130.0 / 120.0)
    assert result.status == "OK"


def test_liquidity_api_has_no_all_debt_or_contract_sales_shortcut():
    signature = inspect.signature(assess_developer_horizon_liquidity)

    assert "total_debt" not in signature.parameters
    assert "contracted_sales" not in signature.parameters
    assert "expected_cash_collections_within_horizon" in signature.parameters
    assert "debt_principal_due_within_horizon" in signature.parameters


def test_developer_evidence_keeps_inventory_and_impairment_as_evidence_not_magic_nav():
    result = collect_developer_evidence(
        contracted_sales_growth=-0.07,
        recognized_revenue_growth=-0.12,
        inventory_book_value=1000.0,
        inventory_impairment_charge=50.0,
        new_land_equity_spend=88.0,
        interest_bearing_debt=236.0,
        average_financing_cost=0.028,
    )

    assert result.inventory_book_value == pytest.approx(1000.0)
    assert result.inventory_impairment_charge == pytest.approx(50.0)
    assert result.evidence_completeness == pytest.approx(7 / 14)
    assert "cash_collection_ratio" in result.missing_fields
    assert not hasattr(result, "quality_score")
    assert not hasattr(result, "inventory_nav")
