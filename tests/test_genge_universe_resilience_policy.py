from __future__ import annotations

from datetime import date

import pytest

from src.strategies.genge_opportunity_discovery import universe_resilience_policy as policy


class _Status:
    error_code = "0"
    error_msg = "success"


class _Query(_Status):
    fields = ["code", "code_name", "ipoDate", "outDate", "type", "status"]

    def __init__(self, rows: list[list[str]]):
        self._rows = rows
        self._index = -1

    def next(self) -> bool:
        self._index += 1
        return self._index < len(self._rows)

    def get_row_data(self) -> list[str]:
        return self._rows[self._index]


def test_baostock_fallback_keeps_only_current_shanghai_shenzhen_stocks(monkeypatch) -> None:
    rows = [
        ["sh.600000", "浦发银行", "1999-11-10", "", "1", "1"],
        ["sh.688001", "华兴源创", "2019-07-22", "", "1", "1"],
        ["sz.000001", "平安银行", "1991-04-03", "", "1", "1"],
        ["sz.300001", "特锐德", "2009-10-30", "", "1", "1"],
        ["bj.430001", "北交测试", "2022-01-01", "", "1", "1"],
        ["sh.510300", "ETF", "2012-05-28", "", "5", "1"],
        ["sz.000999", "已退市", "2000-01-01", "2020-01-01", "1", "0"],
    ]
    monkeypatch.setattr(policy.bs, "login", lambda: _Status())
    monkeypatch.setattr(policy.bs, "query_stock_basic", lambda: _Query(rows))
    monkeypatch.setattr(policy.bs, "logout", lambda: _Status())
    monkeypatch.setattr(policy, "MIN_FALLBACK_ROWS", 4)

    result, audit = policy.fetch_baostock_universe(date(2026, 8, 15))

    assert [row["code"] for row in result] == ["000001", "300001", "600000", "688001"]
    by_code = {row["code"]: row for row in result}
    assert by_code["600000"]["board"] == "SSE_MAIN"
    assert by_code["688001"]["board"] == "STAR"
    assert by_code["000001"]["board"] == "SZSE_MAIN"
    assert by_code["300001"]["board"] == "CHINEXT"
    assert audit["status"] == "PUBLIC_PROVIDER_FALLBACK"
    assert audit["raw_security_count"] == 4


def test_baostock_fallback_marks_future_listing_ineligible(monkeypatch) -> None:
    rows = [
        ["sh.600000", "A", "1999-11-10", "", "1", "1"],
        ["sz.000001", "B", "1991-04-03", "", "1", "1"],
        ["sz.300001", "C", "2027-01-01", "", "1", "1"],
    ]
    monkeypatch.setattr(policy.bs, "login", lambda: _Status())
    monkeypatch.setattr(policy.bs, "query_stock_basic", lambda: _Query(rows))
    monkeypatch.setattr(policy.bs, "logout", lambda: _Status())
    monkeypatch.setattr(policy, "MIN_FALLBACK_ROWS", 3)

    result, _ = policy.fetch_baostock_universe(date(2026, 8, 15))
    by_code = {row["code"]: row for row in result}

    assert by_code["300001"]["exclusion_reason"] == "listing_after_as_of"


def test_baostock_fallback_fails_closed_on_partial_universe(monkeypatch) -> None:
    monkeypatch.setattr(policy.bs, "login", lambda: _Status())
    monkeypatch.setattr(
        policy.bs,
        "query_stock_basic",
        lambda: _Query([["sh.600000", "A", "1999-11-10", "", "1", "1"]]),
    )
    monkeypatch.setattr(policy.bs, "logout", lambda: _Status())
    monkeypatch.setattr(policy, "MIN_FALLBACK_ROWS", 2)

    with pytest.raises(RuntimeError, match="universe incomplete"):
        policy.fetch_baostock_universe(date(2026, 8, 15))


def test_build_universe_uses_fallback_only_after_primary_sources_fail(monkeypatch, tmp_path) -> None:
    def primary(**kwargs):
        raise RuntimeError("official blocked and no snapshot")

    fallback_rows = [
        {"code": "600000", "stock_name": "A", "exchange": "SSE", "board": "SSE_MAIN"}
    ]
    monkeypatch.setattr(policy, "_ORIGINAL_BUILD_ALL_A_UNIVERSE", primary)
    monkeypatch.setattr(
        policy,
        "fetch_baostock_universe",
        lambda as_of: (
            fallback_rows,
            {
                "status": "PUBLIC_PROVIDER_FALLBACK",
                "raw_security_count": 1,
                "sources": [],
            },
        ),
    )

    rows, audit = policy.build_all_a_universe(
        as_of=date(2026, 8, 15), stock_pool_dir=tmp_path
    )

    assert rows == fallback_rows
    assert audit["status"] == "PUBLIC_PROVIDER_FALLBACK"
    assert "official blocked" in audit["fetch_error"]


def test_custom_fetcher_path_preserves_original_core_contract(monkeypatch, tmp_path) -> None:
    calls = []

    def original(**kwargs):
        calls.append(kwargs)
        return [], {"status": "OK"}

    def custom(as_of):
        return [], {"status": "CUSTOM"}

    monkeypatch.setattr(policy, "_ORIGINAL_BUILD_ALL_A_UNIVERSE", original)

    policy.build_all_a_universe(
        as_of=date(2026, 8, 15), stock_pool_dir=tmp_path, fetcher=custom
    )

    assert calls[0]["fetcher"] is custom
