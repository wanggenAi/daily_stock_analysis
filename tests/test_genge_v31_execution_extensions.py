from datetime import date
from types import SimpleNamespace

import pandas as pd

from src.strategies.genge_opportunity_discovery.bank_valuation_execution import execute_rows
from src.strategies.genge_opportunity_discovery.resource_route_enrichment import should_upgrade


class _Loader:
    def load(self, code, *, years, fetch_valuation, fetch_financial):
        assert code == "600000"
        return SimpleNamespace(
            valuation_df=pd.DataFrame(
                [
                    {"date": "2026-08-20", "pb": 0.65},
                    {"date": "2026-08-21", "pb": 0.66},
                ]
            ),
            financial_df=pd.DataFrame(
                [
                    {"report_date": "2022-12-31", "disclosure_date": "2023-04-20", "roe": 10.0},
                    {"report_date": "2023-12-31", "disclosure_date": "2024-04-20", "roe": 10.5},
                    {"report_date": "2024-12-31", "disclosure_date": "2025-04-20", "roe": 11.0},
                    {"report_date": "2025-12-31", "disclosure_date": "2026-04-20", "roe": 11.5},
                ]
            ),
        )


def test_resource_name_plus_broad_resource_industry_upgrades_for_review():
    assert should_upgrade(
        {
            "stock_name": "紫金矿业",
            "industry": "有色金属",
            "valuation_primary_strategy_id": "general_reverse_earnings",
            "valuation_profile_used_for_routing": False,
        }
    )
    assert should_upgrade(
        {
            "stock_name": "洛阳钼业",
            "industry": "工业金属",
            "valuation_primary_strategy_id": "general_reverse_earnings",
            "valuation_profile_used_for_routing": False,
        }
    )


def test_resource_enrichment_does_not_treat_processor_or_generic_name_as_mine_owner():
    assert not should_upgrade(
        {
            "stock_name": "某某矿业",
            "industry": "有色冶炼加工",
            "valuation_primary_strategy_id": "general_reverse_earnings",
            "valuation_profile_used_for_routing": False,
        }
    )
    assert not should_upgrade(
        {
            "stock_name": "中国稀土",
            "industry": "稀土",
            "valuation_primary_strategy_id": "general_reverse_earnings",
            "valuation_profile_used_for_routing": False,
        }
    )


def test_bank_executor_uses_pit_pb_and_multi_year_roe_without_formal_buy():
    rows = execute_rows(
        [
            {
                "code": "600000",
                "stock_name": "示例银行",
                "valuation_primary_strategy_id": "bank_residual_income",
            }
        ],
        as_of=date(2026, 8, 23),
        loader=_Loader(),
        years=7,
        minimum_annual_roe_samples=3,
        maximum_annual_roe_samples=5,
        cost_of_equity=0.11,
        long_term_growth=0.03,
    )
    row = rows[0]
    assert row["bank_model_executed"] is True
    assert row["bank_model_state"] == "EXECUTED_RESEARCH_ONLY"
    assert row["bank_current_pb"] == 0.66
    assert row["bank_roe_sample_count"] == 4
    assert row["bank_fair_pb"] > 0
    assert row["formal_signal_eligible"] is False
    assert row["automatic_promotion_allowed"] is False
    assert row["no_auto_trade"] is True
