from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.strategies.genge_opportunity_discovery.all_a_full_scan import (
    AllAScanConfig,
    RULE_VERSION,
    _add_exit_validation_reference_specs,
    _apply_position_budget,
    _board_from_exchange_row,
    _build_signal_state_rows,
    _changes,
    _current_passed_profile_codes,
    _exit_profiles,
    _exit_profile_strategy_health,
    _listing_row,
    _load_previous_watchlist_state,
    _merge_exact_exit_histories,
    _fundamentals,
    _research_queue,
    apply_universe_filters,
    audit_price_mapping,
    build_actionable_execution_list,
    build_daily_candidate_top5,
    build_daily_signals as build_daily_signals_production,
    build_price_plan,
    classify_candidate,
    enrich_exit_profile,
    load_board_rules,
    mark_listings_after_as_of,
    price_mapping_ratio_at_date,
    quant_screen,
    resistance_levels,
    select_exit_profile_exploration_rows,
    select_exit_validation_reference_rows,
    strict_candidate_checks,
    strict_official_evidence_audit,
)
from src.strategies.genge_opportunity_discovery.exit_profile import (
    MAX_RUN_GAP_OUTCOME_RATIO,
    MIN_PROFILE_SAMPLE_COUNT,
    MIN_OUTCOME_REPLAY_COVERAGE_RATIO,
    MIN_RECENT_2Y_SAMPLE_COUNT,
    PROFILE_SAMPLE_SPACING_SESSIONS,
    _exchange_session_continuity,
    _price_mapping_regime_stable,
    _price_setup_samples,
    _cohort_period_samples,
    _cohort_validation,
    _history_digest,
    _outcome_replay_quality,
    _status_with_replay_quality,
    _status_for,
    _triggered_entry,
    refresh_exit_profiles_from_price_history,
)
from src.strategies.genge_opportunity_discovery.live_exit_policy import (
    LIVE_BALANCED_EXIT_POLICY_VERSION,
    REFERENCE_EXECUTION_STATUS,
    evaluate_live_balanced_v7_exit,
)


def build_daily_signals(**kwargs):
    """Keep legacy lifecycle fixtures explicit about an unchanged price basis."""

    if kwargs.get("adjusted_histories") is not None or kwargs.get("raw_histories") is not None:
        return build_daily_signals_production(**kwargs)
    previous = {
        str(code): dict(row) for code, row in dict(kwargs.get("previous") or {}).items()
    }
    for code, row in previous.items():
        lifecycle = str(row.get("signal_lifecycle_state") or "")
        if lifecycle in {"ENTRY_PENDING", "BREAKOUT_CONFIRMED_ENTRY_PENDING"} or (
            not lifecycle and row.get("user_visible_level") == "STRICT_REVIEW_READY"
        ):
            row.setdefault("signal_plan_adjustment_ratio", 1.0)
            row.setdefault(
                "signal_plan_origin_trade_date",
                row.get("signal_observed_through_date") or row.get("latest_trade_date"),
            )
        if lifecycle in {"ENTRY_TRIGGER_OBSERVED", "POSITION_REVIEW"}:
            row.setdefault("entry_adjustment_ratio", 1.0)
            row.setdefault(
                "entry_observation_trade_date",
                row.get("signal_observed_through_date") or row.get("latest_trade_date"),
            )
    kwargs["previous"] = previous
    for argument in ("current_market_rows", "current_rows"):
        rows = []
        for item in kwargs.get(argument) or []:
            local = dict(item)
            before = previous.get(str(local.get("code") or "").zfill(6), {})
            if before.get("signal_plan_adjustment_ratio") not in {None, ""}:
                local.setdefault("signal_plan_adjustment_ratio_status", "OK")
                local.setdefault(
                    "signal_plan_adjustment_ratio_current",
                    before["signal_plan_adjustment_ratio"],
                )
            if before.get("entry_adjustment_ratio") not in {None, ""}:
                local.setdefault("entry_date_adjustment_ratio_status", "OK")
                local.setdefault(
                    "entry_date_adjustment_ratio_current", before["entry_adjustment_ratio"],
                )
            rows.append(local)
        kwargs[argument] = rows
    return build_daily_signals_production(**kwargs)


def _history(*, adjusted: bool = False, corporate_action: bool = False) -> pd.DataFrame:
    dates = pd.bdate_range("2021-01-04", periods=1250)
    close = np.concatenate([
        np.linspace(20.0, 12.0, 850),
        np.linspace(12.0, 10.0, 220),
        np.linspace(10.0, 11.8, 180),
    ])
    if not adjusted and corporate_action:
        close = close.copy()
        close[:700] *= 2.0
    high = close * 1.02
    low = close * .98
    # Repeated, prominent real resistance pivots.
    for index in (1170, 1195, 1220):
        high[index] = 13.5
    frame = pd.DataFrame({
        "date": dates.date,
        "open": close * .995,
        "close": close,
        "high": high,
        "low": low,
        "volume": np.linspace(1_000_000, 2_000_000, len(dates)),
        "amount": close * np.linspace(1_000_000, 2_000_000, len(dates)),
    })
    for column in ("open", "high", "low", "close"):
        frame[f"raw_{column}"] = frame[column]
    frame["adjustment_ratio"] = 1.0
    return frame


def _mapping_history(points: list[tuple[str, float]]) -> pd.DataFrame:
    closes = [value for _trade_date, value in points]
    return pd.DataFrame({
        "date": [pd.Timestamp(trade_date).date() for trade_date, _value in points],
        "open": closes, "high": closes, "low": closes, "close": closes,
        "volume": [1_000.0] * len(points),
    })


def test_price_history_exit_refresh_replaces_stale_seed_with_traceable_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.strategies.genge_opportunity_discovery.exit_profile as exit_profile

    output = tmp_path / "exit_profile.csv"
    output.write_text(
        "code,stock_name,balanced_exit_historical_profile,signal_count\n000001,旧名称,PASSED,999\n",
        encoding="utf-8",
    )
    samples = [
        {"as_of_date": date(2026, 1, 1), "return": 3.0, "drawdown": -4.0}
        for _ in range(30)
    ]
    monkeypatch.setattr(exit_profile, "_price_setup_samples", lambda **_kwargs: samples)

    path, summary = refresh_exit_profiles_from_price_history(
        output_file=output,
        candidates=[{"code": "000001", "stock_name": "新名称"}],
        histories={"000001": _history(adjusted=True)},
        as_of=date(2026, 7, 22),
    )
    row = pd.read_csv(path, dtype={"code": str}).iloc[0]

    assert row["stock_name"] == "新名称"
    assert row["signal_count"] == 30
    assert row["balanced_exit_historical_profile"] == "PASSED"
    assert row["exit_profile_entry_mode"] == "pullback"
    assert row["pullback_profile_status"] == "PASSED"
    assert row["breakout_profile_status"] == "PASSED"
    assert str(row["profile_data_version"]).startswith("sha256:")
    assert summary["strict_metadata_eligible_count"] == 1
    assert summary["sample_spacing_sessions"] == PROFILE_SAMPLE_SPACING_SESSIONS
    assert summary["minimum_profile_sample_count"] == MIN_PROFILE_SAMPLE_COUNT
    assert summary["minimum_recent_2y_sample_count"] == MIN_RECENT_2Y_SAMPLE_COUNT


def test_signal_state_rejects_partially_corrupt_rows(tmp_path: Path) -> None:
    state_file = tmp_path / "last_all_a_state.json"
    state_file.write_text(
        json.dumps({
            "state_schema_version": 2,
            "by_code": {
                "000001": {"code": "000001", "signal_lifecycle_state": "ENTRY_PENDING"},
                "000002": "truncated-row",
            },
        }),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="invalid row"):
        _load_previous_watchlist_state(state_file)


def test_fundamental_fetch_prioritizes_exit_profile_passed_codes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.strategies.genge_opportunity_discovery.all_a_full_scan as all_a

    calls: list[str] = []

    class FakeLoader:
        def __init__(self, _cache_dir: Path) -> None:
            pass

        def load(self, code: str, **_kwargs):
            calls.append(code)
            return SimpleNamespace(
                valuation_df=pd.DataFrame({"date": ["2026-07-23"], "pe": [10.0]}),
                financial_df=pd.DataFrame({"date": ["2026-07-23"], "roe": [12.0]}),
                provider_errors={},
            )

    monkeypatch.setattr(all_a, "PublicFundamentalLoader", FakeLoader)
    rows = [
        {"code": "000001", "stock_name": "高排名", "industry": "银行", "quant_rank": 1, "quant_status": "PRIORITY_RESEARCH"},
        {"code": "000088", "stock_name": "退出通过", "industry": "港口", "quant_rank": 50, "quant_status": "SECONDARY_RESEARCH"},
    ]
    histories = {code: _history(adjusted=True) for code in ("000001", "000088")}
    config = AllAScanConfig(
        as_of=date(2026, 7, 23), next_trade_date=date(2026, 7, 24),
        output_dir=tmp_path / "out", stock_pool_output=tmp_path / "pool.csv",
        fundamental_cache_dir=tmp_path / "fundamentals", evidence_queue_size=2,
        fundamental_limit=1,
    )

    inputs, errors = _fundamentals(rows, histories, config, priority_codes=["000088"])

    by_code = {item.code: item for item in inputs}
    assert calls == ["000088"]
    assert by_code["000088"].financial_df is not None
    assert by_code["000001"].financial_df is None
    assert not errors


def test_required_exit_profile_code_outside_top_queue_is_included_and_fetched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.strategies.genge_opportunity_discovery.all_a_full_scan as all_a

    calls: list[str] = []

    class FakeLoader:
        def __init__(self, _cache_dir: Path) -> None:
            pass

        def load(self, code: str, **_kwargs):
            calls.append(code)
            return SimpleNamespace(
                valuation_df=pd.DataFrame({"date": ["2026-07-23"], "pe": [10.0]}),
                financial_df=pd.DataFrame({"date": ["2026-07-23"], "roe": [12.0]}),
                provider_errors={},
            )

    monkeypatch.setattr(all_a, "PublicFundamentalLoader", FakeLoader)
    rows = [
        {
            "code": "000001", "stock_name": "Top80", "industry": "银行",
            "quant_rank": 1, "quant_status": "PRIORITY_RESEARCH",
        },
        {
            "code": "000088", "stock_name": "探索画像通过", "industry": "港口",
            "quant_rank": 81, "quant_status": "PRIORITY_RESEARCH",
        },
    ]
    histories = {code: _history(adjusted=True) for code in ("000001", "000088")}
    config = AllAScanConfig(
        as_of=date(2026, 7, 23), next_trade_date=date(2026, 7, 24),
        output_dir=tmp_path / "out", stock_pool_output=tmp_path / "pool.csv",
        fundamental_cache_dir=tmp_path / "fundamentals", evidence_queue_size=1,
        fundamental_limit=0,
    )

    inputs, errors = _fundamentals(
        rows, histories, config,
        priority_codes=["000088"], required_codes=["000088"],
    )

    by_code = {item.code: item for item in inputs}
    assert set(by_code) == {"000001", "000088"}
    assert calls == ["000088"]
    assert by_code["000088"].financial_df is not None
    assert by_code["000001"].financial_df is None
    assert not errors


def test_research_queue_uses_non_rejected_low_priority_fallback_without_reordering_primary() -> None:
    rows = [
        {"code": "000001", "quant_rank": 1, "quant_status": "SECONDARY_RESEARCH", "hard_blockers": ""},
        {"code": "000002", "quant_rank": 2, "quant_status": "LOW_PRIORITY", "hard_blockers": ""},
        {"code": "000003", "quant_rank": 3, "quant_status": "HARD_REJECT", "hard_blockers": "limit"},
        {"code": "000004", "quant_rank": 4, "quant_status": "LOW_PRIORITY", "hard_blockers": ""},
    ]

    queue = _research_queue(rows, limit=3)

    assert [row["code"] for row in queue] == ["000001", "000002", "000004"]
    assert all(row["quant_status"] != "HARD_REJECT" for row in queue)


def test_exit_validation_reference_is_stable_diverse_and_fixed_across_exclusions() -> None:
    rows = []
    for board_index, board in enumerate(("SSE_MAIN", "SZSE_MAIN", "STAR", "CHINEXT"), 1):
        for index in range(8):
            rows.append({
                "code": f"{board_index}{index:05d}", "board": board,
                "industry": f"行业{index % 4}", "quant_status": "LOW_PRIORITY",
                "hard_blockers": "", "quant_rank": index + 1,
            })
    rows.append({
        "code": "999999", "board": "SSE_MAIN", "industry": "排除",
        "quant_status": "HARD_REJECT", "hard_blockers": "price_limit_risk",
    })

    first = select_exit_validation_reference_rows(rows, exclude_codes=["100000", "999999"], per_board=4)
    second = select_exit_validation_reference_rows(reversed(rows), exclude_codes=["100000", "999999"], per_board=4)
    without_exclusions = select_exit_validation_reference_rows(rows, exclude_codes=[], per_board=4)

    assert [row["code"] for row in first] == [row["code"] for row in second]
    assert [row["code"] for row in first] == [row["code"] for row in without_exclusions]
    assert {board: sum(row["board"] == board for row in first) for board in {row["board"] for row in first}} == {
        "SSE_MAIN": 4, "SZSE_MAIN": 4, "STAR": 4, "CHINEXT": 4,
    }


def test_reference_overlap_does_not_replace_candidate_breakout_plan() -> None:
    rules = load_board_rules("config/board_risk_rules.yaml")
    specs = {
        "600001": {
            "entry_mode": "breakout",
            "breakout_volume_ratio": 9.9,
            "max_chase_atr_multiple": 0.1,
            "volatility_multiplier": 0.8,
            "trigger_window_days": 10,
        },
    }

    _add_exit_validation_reference_specs(
        specs,
        [
            {"code": "600001", "board": "SSE_MAIN"},
            {"code": "600002", "board": "SSE_MAIN"},
        ],
        rules,
    )

    assert specs["600001"]["entry_mode"] == "breakout"
    assert specs["600001"]["breakout_volume_ratio"] == 9.9
    assert specs["600002"]["entry_mode"] == "pullback"
    assert specs["600002"]["breakout_volume_ratio"] == rules["SSE_MAIN"].breakout_volume_ratio
    assert specs["600002"]["minimum_history_rows"] == 800
    assert specs["600002"]["minimum_turnover"] == 20_000_000
    assert specs["600002"]["max_5d_return_pct"] == 18.0
    assert specs["600002"]["max_10d_return_pct"] == 28.0


def test_equal_length_exact_history_replaces_rounded_qfq_history() -> None:
    ordinary = pd.DataFrame({
        "date": [date(2026, 7, 30), date(2026, 7, 31)],
        "close": [9.88, 9.99],
    })
    exact = pd.DataFrame({
        "date": [date(2026, 7, 30), date(2026, 7, 31)],
        "close": [9.876543, 9.987654],
        "raw_close": [19.76, 19.98],
        "adjustment_ratio": [2.0003, 2.00047],
    })

    merged = _merge_exact_exit_histories(
        {"600001": ordinary}, {"600001": exact},
    )

    assert merged["600001"] is exact
    assert "adjustment_ratio" in merged["600001"].columns
    assert merged["600001"].iloc[-1]["close"] == pytest.approx(9.987654)


def test_exit_profile_exploration_is_weekly_deterministic_and_diverse() -> None:
    rows = [
        {
            "code": f"{index:06d}",
            "board": "SSE_MAIN" if index % 2 else "SZSE_MAIN",
            "industry": f"行业{index % 12}",
            "quant_status": (
                "PRIORITY_RESEARCH" if index % 3 else "SECONDARY_RESEARCH"
            ),
            "quant_score": 90.0 - index / 10,
        }
        for index in range(1, 81)
    ]
    rows.extend([
        {
            "code": "900001", "industry": "排除行业",
            "quant_status": "PRIORITY_RESEARCH", "quant_score": 99.0,
        },
        {
            "code": "900002", "industry": "拒绝行业",
            "quant_status": "LOW_PRIORITY", "quant_score": 99.0,
        },
    ])

    first = select_exit_profile_exploration_rows(
        rows,
        exclude_codes=["900001"],
        as_of=date(2026, 7, 29),
        prior_validated_codes=["000007", "000005"],
        limit=20,
    )
    reordered = select_exit_profile_exploration_rows(
        reversed(rows),
        exclude_codes=["900001"],
        as_of=date(2026, 7, 29),
        prior_validated_codes=["000005", "000007"],
        limit=20,
    )

    assert [row["code"] for row in first] == [row["code"] for row in reordered]
    assert [row["code"] for row in first[:2]] == ["000005", "000007"]
    assert all(
        row["exit_profile_exploration_reason"]
        == "PRIOR_VALIDATED_PROFILE_REFRESH"
        for row in first[:2]
    )
    assert len(first) == 20
    assert len({row["code"] for row in first}) == 20
    assert "900001" not in {row["code"] for row in first}
    assert "900002" not in {row["code"] for row in first}
    assert all(
        row["quant_status"] in {"PRIORITY_RESEARCH", "SECONDARY_RESEARCH"}
        for row in first
    )
    assert len({row["industry"] for row in first[:12]}) == 12
    assert all(
        row["exit_profile_exploration_rotation_bucket"] == "2026-W31"
        for row in first
    )


def test_exit_profile_exploration_rotates_in_a_new_iso_week() -> None:
    rows = [
        {
            "code": f"{index:06d}", "industry": "同一行业",
            "quant_status": "PRIORITY_RESEARCH", "quant_score": 50.0,
        }
        for index in range(1, 101)
    ]

    first_week = select_exit_profile_exploration_rows(
        rows, exclude_codes=(), as_of=date(2026, 7, 29), limit=10,
    )
    next_week = select_exit_profile_exploration_rows(
        rows, exclude_codes=(), as_of=date(2026, 8, 5), limit=10,
    )

    assert {row["code"] for row in first_week} != {row["code"] for row in next_week}
    assert {
        row["exit_profile_exploration_rotation_bucket"] for row in next_week
    } == {"2026-W32"}


def test_exit_profile_priority_excludes_stale_candidates_outside_current_queue() -> None:
    candidates = [{"code": "000001"}, {"code": "000002"}, {"code": "000001"}]
    profiles = {
        "000001": {"exit_profile_status": "PASSED"},
        "000002": {"exit_profile_status": "FAILED"},
        "000088": {"exit_profile_status": "PASSED"},
    }

    assert _current_passed_profile_codes(candidates, profiles) == ["000001"]


def test_exit_profile_uses_independent_sample_thresholds() -> None:
    assert _status_for([2.0] * MIN_PROFILE_SAMPLE_COUNT, [-5.0] * MIN_PROFILE_SAMPLE_COUNT) == "PASSED"
    assert _status_for([2.0] * 5, [-5.0] * 5) == "NOT_AVAILABLE"


def test_strict_plan_reuses_prepared_resistance_pivots_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.strategies.genge_opportunity_discovery.exit_profile as exit_profile

    history = exit_profile.prepare_price_frame(_history(adjusted=True)).tail(500)
    calls = 0
    original = exit_profile._resistance_pivots

    def capture_pivots(*args, **kwargs):
        nonlocal calls
        calls += 1
        assert kwargs["history_is_prepared"] is True
        return original(*args, **kwargs)

    monkeypatch.setattr(exit_profile, "_resistance_pivots", capture_pivots)
    exit_profile._strict_point_in_time_plan_mode(
        setup_history=history,
        adjustment_ratio=float(history.iloc[-1]["adjustment_ratio"]),
        max_chase_atr_multiple=.35,
        volatility_multiplier=1.0,
        history_is_prepared=True,
    )

    assert calls == 1


def test_trigger_entry_memoizes_pure_gates_with_complete_spec_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.strategies.genge_opportunity_discovery.exit_profile as exit_profile

    dates = pd.bdate_range("2026-01-01", periods=32)
    frame = pd.DataFrame({
        "date": dates.date, "open": [100.0] * 32, "high": [101.0] * 32,
        "low": [99.0] * 32, "close": [100.0] * 32,
        "volume": [1_000.0] * 32, "amount": [100_000.0] * 32,
        "raw_open": [100.0] * 32, "raw_high": [101.0] * 32,
        "raw_low": [99.0] * 32, "raw_close": [100.0] * 32,
        "adjustment_ratio": [1.0] * 32,
    })
    calls = {"strict": 0, "observable": 0}

    def strict(**_kwargs):
        calls["strict"] += 1
        return "pullback"

    def observable(*_args, **_kwargs):
        calls["observable"] += 1
        return True

    monkeypatch.setattr(exit_profile, "_strict_point_in_time_plan_mode", strict)
    monkeypatch.setattr(exit_profile, "_observable_setup_gates_pass", observable)
    monkeypatch.setattr(
        exit_profile, "_session_window_contiguous", lambda *_args, **_kwargs: True,
    )
    strict_cache: dict[tuple[int, float, float, float], str] = {}
    observable_cache: dict[tuple[int, int, float, float, float], bool] = {}
    common = {
        "frame": frame, "setup_index": 20,
        "breakout_volume_ratio": 1.2, "max_chase_atr_multiple": .35,
        "volatility_multiplier": 1.0, "enforce_strict_setup_gates": True,
        "strict_mode_cache": strict_cache,
        "observable_gate_cache": observable_cache,
        "frame_is_prepared": True,
    }

    first = _triggered_entry(entry_mode="pullback", **common)
    first_counts = dict(calls)
    repeated = _triggered_entry(entry_mode="pullback", **common)
    rejected_mode = _triggered_entry(entry_mode="breakout", **common)

    assert repeated == first
    assert rejected_mode is None
    assert calls == first_counts == {"strict": 1, "observable": 1}

    _triggered_entry(
        entry_mode="pullback", **{
            **common, "max_chase_atr_multiple": .45,
        },
    )
    assert calls == {"strict": 2, "observable": 1}
    _triggered_entry(
        entry_mode="pullback", **{
            **common, "minimum_turnover": 1.0,
        },
    )
    assert calls == {"strict": 2, "observable": 2}


def test_refresh_shares_gate_caches_between_entry_modes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.strategies.genge_opportunity_discovery.exit_profile as exit_profile

    cache_ids: list[tuple[int, int]] = []

    def capture_caches(**kwargs):
        cache_ids.append((
            id(kwargs["strict_mode_cache"]), id(kwargs["observable_gate_cache"]),
        ))
        return []

    monkeypatch.setattr(exit_profile, "_price_setup_samples", capture_caches)
    history = _history(adjusted=True)
    refresh_exit_profiles_from_price_history(
        output_file=tmp_path / "exit_profile.csv",
        candidates=[{"code": "000001", "stock_name": "候选", "board": "SZSE_MAIN"}],
        histories={"000001": history},
        as_of=max(history["date"]),
    )

    assert len(cache_ids) == 2
    assert cache_ids[0] == cache_ids[1]


def test_price_exit_samples_do_not_overlap_primary_return_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.strategies.genge_opportunity_discovery.exit_profile as exit_profile

    monkeypatch.setattr(
        exit_profile, "_strict_point_in_time_plan_mode", lambda **_kwargs: "pullback",
    )
    monkeypatch.setattr(
        exit_profile, "_observable_setup_gates_pass", lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        exit_profile, "_session_window_contiguous", lambda *_args, **_kwargs: True,
    )
    history = _history(adjusted=True)
    samples = _price_setup_samples(
        code="000001", stock_name="测试股份", history=history,
        as_of=date(2026, 7, 22), entry_mode="pullback",
    )
    positions = {trade_date: index for index, trade_date in enumerate(history["date"])}
    assert len(samples) >= 2
    assert all(
        positions[current["as_of_date"]] - positions[previous["as_of_date"]] >= PROFILE_SAMPLE_SPACING_SESSIONS
        for previous, current in zip(samples, samples[1:])
    )


def test_price_exit_samples_pass_full_history_point_in_time_mas_to_day45(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.strategies.genge_opportunity_discovery.exit_profile as exit_profile

    captured_windows: list[pd.DataFrame] = []

    def capture_policy_window(**kwargs: object) -> dict[str, object]:
        captured_windows.append(kwargs["future_rows"].copy())
        prefix = exit_profile.BALANCED_EXIT_POLICY_NAME
        return {
            f"{prefix}_exit_adjusted_net_return_60d": 2.0,
            f"{prefix}_exit_adjusted_max_drawdown_60d": -4.0,
            f"{prefix}_exit_date_60d": kwargs["future_rows"].iloc[-1]["date"],
        }

    monkeypatch.setattr(
        exit_profile, "simulate_daily_signal_balanced_v7_exit", capture_policy_window,
    )
    monkeypatch.setattr(
        exit_profile, "_strict_point_in_time_plan_mode", lambda **_kwargs: "pullback",
    )
    monkeypatch.setattr(
        exit_profile, "_observable_setup_gates_pass", lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        exit_profile, "_session_window_contiguous", lambda *_args, **_kwargs: True,
    )
    history = _history(adjusted=True)

    samples = _price_setup_samples(
        code="000001", stock_name="测试股份", history=history,
        as_of=date(2026, 7, 22), entry_mode="pullback",
    )

    assert samples
    assert captured_windows
    first_window = captured_windows[0]
    assert len(first_window) > 61
    assert {"ma20_post", "ma60_post"}.issubset(first_window.columns)
    entry_date = first_window.iloc[0]["date"]
    entry_index = history.index[history["date"] == entry_date][0]
    day45_index = entry_index + 44
    full_close = pd.to_numeric(history["close"], errors="coerce")
    expected_ma20 = full_close.rolling(20).mean().iloc[day45_index]
    expected_ma60 = full_close.rolling(60).mean().iloc[day45_index]

    assert first_window.iloc[44]["ma20_post"] == pytest.approx(expected_ma20)
    assert first_window.iloc[44]["ma60_post"] == pytest.approx(expected_ma60)
    assert first_window.iloc[44]["ma60_post"] != pytest.approx(
        pd.to_numeric(first_window.iloc[:45]["close"], errors="coerce").mean(),
    )


def test_trigger_aligned_entries_replay_pullback_and_breakout_separately() -> None:
    dates = pd.bdate_range("2026-01-01", periods=32)
    frame = pd.DataFrame({
        "date": dates.date,
        "open": [100.0] * 32,
        "high": [101.0] * 32,
        "low": [99.0] * 32,
        "close": [100.0] * 32,
        "raw_open": [100.0] * 32, "raw_high": [101.0] * 32,
        "raw_low": [99.0] * 32,
        "raw_close": [100.0] * 32,
        "adjustment_ratio": [1.0] * 32,
        "volume": [1_000.0] * 32,
    })
    frame.loc[21, ["open", "high", "low", "close", "volume"]] = [100.5, 102.0, 99.2, 101.5, 1_500.0]
    frame.loc[22, ["open", "high", "low", "close", "volume"]] = [101.4, 102.0, 100.8, 101.6, 1_100.0]
    frame.loc[21, ["raw_open", "raw_high", "raw_low", "raw_close"]] = [100.5, 102.0, 99.2, 101.5]
    frame.loc[22, ["raw_open", "raw_high", "raw_low", "raw_close"]] = [101.4, 102.0, 100.8, 101.6]

    pullback = _triggered_entry(
        frame=frame, setup_index=20, entry_mode="pullback",
        breakout_volume_ratio=1.2, max_chase_atr_multiple=.35,
        volatility_multiplier=1.0,
    )
    breakout = _triggered_entry(
        frame=frame, setup_index=20, entry_mode="breakout",
        breakout_volume_ratio=1.2, max_chase_atr_multiple=.35,
        volatility_multiplier=1.0,
    )

    assert pullback is not None and pullback[0] == 21
    assert breakout is not None and breakout[0] == 22
    assert pullback[1] < breakout[1]


def test_entry_plan_raw_tick_mapping_is_invariant_to_qfq_scale() -> None:
    dates = pd.bdate_range("2026-01-01", periods=32)
    raw = pd.DataFrame({
        "date": dates.date, "open": [100.0] * 32, "high": [101.0] * 32,
        "low": [99.0] * 32, "close": [100.0] * 32,
        "volume": [1_000.0] * 32, "adjustment_ratio": [1.0] * 32,
        "raw_open": [100.0] * 32, "raw_high": [101.0] * 32,
        "raw_low": [99.0] * 32, "raw_close": [100.0] * 32,
    })
    raw.loc[21, ["open", "high", "low", "close", "volume", "raw_close"]] = [
        100.5, 102.0, 99.2, 101.5, 1_500.0, 101.5,
    ]
    raw.loc[22, ["open", "high", "low", "close", "raw_close"]] = [
        101.4, 102.0, 100.8, 101.6, 101.6,
    ]
    raw.loc[21, ["raw_open", "raw_high", "raw_low", "raw_close"]] = [100.5, 102.0, 99.2, 101.5]
    raw.loc[22, ["raw_open", "raw_high", "raw_low", "raw_close"]] = [101.4, 102.0, 100.8, 101.6]
    qfq = raw.copy()
    for column in ("open", "high", "low", "close"):
        qfq[column] = qfq[column] / 10.0
    qfq["adjustment_ratio"] = 10.0

    unscaled = _triggered_entry(
        frame=raw, setup_index=20, entry_mode="breakout",
        breakout_volume_ratio=1.2, max_chase_atr_multiple=.35,
        volatility_multiplier=1.0,
    )
    scaled = _triggered_entry(
        frame=qfq, setup_index=20, entry_mode="breakout",
        breakout_volume_ratio=1.2, max_chase_atr_multiple=.35,
        volatility_multiplier=1.0,
    )

    assert unscaled is not None and scaled is not None
    assert scaled[0] == unscaled[0]
    for scaled_price, raw_price in zip(scaled[1:], unscaled[1:]):
        assert scaled_price * 10.0 == pytest.approx(raw_price, abs=.011)


def test_price_mapping_change_cancels_pending_window_and_invalidates_holding_window() -> None:
    frame = pd.DataFrame({"adjustment_ratio": [1.0] * 5 + [1.25] * 5})
    small_dividend = pd.DataFrame({
        "adjustment_ratio": [1.0] * 5 + [.99821] * 5,
    })

    assert _price_mapping_regime_stable(frame, start_index=0, end_index=4)
    assert not _price_mapping_regime_stable(frame, start_index=0, end_index=5)
    assert not _price_mapping_regime_stable(
        small_dividend, start_index=0, end_index=5,
    )


def test_profile_session_continuity_detects_suspension_gap() -> None:
    assert _exchange_session_continuity([
        date(2026, 7, 17), date(2026, 7, 20), date(2026, 7, 21),
    ]) == [True, True, True]
    assert _exchange_session_continuity([
        date(2026, 7, 17), date(2026, 7, 21),
    ]) == [True, False]
    assert _exchange_session_continuity([
        date(2026, 2, 13), date(2026, 2, 24),
    ]) == [True, True]
    assert _exchange_session_continuity([
        date(2000, 1, 4), date(2000, 1, 5), date(2026, 2, 13),
    ]) == [True, True, False]


def test_pullback_fill_is_not_dropped_when_same_day_low_hits_stop() -> None:
    dates = pd.bdate_range("2026-01-01", periods=32)
    frame = pd.DataFrame({
        "date": dates.date, "open": [100.0] * 32, "high": [101.0] * 32,
        "low": [99.0] * 32, "close": [100.0] * 32, "volume": [1_000.0] * 32,
        "raw_open": [100.0] * 32, "raw_high": [101.0] * 32,
        "raw_low": [99.0] * 32, "raw_close": [100.0] * 32,
        "adjustment_ratio": [1.0] * 32,
    })
    frame.loc[21, ["open", "high", "low", "close"]] = [101.0, 101.5, 98.0, 98.5]
    frame.loc[21, ["raw_open", "raw_high", "raw_low", "raw_close"]] = [101.0, 101.5, 98.0, 98.5]

    result = _triggered_entry(
        frame=frame, setup_index=20, entry_mode="pullback",
        breakout_volume_ratio=1.2, max_chase_atr_multiple=.35,
        volatility_multiplier=1.0,
    )

    assert result is not None
    assert result[0] == 21
    assert frame.iloc[21]["low"] <= result[2]


def test_historical_pullback_and_breakout_do_not_claim_one_price_entry() -> None:
    dates = pd.bdate_range("2026-01-01", periods=32)
    base = pd.DataFrame({
        "date": dates.date, "open": [100.0] * 32, "high": [101.0] * 32,
        "low": [99.0] * 32, "close": [100.0] * 32,
        "volume": [1_000.0] * 32, "adjustment_ratio": [1.0] * 32,
        "raw_open": [100.0] * 32, "raw_high": [101.0] * 32,
        "raw_low": [99.0] * 32, "raw_close": [100.0] * 32,
    })
    pullback_frame = base.copy()
    pullback_frame.loc[21, ["open", "high", "low", "close"]] = 100.0
    pullback_frame.loc[21, ["raw_open", "raw_high", "raw_low", "raw_close"]] = 100.0
    breakout_frame = base.copy()
    breakout_frame.loc[21, ["open", "high", "low", "close", "volume"]] = [
        100.5, 102.0, 99.2, 101.5, 1_500.0,
    ]
    breakout_frame.loc[21, ["raw_open", "raw_high", "raw_low", "raw_close"]] = [
        100.5, 102.0, 99.2, 101.5,
    ]
    breakout_frame.loc[22, ["open", "high", "low", "close"]] = 101.4
    breakout_frame.loc[22, ["raw_open", "raw_high", "raw_low", "raw_close"]] = 101.4

    pullback = _triggered_entry(
        frame=pullback_frame, setup_index=20, entry_mode="pullback",
        breakout_volume_ratio=1.2, max_chase_atr_multiple=.35,
        volatility_multiplier=1.0,
    )
    breakout = _triggered_entry(
        frame=breakout_frame, setup_index=20, entry_mode="breakout",
        breakout_volume_ratio=1.2, max_chase_atr_multiple=.35,
        volatility_multiplier=1.0,
    )

    assert pullback is None
    assert breakout is None


def test_breakout_uses_next_open_and_rejects_gap_above_max_chase() -> None:
    dates = pd.bdate_range("2026-01-01", periods=32)
    frame = pd.DataFrame({
        "date": dates.date, "open": [100.0] * 32, "high": [101.0] * 32,
        "low": [99.0] * 32, "close": [100.0] * 32, "volume": [1_000.0] * 32,
        "raw_open": [100.0] * 32, "raw_high": [101.0] * 32,
        "raw_low": [99.0] * 32, "raw_close": [100.0] * 32,
        "adjustment_ratio": [1.0] * 32,
    })
    frame.loc[21, ["open", "high", "low", "close", "volume"]] = [100.5, 102.0, 99.5, 101.5, 1_500.0]
    frame.loc[22, ["open", "high", "low", "close"]] = [110.0, 111.0, 109.0, 110.0]
    frame.loc[21, ["raw_open", "raw_high", "raw_low", "raw_close"]] = [100.5, 102.0, 99.5, 101.5]
    frame.loc[22, ["raw_open", "raw_high", "raw_low", "raw_close"]] = [110.0, 111.0, 109.0, 110.0]

    result = _triggered_entry(
        frame=frame, setup_index=20, entry_mode="breakout",
        breakout_volume_ratio=1.2, max_chase_atr_multiple=.35,
        volatility_multiplier=1.0,
    )

    assert result is None


@pytest.mark.parametrize(
    ("breach_index", "breach_values"),
    [
        (21, {"low": 90.0}),
        (21, {"low": np.nan, "close": 90.0}),
        (23, {"low": 90.0}),
    ],
    ids=("stop_before_confirmation", "close_invalidation", "stop_on_confirmation_day"),
)
def test_breakout_confirmation_window_cancels_after_frozen_plan_breach(
    breach_index: int, breach_values: dict[str, float],
) -> None:
    dates = pd.bdate_range("2026-01-01", periods=36)
    frame = pd.DataFrame({
        "date": dates.date, "open": [100.0] * 36, "high": [101.0] * 36,
        "low": [99.0] * 36, "close": [100.0] * 36, "volume": [1_000.0] * 36,
        "raw_open": [100.0] * 36, "raw_high": [101.0] * 36,
        "raw_low": [99.0] * 36, "raw_close": [100.0] * 36,
        "adjustment_ratio": [1.0] * 36,
    })
    # A valid close/volume confirmation would occur later, followed by an
    # executable next open, unless the frozen plan was already invalidated.
    frame.loc[23, ["open", "high", "low", "close", "volume"]] = [
        100.5, 102.0, 99.5, 101.5, 1_500.0,
    ]
    frame.loc[24, ["open", "high", "low", "close"]] = [101.4, 102.0, 100.8, 101.6]
    frame.loc[23, ["raw_open", "raw_high", "raw_low", "raw_close"]] = [100.5, 102.0, 99.5, 101.5]
    frame.loc[24, ["raw_open", "raw_high", "raw_low", "raw_close"]] = [101.4, 102.0, 100.8, 101.6]
    for field, value in breach_values.items():
        frame.loc[breach_index, field] = value
        frame.loc[breach_index, f"raw_{field}"] = value

    result = _triggered_entry(
        frame=frame, setup_index=20, entry_mode="breakout",
        breakout_volume_ratio=1.2, max_chase_atr_multiple=.35,
        volatility_multiplier=1.0,
    )

    assert result is None


def _cohort_samples(*, as_of: date, recent_return: float = 2.0) -> list[dict]:
    dates = [
        (pd.Timestamp(as_of) - pd.offsets.BDay(70 + 65 * index)).date()
        for index in reversed(range(12))
    ]
    cutoff = as_of - pd.Timedelta(days=730)
    return [
        {
            "code": f"6{period_index:02d}{member_index:03d}",
            "as_of_date": trade_date,
            "outcome_end_date": (
                pd.Timestamp(trade_date) + pd.offsets.BDay(60)
            ).date(),
            "entry_mode": "pullback",
            "return": recent_return if trade_date >= cutoff else 2.0,
            "drawdown": -5.0,
        }
        for period_index, trade_date in enumerate(dates)
        for member_index in range(3)
    ]


def test_cohort_validation_counts_time_eras_not_correlated_stocks() -> None:
    as_of = date(2026, 7, 29)
    samples = _cohort_samples(as_of=as_of)
    periods = _cohort_period_samples(samples, as_of=as_of)
    result = _cohort_validation(
        samples, as_of=as_of, cohort_key="MAIN|pullback",
        data_end_by_code={item["code"]: as_of for item in samples},
    )

    assert len(periods) == 12
    assert result["member_sample_count"] == 36
    assert result["unique_code_count"] == 36
    assert result["status"] == "PASSED"

    one_era = [dict(item, as_of_date=as_of, outcome_end_date=as_of) for item in samples]
    collapsed = _cohort_validation(
        one_era, as_of=as_of, cohort_key="MAIN|pullback",
        data_end_by_code={item["code"]: as_of for item in one_era},
    )
    assert collapsed["period_count"] == 1
    assert collapsed["status"] == "NOT_AVAILABLE"


def test_cohort_recent_deterioration_fails_closed() -> None:
    as_of = date(2026, 7, 29)
    samples = _cohort_samples(as_of=as_of, recent_return=-3.0)
    result = _cohort_validation(
        samples, as_of=as_of, cohort_key="MAIN|pullback",
        data_end_by_code={item["code"]: as_of for item in samples},
    )

    assert result["recent_stability_passed"] is False
    assert result["status"] != "PASSED"


def _incomplete_outcome(reason: str) -> dict:
    return {
        "code": "699999", "as_of_date": date(2026, 7, 29),
        "outcome_end_date": None, "entry_mode": "pullback",
        "return": None, "drawdown": None, "outcome_complete": False,
        "exit_reason": reason,
    }


def test_direct_replay_quality_excludes_one_corporate_action_without_bias() -> None:
    complete = [
        {"return": 2.0, "drawdown": -4.0, "outcome_complete": True}
        for _ in range(MIN_PROFILE_SAMPLE_COUNT)
    ]
    # The unusable outcome has no return/drawdown payload, so changing the
    # unseen economic outcome could never improve the completed distribution.
    quality = _outcome_replay_quality([
        *complete, _incomplete_outcome("CORPORATE_ACTION_REVIEW"),
    ])

    assert quality["corporate_action_excluded_count"] == 1
    assert quality["outcome_replay_coverage_ratio"] == pytest.approx(12 / 13)
    assert quality["outcome_replay_coverage_ratio"] >= MIN_OUTCOME_REPLAY_COVERAGE_RATIO
    assert quality["replay_quality_passed"] is True
    assert _status_with_replay_quality(
        [2.0] * 12, [-4.0] * 12, quality,
    ) == "PASSED"


def test_refresh_and_scope_accept_direct_profile_with_safe_exclusion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.strategies.genge_opportunity_discovery.exit_profile as exit_profile

    as_of = date(2026, 7, 29)
    complete = [
        {
            "code": "000001", "as_of_date": as_of, "entry_mode": "pullback",
            "return": 2.0, "drawdown": -4.0, "outcome_complete": True,
        }
        for _ in range(MIN_PROFILE_SAMPLE_COUNT)
    ]
    monkeypatch.setattr(
        exit_profile, "_price_setup_samples",
        lambda **_kwargs: [
            *complete, _incomplete_outcome("CORPORATE_ACTION_REVIEW"),
        ],
    )
    output, _ = refresh_exit_profiles_from_price_history(
        output_file=tmp_path / "exit_profile.csv",
        candidates=[{"code": "000001", "stock_name": "候选", "board": "SZSE_MAIN"}],
        histories={"000001": _history(adjusted=True)},
        as_of=as_of,
        entry_plan_specs={"000001": {"entry_mode": "pullback"}},
    )

    row = pd.read_csv(output, dtype={"code": str}).iloc[0]
    profiles, _ = _exit_profiles(output)
    enriched = enrich_exit_profile(profiles["000001"], as_of=as_of)
    assert row["balanced_exit_historical_profile"] == "PASSED"
    assert row["stock_outcome_replay_coverage_ratio"] == pytest.approx(12 / 13, abs=1e-6)
    assert bool(row["stock_replay_quality_passed"]) is True
    assert enriched["exit_profile_validation_scope_valid"] is True


def test_direct_replay_quality_rejects_over_twenty_percent_exclusions() -> None:
    complete = [
        {"return": 2.0, "drawdown": -4.0, "outcome_complete": True}
        for _ in range(MIN_PROFILE_SAMPLE_COUNT)
    ]
    excluded = [
        _incomplete_outcome("CORPORATE_ACTION_REVIEW") for _ in range(4)
    ]
    quality = _outcome_replay_quality([*complete, *excluded])

    assert quality["outcome_replay_coverage_ratio"] == pytest.approx(.75)
    assert quality["replay_quality_passed"] is False
    assert _status_with_replay_quality(
        [2.0] * 12, [-4.0] * 12, quality,
    ) == "DEGRADED"


def test_direct_replay_quality_rejects_run_gap_ratio_over_five_percent() -> None:
    complete = [
        {"return": 2.0, "drawdown": -4.0, "outcome_complete": True}
        for _ in range(MIN_PROFILE_SAMPLE_COUNT)
    ]
    quality = _outcome_replay_quality([
        *complete, _incomplete_outcome("RUN_GAP_POSITION_REVIEW"),
    ])

    assert quality["outcome_replay_coverage_ratio"] >= MIN_OUTCOME_REPLAY_COVERAGE_RATIO
    assert quality["run_gap_outcome_ratio"] > MAX_RUN_GAP_OUTCOME_RATIO
    assert quality["replay_quality_passed"] is False
    assert _status_with_replay_quality(
        [2.0] * 12, [-4.0] * 12, quality,
    ) == "DEGRADED"


@pytest.mark.parametrize(
    "reason",
    [
        "UNEXECUTABLE_LOCKED_LIMIT_REVIEW",
        "OUTCOME_EXECUTION_DATE_UNMAPPED",
        "UNEXPECTED_INCOMPLETE_REASON",
    ],
)
def test_direct_replay_quality_hard_vetoes_locked_unmapped_and_unknown(
    reason: str,
) -> None:
    complete = [
        {"return": 2.0, "drawdown": -4.0, "outcome_complete": True}
        for _ in range(MIN_PROFILE_SAMPLE_COUNT)
    ]
    quality = _outcome_replay_quality([
        *complete, _incomplete_outcome(reason),
    ])

    assert quality["hard_veto_outcome_count"] == 1
    assert quality["replay_quality_passed"] is False
    assert _status_with_replay_quality(
        [2.0] * 12, [-4.0] * 12, quality,
    ) == "FAILED"


def test_cohort_known_exclusion_preserves_fact_but_can_pass_replay_quality() -> None:
    as_of = date(2026, 7, 29)
    samples = [
        *_cohort_samples(as_of=as_of),
        _incomplete_outcome("CORPORATE_ACTION_REVIEW"),
    ]
    result = _cohort_validation(
        samples, as_of=as_of, cohort_key="MAIN|pullback",
        data_end_by_code={item["code"]: as_of for item in samples},
    )

    assert result["status"] == "PASSED"
    assert result["outcome_end_complete"] is False
    assert result["invalid_outcome_end_count"] == 1
    assert result["replay_quality_passed"] is True
    assert result["corporate_action_excluded_count"] == 1


@pytest.mark.parametrize(
    ("reason", "excluded_count"),
    [
        ("CORPORATE_ACTION_REVIEW", 10),
        ("RUN_GAP_POSITION_REVIEW", 2),
    ],
)
def test_cohort_replay_quality_blocks_excess_exclusions(
    reason: str, excluded_count: int,
) -> None:
    as_of = date(2026, 7, 29)
    samples = [
        *_cohort_samples(as_of=as_of),
        *[_incomplete_outcome(reason) for _ in range(excluded_count)],
    ]
    result = _cohort_validation(
        samples, as_of=as_of, cohort_key="MAIN|pullback",
        data_end_by_code={item["code"]: as_of for item in samples},
    )

    assert result["status"] != "PASSED"
    assert result["replay_quality_passed"] is False
    if reason == "CORPORATE_ACTION_REVIEW":
        assert result["outcome_replay_coverage_ratio"] < MIN_OUTCOME_REPLAY_COVERAGE_RATIO
    else:
        assert result["run_gap_outcome_ratio"] > MAX_RUN_GAP_OUTCOME_RATIO


def test_cohort_unresolved_locked_exit_is_an_explicit_validation_veto() -> None:
    as_of = date(2026, 7, 29)
    samples = _cohort_samples(as_of=as_of)
    samples.append({
        "code": "699999", "as_of_date": as_of,
        "entry_mode": "pullback", "outcome_end_date": None,
        "return": None, "drawdown": None, "outcome_complete": False,
        "exit_reason": "UNEXECUTABLE_LOCKED_LIMIT_REVIEW",
    })
    result = _cohort_validation(
        samples, as_of=as_of, cohort_key="MAIN|pullback",
        data_end_by_code={item["code"]: as_of for item in samples},
    )

    assert result["status"] == "FAILED"
    assert result["outcome_end_complete"] is False
    assert result["invalid_outcome_end_count"] == 1


def test_refresh_uses_independent_cohort_with_half_position_and_stock_veto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.strategies.genge_opportunity_discovery.exit_profile as exit_profile

    as_of = date(2026, 7, 29)
    reference_samples = _cohort_samples(as_of=as_of)
    by_code: dict[str, list[dict]] = {}
    for item in reference_samples:
        by_code.setdefault(item["code"], []).append(item)

    def samples_for(**kwargs):
        code = kwargs["code"]
        mode = kwargs["entry_mode"]
        if code == "000001":
            return [
                {"code": code, "as_of_date": as_of, "entry_mode": mode, "return": 1.0, "drawdown": -4.0},
                {"code": code, "as_of_date": as_of, "entry_mode": mode, "return": 2.0, "drawdown": -5.0},
            ]
        return [dict(item, entry_mode=mode) for item in by_code[code]]

    monkeypatch.setattr(exit_profile, "_price_setup_samples", samples_for)
    references = [
        {"code": code, "stock_name": code, "board": "SSE_MAIN"} for code in sorted(by_code)
    ]
    histories = {"000001": _history(adjusted=True), **{
        code: _history(adjusted=True) for code in by_code
    }}
    output, _ = refresh_exit_profiles_from_price_history(
        output_file=tmp_path / "exit_profile.csv",
        candidates=[{"code": "000001", "stock_name": "候选", "board": "SSE_MAIN"}],
        validation_candidates=references,
        histories=histories,
        as_of=as_of,
        entry_plan_specs={"000001": {"entry_mode": "pullback"}},
    )
    row = pd.read_csv(output, dtype={"code": str}).iloc[0]

    assert row["balanced_exit_historical_profile"] == "PASSED"
    assert row["profile_validation_scope"] == "ENTRY_MODE_COHORT_INDEPENDENT_REFERENCE"
    assert row["profile_position_multiplier"] == .5
    assert row["signal_count"] == 12
    assert row["stock_signal_count"] == 2

    def failed_candidate_samples(**kwargs):
        if kwargs["code"] == "000001":
            return [
                {"code": "000001", "as_of_date": as_of, "entry_mode": kwargs["entry_mode"], "return": value, "drawdown": -10.0}
                for value in (-2.0, -2.0, -2.0, -2.0, 3.0, 3.0)
            ]
        return [dict(item, entry_mode=kwargs["entry_mode"]) for item in by_code[kwargs["code"]]]

    monkeypatch.setattr(exit_profile, "_price_setup_samples", failed_candidate_samples)
    output, _ = refresh_exit_profiles_from_price_history(
        output_file=tmp_path / "exit_profile.csv",
        candidates=[{"code": "000001", "stock_name": "候选", "board": "SSE_MAIN"}],
        validation_candidates=references,
        histories=histories,
        as_of=as_of,
        entry_plan_specs={"000001": {"entry_mode": "pullback"}},
    )
    blocked = pd.read_csv(output, dtype={"code": str}).iloc[0]
    assert blocked["balanced_exit_historical_profile"] == "DEGRADED"
    assert bool(blocked["stock_negative_veto_clear"]) is False


def test_refresh_unresolved_locked_exit_blocks_direct_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.strategies.genge_opportunity_discovery.exit_profile as exit_profile

    as_of = date(2026, 7, 29)
    complete = [
        {
            "code": "000001", "as_of_date": as_of,
            "entry_mode": "pullback", "return": 3.0, "drawdown": -4.0,
            "outcome_complete": True,
        }
        for _ in range(MIN_PROFILE_SAMPLE_COUNT)
    ]
    incomplete = {
        "code": "000001", "as_of_date": as_of,
        "entry_mode": "pullback", "return": None, "drawdown": None,
        "outcome_complete": False,
        "exit_reason": "UNEXECUTABLE_LOCKED_LIMIT_REVIEW",
    }
    monkeypatch.setattr(
        exit_profile, "_price_setup_samples",
        lambda **_kwargs: [*complete, incomplete],
    )

    output, _ = refresh_exit_profiles_from_price_history(
        output_file=tmp_path / "exit_profile.csv",
        candidates=[{"code": "000001", "stock_name": "候选", "board": "SZSE_MAIN"}],
        histories={"000001": _history(adjusted=True)},
        as_of=as_of,
        entry_plan_specs={"000001": {"entry_mode": "pullback"}},
    )
    row = pd.read_csv(output, dtype={"code": str}).iloc[0]

    assert row["balanced_exit_historical_profile"] == "FAILED"
    assert row["stock_profile_status"] == "FAILED"
    assert row["stock_signal_count"] == MIN_PROFILE_SAMPLE_COUNT
    assert row["stock_incomplete_outcome_count"] == 1
    assert row["profile_position_multiplier"] == 0.0


def test_exit_profile_hash_is_point_in_time_and_includes_volume_and_spec() -> None:
    history = _history(adjusted=True)
    as_of = max(history["date"])
    base = _history_digest(history, as_of=as_of, spec={"entry_mode": "pullback"}, code="000001")
    future = pd.concat([
        history,
        pd.DataFrame([{
            **history.iloc[-1].to_dict(),
            "date": as_of + pd.Timedelta(days=7), "close": 999.0, "volume": 999.0,
        }]),
    ], ignore_index=True)
    assert _history_digest(future, as_of=as_of, spec={"entry_mode": "pullback"}, code="000001") == base
    changed_volume = history.copy()
    changed_volume.loc[changed_volume.index[-1], "volume"] *= 2
    assert _history_digest(changed_volume, as_of=as_of, spec={"entry_mode": "pullback"}, code="000001") != base
    assert _history_digest(history, as_of=as_of, spec={"entry_mode": "breakout"}, code="000001") != base


def test_actionable_execution_list_keeps_every_current_strict_trigger() -> None:
    rows = [{
        "code": "000001", "stock_name": "测试股份", "preferred_plan": "pullback",
        "pullback_entry_low": 9.8, "pullback_entry_high": 10.0,
        "pullback_stop_price": 9.4, "pullback_logic_invalidation_price": 9.2,
        "pullback_target_1": 11.2, "pullback_target_2": 12.0,
        "real_reward_risk_ratio": 2.0, "risk_budget_initial_position_pct": 3.0,
        "risk_budget_max_position_pct": 5.0, "cancel_conditions": "重大负面公告",
        "industry_evidence_status": "VERIFIED", "company_evidence_status": "VERIFIED",
        "hard_logic_level": "MEDIUM", "exit_profile_status": "PASSED",
        "exit_profile_entry_mode": "pullback", "evidence_urls": "https://example.com",
        "market_regime_status": "GREEN", "industry_regime_status": "NEUTRAL",
        "industry_regime_sample_count": 20, "event_scan_status": "OK",
        "event_risk_level": "LOW", "price_volume_state": "NEUTRAL",
        "real_world_gate_passed": True,
    }]

    result = build_actionable_execution_list(strict_rows=rows, next_trade_date=date(2026, 7, 23))

    assert result[0]["execution_action"] == "BUY_IF_TRIGGERED"
    assert result[0]["max_buy_price"] == 10.0
    assert result[0]["risk_budget_max_position_pct"] == 5.0


@pytest.mark.parametrize("risk_override", [
    {"market_regime_status": "RED"},
    {"market_regime_status": "UNKNOWN"},
    {"industry_regime_status": "CRISIS"},
    {"industry_regime_status": "UNKNOWN"},
    {"industry_regime_sample_count": 4},
    {"event_scan_status": "PARTIAL"},
    {"event_risk_level": "HIGH"},
    {"price_volume_state": "DISTRIBUTION"},
    {"real_world_gate_passed": False},
])
def test_actionable_execution_list_defensively_rejects_real_world_risk(
    risk_override: dict,
) -> None:
    row = {
        "code": "000001", "stock_name": "测试股份", "preferred_plan": "pullback",
        "pullback_entry_low": 9.8, "pullback_entry_high": 10.0,
        "pullback_stop_price": 9.4, "pullback_logic_invalidation_price": 9.2,
        "pullback_target_1": 11.2, "pullback_target_2": 12.0,
        "market_regime_status": "GREEN", "industry_regime_status": "NEUTRAL",
        "industry_regime_sample_count": 20, "event_scan_status": "OK",
        "event_risk_level": "LOW", "price_volume_state": "NEUTRAL",
        "real_world_gate_passed": True,
    }
    row.update(risk_override)
    assert build_actionable_execution_list(
        strict_rows=[row], next_trade_date=date(2026, 7, 23),
    ) == []


def _row(board: str = "SZSE_MAIN") -> dict:
    return {
        "code": "000001", "stock_name": "测试股份", "exchange": "SZSE", "board": board,
        "security_type": "ORDINARY_A_SHARE", "listing_status": "LISTED", "listing_date": "2020-01-01",
        "is_st": False, "is_suspended": "", "latest_trade_date": "", "liquidity": "",
        "industry": "银行", "industry_source": "fixture", "universe_source": "fixture", "exclusion_reason": "",
    }


def test_exchange_board_mapping_uses_listing_metadata() -> None:
    assert _board_from_exchange_row(exchange="SSE", board_text="STAR", code="123456") == "STAR"
    assert _board_from_exchange_row(exchange="SSE", board_text="SSE_MAIN", code="123456") == "SSE_MAIN"
    assert _board_from_exchange_row(exchange="SZSE", board_text="创业板", code="123456") == "CHINEXT"
    assert _board_from_exchange_row(exchange="SZSE", board_text="主板", code="123456") == "SZSE_MAIN"
    assert _board_from_exchange_row(exchange="SZSE", board_text="未知", code="000001") == "UNRESOLVED"


def test_listing_row_excludes_st_and_unresolved_security_type() -> None:
    st = _listing_row(code="000001", name="*ST测试", exchange="SZSE", board="主板", listing_date="2020-01-01", universe_source="fixture")
    unresolved = _listing_row(code="000002", name="测试", exchange="SZSE", board="未知", listing_date="2020-01-01", universe_source="fixture")
    assert st["exclusion_reason"] == "st_or_delisting_risk"
    assert unresolved["exclusion_reason"] == "security_type_unconfirmed"


def test_listing_after_as_of_is_skipped_without_fatal_price_failure() -> None:
    as_of = date(2026, 7, 20)
    future = _row(board="STAR")
    future.update({
        "code": "688806",
        "stock_name": "N泰诺",
        "exchange": "SSE",
        "listing_date": "2026-07-21",
    })
    rows = mark_listings_after_as_of([future], as_of=as_of)

    assert rows[0]["exclusion_reason"] == "listing_after_as_of"
    universe, audit_rows, counts = apply_universe_filters(
        rows, {}, {}, {}, {"688806:raw": "history unavailable"},
        as_of=as_of, board_rules=load_board_rules("config/board_risk_rules.yaml"),
    )

    assert universe[0]["exclusion_reason"] == "listing_after_as_of"
    assert audit_rows[0]["reason"] == "listing_after_as_of"
    assert counts["listing_after_as_of"] == 1
    assert counts["fatal_data_failure_count"] == 0


def test_board_rules_are_differentiated() -> None:
    rules = load_board_rules(Path("config/board_risk_rules.yaml"))
    assert rules["STAR"].daily_price_limit == .20
    assert rules["CHINEXT"].minimum_turnover > rules["SZSE_MAIN"].minimum_turnover
    assert rules["STAR"].max_chase_atr_multiple < rules["SSE_MAIN"].max_chase_atr_multiple


def test_adjusted_raw_mapping_detects_corporate_action_and_keeps_raw_latest_price() -> None:
    qfq = _history(adjusted=True)
    raw = _history(corporate_action=True)
    audit = audit_price_mapping(qfq, raw, as_of=qfq.iloc[-1]["date"], qfq_source="qfq", raw_source="raw")
    assert audit["price_mapping_status"] == "OK"
    assert audit["corporate_action_detected"] is True
    assert audit["raw_latest_close"] == pytest.approx(float(raw.iloc[-1]["close"]), abs=1e-4)
    assert audit["adjusted_latest_close"] == pytest.approx(float(qfq.iloc[-1]["close"]), abs=1e-4)


def test_same_stale_trade_date_is_suspension_not_mapping_failure() -> None:
    qfq = _history(adjusted=True).iloc[:-3]
    raw = _history().iloc[:-3]
    as_of = _history().iloc[-1]["date"]
    audit = audit_price_mapping(qfq, raw, as_of=as_of, qfq_source="qfq", raw_source="raw")
    assert audit["price_mapping_status"] == "NO_ASOF_TRADE"
    rules = load_board_rules("config/board_risk_rules.yaml")
    _, audit_rows, counts = apply_universe_filters(
        [_row()], {"000001": qfq}, {"000001": raw}, {"000001": audit}, {},
        as_of=as_of, board_rules=rules,
    )
    assert audit_rows[0]["reason"] == "suspended_or_latest_trade_date_mismatch"
    assert counts["fatal_data_failure_count"] == 0


def test_single_price_fetch_failure_is_recoverable_and_audited() -> None:
    as_of = date(2026, 7, 20)
    rules = load_board_rules("config/board_risk_rules.yaml")

    universe, audit_rows, counts = apply_universe_filters(
        [_row()], {}, {}, {}, {"000001:raw": "provider unavailable"},
        as_of=as_of, board_rules=rules,
    )

    assert universe[0]["exclusion_reason"] == "price_fetch_failed"
    assert audit_rows[0]["reason"] == "price_fetch_failed"
    assert counts["recoverable_price_failure_count"] == 1
    assert counts["fatal_data_failure_count"] == 0
    assert counts["price_data_coverage_ratio"] == 0.0


def test_systemic_price_failures_are_fatal_only_after_threshold() -> None:
    as_of = date(2026, 7, 20)
    rules = load_board_rules("config/board_risk_rules.yaml")
    rows = []
    errors = {}
    for index in range(51):
        code = f"{index + 1:06d}"
        row = _row()
        row["code"] = code
        rows.append(row)
        errors[f"{code}:raw"] = "provider unavailable"

    _, _, counts = apply_universe_filters(
        rows, {}, {}, {}, errors, as_of=as_of, board_rules=rules,
    )

    assert counts["recoverable_price_failure_count"] == 51
    assert counts["fatal_data_failure_count"] == 51
    assert counts["price_data_coverage_ratio"] == 0.0


def test_quant_indicators_use_qfq_not_raw_corporate_action_history() -> None:
    qfq = _history(adjusted=True)
    raw = _history(corporate_action=True)
    as_of = qfq.iloc[-1]["date"]
    rules = load_board_rules("config/board_risk_rules.yaml")
    audit = audit_price_mapping(qfq, raw, as_of=as_of, qfq_source="qfq", raw_source="raw")
    universe, _, counts = apply_universe_filters([_row()], {"000001": qfq}, {"000001": raw}, {"000001": audit}, {}, as_of=as_of, board_rules=rules)
    result = quant_screen(universe, {"000001": qfq}, {"000001": raw}, {"000001": audit}, qfq, as_of=as_of, board_rules=rules)
    expected_ma250 = qfq.close.tail(250).mean()
    assert counts["effective_scan_count"] == 1
    assert result[0]["ma250"] == pytest.approx(expected_ma250, abs=.01)
    assert result[0]["raw_latest_close"] == pytest.approx(float(raw.iloc[-1].close), abs=.01)
    expected_percentile = float((qfq.close <= qfq.iloc[-1].close).mean())
    assert result[0]["price_percentile_5y"] == pytest.approx(expected_percentile, abs=.0001)
    assert result[0]["return_1d_pct"] == pytest.approx((qfq.iloc[-1].close / qfq.iloc[-2].close - 1) * 100, abs=.0001)
    assert result[0]["price_volume_state"] in {"NEUTRAL", "WEAK_DEMAND", "ACCUMULATION", "DISTRIBUTION", "CAPITULATION_RISK"}


def test_price_plan_uses_raw_prices_and_enforces_geometry() -> None:
    raw = _history(corporate_action=True)
    rules = load_board_rules("config/board_risk_rules.yaml")
    plan = build_price_plan({}, raw, rules["SZSE_MAIN"], ["https://example.com/report.pdf"])
    assert plan["raw_latest_close"] == pytest.approx(float(raw.iloc[-1].close), abs=.01)
    if plan["pullback_entry_low"] != "":
        assert plan["pullback_stop_price"] < plan["pullback_entry_low"] <= plan["pullback_entry_high"] < plan["pullback_target_1"]
    if plan["breakout_target_1"] != "":
        assert plan["breakout_stop_price"] < plan["breakout_trigger_price"] <= plan["breakout_max_chase_price"] < plan["breakout_target_1"]


def test_price_plan_geometry_uses_qfq_and_ignores_raw_corporate_action_break() -> None:
    adjusted = _history(adjusted=True)
    clean_raw = adjusted.drop(columns=["raw_close", "adjustment_ratio"]).copy()
    action_raw = clean_raw.copy()
    # Put a large mechanical raw-price break inside every relevant technical
    # lookback. The qfq economic history is unchanged.
    for column in ("open", "high", "low", "close"):
        action_raw.loc[:1219, column] *= 1.5
    rules = load_board_rules("config/board_risk_rules.yaml")

    clean = build_price_plan(
        {}, clean_raw, rules["SZSE_MAIN"], [], adjusted_history=adjusted,
    )
    rebased = build_price_plan(
        {}, action_raw, rules["SZSE_MAIN"], [], adjusted_history=adjusted,
    )

    comparable_fields = {
        key for key in clean
        if key not in {"pullback_resistance_audit", "breakout_resistance_audit"}
    }
    assert {key: clean[key] for key in comparable_fields} == {
        key: rebased[key] for key in comparable_fields
    }


def test_resistance_requires_two_touches_and_minimum_distance() -> None:
    raw = _history()
    atr = 0.3
    all_levels, eligible = resistance_levels(raw, atr14=atr, entry=11.8)
    assert all_levels
    assert eligible
    assert all(item["touches"] >= 2 for item in eligible)
    assert all(item["price"] - 11.8 >= max(atr, 11.8 * .02) for item in eligible)


def _candidate(**overrides) -> dict:
    row = {
        "quant_status": "PRIORITY_RESEARCH",
        "hard_blockers": "", "price_percentile_5y": .25, "trend_confirmation_level": "MEDIUM",
        "adjusted_latest_close": 11.8, "ma60": 11.5, "ma20_slope_pct": .2, "ma60_slope_pct": .1,
        "financial_safety_score": 78, "valuation_score": 70,
        "industry_evidence_status": "PARTIALLY_VERIFIED", "company_evidence_status": "VERIFIED",
        "hard_logic_level": "MEDIUM", "execution_risk_quality": "GOOD", "value_trap_flag": False,
        "price_mapping_status": "OK", "soft_blockers": "", "risk_flags": "",
        "strict_official_evidence_count": 1,
        "strict_official_evidence_domains": "static.cninfo.com.cn",
        "strict_official_evidence_passed": True,
        "market_regime_status": "GREEN", "market_regime_score": 70,
        "market_position_multiplier": 1.0, "external_risk_level": "LOW",
        "industry_regime_status": "NEUTRAL", "industry_regime_score": 55,
        "industry_regime_sample_count": 20,
        "price_volume_state": "NEUTRAL", "price_volume_score": 55,
        "event_risk_level": "LOW", "event_scan_status": "OK",
        "real_world_gate_passed": True, "real_world_risk_flags": "",
    }
    row.update(overrides)
    return row


def _plan(rr: float = 1.8, ready: bool = True) -> dict:
    return {
        "real_reward_risk_ratio": rr,
        "preferred_plan": "pullback",
        "pullback_status": "READY" if ready else "VALID_RR_BELOW_STRICT",
        "breakout_status": "NO_ELIGIBLE_REAL_RESISTANCE",
    }


def _profile() -> dict:
    return {
        "exit_profile_status": "PASSED", "exit_profile_sample_count": 50,
        "exit_profile_confidence": "MEDIUM", "profile_data_end_date": "2025-12-31",
        "recent_2y_sample_count": 20,
        "profile_rule_version": RULE_VERSION, "exit_profile_freshness_days": 30,
        "exit_profile_rule_version_match": True, "exit_profile_freshness_passed": True,
        "exit_profile_data_version": "fixture-v1", "exit_profile_data_traceable": True,
        "exit_profile_entry_mode": "pullback",
        "profile_validation_scope": "STOCK_SPECIFIC", "profile_position_multiplier": 1.0,
        "exit_profile_validation_scope_valid": True,
    }


def test_strict_review_ready_requires_every_hard_gate() -> None:
    rule = load_board_rules("config/board_risk_rules.yaml")["SZSE_MAIN"]
    level, missing = classify_candidate(_candidate(), _plan(), _profile(), ["https://example.com/report.pdf"], board_rule=rule)
    assert level == "STRICT_REVIEW_READY"
    assert not missing
    for override in (
        {"price_percentile_5y": .36}, {"trend_confirmation_level": "WEAK"},
        {"financial_safety_score": 59}, {"hard_logic_level": "WEAK"},
        {"quant_status": "LOW_PRIORITY"},
    ):
        level, _ = classify_candidate(_candidate(**override), _plan(), _profile(), ["https://example.com/report.pdf"], board_rule=rule)
        assert level != "STRICT_REVIEW_READY"


def test_strict_exit_profile_must_match_today_entry_mode_and_valid_scope() -> None:
    rule = load_board_rules("config/board_risk_rules.yaml")["SZSE_MAIN"]
    mismatched = _profile()
    mismatched["exit_profile_entry_mode"] = "breakout"
    checks = strict_candidate_checks(_candidate(), _plan(), mismatched, board_rule=rule)
    assert checks["exit_profile_entry_mode_match"] is False

    invalid_scope = _profile()
    invalid_scope["exit_profile_validation_scope_valid"] = False
    checks = strict_candidate_checks(_candidate(), _plan(), invalid_scope, board_rule=rule)
    assert checks["exit_profile_validation_scope"] is False


def test_cohort_validated_profile_halves_position_budget() -> None:
    plan = {
        **_plan(), "pullback_entry_high": 11.0, "pullback_stop_price": 10.0,
    }
    direct = _candidate(profile_position_multiplier=1.0)
    cohort = _candidate(profile_position_multiplier=.5)

    _apply_position_budget(direct, plan, "STRICT_REVIEW_READY")
    _apply_position_budget(cohort, plan, "STRICT_REVIEW_READY")

    assert cohort["risk_budget_initial_position_pct"] == pytest.approx(
        direct["risk_budget_initial_position_pct"] * .5, abs=.01,
    )
    assert cohort["risk_budget_max_position_pct"] == pytest.approx(
        direct["risk_budget_max_position_pct"] * .5, abs=.01,
    )


@pytest.mark.parametrize(("override", "failed_gate"), [
    ({"market_regime_status": "RED"}, "market_regime_not_red"),
    ({"market_regime_status": "UNKNOWN"}, "market_regime_not_red"),
    ({"industry_regime_status": "CRISIS"}, "industry_regime_not_crisis"),
    ({"industry_regime_status": "UNKNOWN"}, "industry_regime_available"),
    ({"industry_regime_sample_count": 4}, "industry_regime_available"),
    ({"event_risk_level": "HIGH"}, "event_risk_not_high"),
    ({"event_scan_status": "UNKNOWN"}, "event_risk_known"),
    ({"price_volume_state": "DISTRIBUTION"}, "price_volume_not_distribution"),
    ({"price_volume_state": "CAPITULATION_RISK"}, "price_volume_not_distribution"),
])
def test_real_world_risk_cannot_pass_strict_gate(override: dict, failed_gate: str) -> None:
    rule = load_board_rules("config/board_risk_rules.yaml")["SZSE_MAIN"]
    row = _candidate(**override)
    checks = strict_candidate_checks(row, _plan(), _profile(), board_rule=rule)
    level, missing = classify_candidate(
        row, _plan(), _profile(), ["https://example.com/report.pdf"], board_rule=rule,
    )
    assert checks[failed_gate] is False
    assert level != "STRICT_REVIEW_READY"
    assert failed_gate in missing


def test_strict_exit_metadata_thresholds_match_non_overlapping_samples() -> None:
    rule = load_board_rules("config/board_risk_rules.yaml")["SZSE_MAIN"]
    profile = _profile()
    profile["exit_profile_sample_count"] = MIN_PROFILE_SAMPLE_COUNT
    profile["recent_2y_sample_count"] = MIN_RECENT_2Y_SAMPLE_COUNT
    checks = strict_candidate_checks(_candidate(), _plan(), profile, board_rule=rule)
    assert checks["exit_profile_sample_count"] is True
    assert checks["exit_profile_recent_2y_samples"] is True

    profile["exit_profile_sample_count"] = MIN_PROFILE_SAMPLE_COUNT - 1
    profile["recent_2y_sample_count"] = MIN_RECENT_2Y_SAMPLE_COUNT - 1
    checks = strict_candidate_checks(_candidate(), _plan(), profile, board_rule=rule)
    assert checks["exit_profile_sample_count"] is False
    assert checks["exit_profile_recent_2y_samples"] is False


def _evidence(**overrides) -> dict:
    row = {
        "scope": "company", "code": "000001", "industry": "银行",
        "evidence_date": "2026-07-01", "source_type": "EXCHANGE_DISCLOSURE",
        "original_url": "https://static.cninfo.com.cn/finalpage/report.pdf",
        "evidence_status": "VERIFIED", "parse_status": "OK",
        "normalized_summary": "正式公告已解析并核验。", "warning_flags": "",
    }
    row.update(overrides)
    return row


def test_news_url_cannot_satisfy_strict_official_evidence() -> None:
    audit = strict_official_evidence_audit([
        _evidence(source_type="NEWS", original_url="https://news.example.com/story")
    ], _row(), as_of=date(2026, 7, 13))
    assert audit["strict_official_evidence_count"] == 0
    assert audit["strict_official_evidence_passed"] is False


@pytest.mark.parametrize("url", [
    "https://static.cninfo.com.cn/finalpage/report.pdf",
    "https://www.sse.com.cn/disclosure/report.pdf",
    "https://www.szse.cn/disclosure/report.pdf",
    "https://www.stats.gov.cn/report.html",
])
def test_formal_official_domains_satisfy_strict_evidence(url: str) -> None:
    audit = strict_official_evidence_audit(
        [_evidence(original_url=url)], _row(), as_of=date(2026, 7, 13)
    )
    assert audit["strict_official_evidence_count"] == 1
    assert audit["strict_official_evidence_passed"] is True


def test_url_without_parsed_content_cannot_satisfy_strict_evidence() -> None:
    audit = strict_official_evidence_audit([
        _evidence(normalized_summary="", raw_excerpt="", content_hash="", extracted_value="")
    ], _row(), as_of=date(2026, 7, 13))
    assert audit["strict_official_evidence_passed"] is False


def _raw_profile(**overrides) -> dict:
    profile = {
        "exit_profile_status": "PASSED", "exit_profile_sample_count": 50,
        "exit_profile_confidence": "MEDIUM", "profile_data_end_date": "2026-07-01",
        "recent_2y_sample_count": 20,
        "profile_rule_version": RULE_VERSION, "exit_profile_data_version": "fixture-v1",
    }
    profile.update(overrides)
    return profile


@pytest.mark.parametrize("overrides", [
    {"profile_data_end_date": ""},
    {"profile_data_end_date": "2025-01-01"},
    {"profile_rule_version": "old-rule-version"},
])
def test_invalid_exit_profile_metadata_cannot_be_strict(overrides: dict) -> None:
    profile = enrich_exit_profile(_raw_profile(**overrides), as_of=date(2026, 7, 13))
    level, missing = classify_candidate(
        _candidate(), _plan(), profile, ["https://static.cninfo.com.cn/report.pdf"],
        board_rule=load_board_rules("config/board_risk_rules.yaml")["SZSE_MAIN"],
    )
    assert level != "STRICT_REVIEW_READY"
    assert any(name.startswith("exit_profile_") for name in missing)


def test_exit_profile_diagnostic_explains_stock_and_cohort_shortfalls() -> None:
    profile = enrich_exit_profile({
        "code": "603658",
        "exit_profile_status": "DEGRADED",
        "profile_validation_scope": "STOCK_SPECIFIC_INSUFFICIENT",
        "stock_profile_status": "DEGRADED",
        "stock_signal_count": 6,
        "stock_recent_2y_sample_count": 4,
        "stock_avg_net_return_60d": -0.1568,
        "stock_recent_avg_net_return_60d": -4.5227,
        "stock_win_rate_60d": 50.0,
        "stock_recent_stability_passed": False,
        "cohort_key": "MAIN|pullback",
        "cohort_profile_status": "DEGRADED",
        "cohort_period_count": 32,
        "cohort_recent_2y_period_count": 2,
        "cohort_return_lower_bound_60d": -3.0187,
        "cohort_member_win_rate_60d": 34.27,
        "cohort_recent_avg_net_return_60d": 20.02,
        "cohort_independence_passed": True,
        "cohort_recent_stability_passed": False,
    }, as_of=date(2026, 7, 29))

    detail = profile["exit_profile_blocker_detail"]
    assert "samples=6/12" in detail
    assert "recent=4/3" in detail
    assert "periods=32/12" in detail
    assert "lcb=-3.0187%" in detail
    assert "member_win=34.27%" in detail


def test_exit_profile_strategy_health_distinguishes_no_edge_from_run_failure() -> None:
    no_edge = _exit_profile_strategy_health({
        "candidate_distribution": {"DEGRADED": 80},
        "cohort_validations": {
            "MAIN|pullback": {
                "status": "DEGRADED", "independence_passed": True,
                "recent_stability_passed": False, "performance_passed": False,
                "member_performance_passed": False,
            },
        },
    })
    assert no_edge["status"] == "NO_VALIDATED_EXIT_EDGE"
    assert no_edge["cohort_independence_passed_count"] == 1
    assert no_edge["cohort_performance_passed_count"] == 0

    cohort_edge = _exit_profile_strategy_health({
        "candidate_distribution": {},
        "cohort_validations": {"MAIN|pullback": {"status": "PASSED"}},
    })
    assert cohort_edge["status"] == "REFERENCE_COHORT_VALIDATED_EDGE_AVAILABLE"

    candidate_edge = _exit_profile_strategy_health({
        "candidate_distribution": {"PASSED": 1},
        "cohort_validations": {},
    })
    assert candidate_edge["status"] == "CANDIDATE_VALIDATED_EDGE_AVAILABLE"


def test_condition_watch_requires_financial_passed_and_rr_1_3() -> None:
    rule = load_board_rules("config/board_risk_rules.yaml")["SZSE_MAIN"]
    base = _candidate(trend_confirmation_level="WEAK", industry_evidence_status="MISSING", hard_logic_level="WEAK")
    level, _ = classify_candidate(base, _plan(1.3, ready=False), {"exit_profile_status": "NOT_AVAILABLE"}, ["https://example.com/report.pdf"], board_rule=rule)
    assert level == "CONDITION_WATCH"
    low_rr, _ = classify_candidate(base, _plan(1.29, ready=False), {}, ["https://example.com/report.pdf"], board_rule=rule)
    bad_financial, _ = classify_candidate({**base, "financial_safety_score": 59}, _plan(1.3, ready=False), {}, ["https://example.com/report.pdf"], board_rule=rule)
    assert low_rr != "CONDITION_WATCH"
    assert bad_financial != "CONDITION_WATCH"


def test_non_strict_actual_output_rows_have_zero_position(tmp_path: Path) -> None:
    rows = []
    plan = {
        **_plan(1.3, ready=False), "preferred_plan": "pullback",
        "pullback_entry_high": 11.0, "pullback_stop_price": 10.0,
        "breakout_max_chase_price": 11.2,
    }
    for level in ("CONDITION_WATCH", "RESEARCH_WATCH", "NOT_QUALIFIED"):
        row = {"code": level, "user_visible_level": level}
        _apply_position_budget(row, plan, level)
        rows.append(row)
    output = tmp_path / "actual_output.csv"
    pd.DataFrame(rows).to_csv(output, index=False)
    actual = pd.read_csv(output)
    assert set(actual["user_visible_level"]) == {"CONDITION_WATCH", "RESEARCH_WATCH", "NOT_QUALIFIED"}
    assert (actual["risk_budget_initial_position_pct"] == 0).all()
    assert (actual["risk_budget_max_position_pct"] == 0).all()


def test_market_and_industry_regimes_reduce_strict_position_budget() -> None:
    plan = {
        **_plan(), "preferred_plan": "pullback",
        "pullback_entry_high": 11.0, "pullback_stop_price": 10.0,
        "breakout_max_chase_price": 11.2,
    }
    green: dict = {"market_position_multiplier": 1.0, "industry_regime_status": "STRONG"}
    yellow: dict = {"market_position_multiplier": 0.5, "industry_regime_status": "STRONG"}
    yellow_weak: dict = {"market_position_multiplier": 0.5, "industry_regime_status": "WEAK"}
    medium_event_weak_demand: dict = {
        "market_position_multiplier": 1.0,
        "industry_regime_status": "STRONG",
        "event_risk_level": "MEDIUM",
        "price_volume_state": "WEAK_DEMAND",
    }
    for row in (green, yellow, yellow_weak, medium_event_weak_demand):
        _apply_position_budget(row, plan, "STRICT_REVIEW_READY")
    assert yellow["risk_budget_initial_position_pct"] == pytest.approx(green["risk_budget_initial_position_pct"] * 0.5, abs=.01)
    assert yellow_weak["risk_budget_initial_position_pct"] == pytest.approx(yellow["risk_budget_initial_position_pct"] * 0.75, abs=.01)
    assert medium_event_weak_demand["risk_budget_initial_position_pct"] == pytest.approx(
        green["risk_budget_initial_position_pct"] * 0.75 * 0.8, abs=.01,
    )


def test_daily_candidate_top5_is_unique_ranked_and_keeps_buy_gate_semantics() -> None:
    strict = {
        "code": "000001", "stock_name": "严格", "user_visible_level": "STRICT_REVIEW_READY",
        "actionability_rank": 1, "risk_budget_initial_position_pct": 2.0,
        "risk_budget_max_position_pct": 5.0,
    }
    watch = [
        {
            "code": f"00000{index}", "stock_name": f"观察{index}",
            "user_visible_level": "CONDITION_WATCH", "actionability_rank": index,
            "risk_budget_initial_position_pct": 9.0, "risk_budget_max_position_pct": 9.0,
        }
        for index in range(2, 6)
    ]
    signals = [{
        "code": strict["code"], "signal_action": "BUY_IF_TRIGGERED",
        "signal_reason": "all_strict_gates_passed",
    }, *[
        {"code": row["code"], "signal_action": "WATCH_ONLY", "signal_reason": "missing"}
        for row in watch
    ]]
    result = build_daily_candidate_top5(
        deep_rows=[strict, *watch], daily_signals=signals, limit=5,
    )
    assert [row["candidate_rank"] for row in result] == [1, 2, 3, 4, 5]
    assert len({row["code"] for row in result}) == 5
    assert result[0]["candidate_action"] == "BUY_IF_TRIGGERED"
    assert result[0]["formal_buy_eligible"] is True
    assert all(row["candidate_action"] == "WATCH_ONLY" for row in result[1:])
    assert all(row["risk_budget_max_position_pct"] == 0.0 for row in result[1:])


def test_daily_candidate_top5_safely_fills_from_quant_rows() -> None:
    deep = [{
        "code": "000001", "stock_name": "深度候选", "actionability_rank": 1,
        "user_visible_level": "CONDITION_WATCH",
    }]
    fallback = [
        {"code": f"00000{index}", "stock_name": f"量化{index}", "quant_rank": index}
        for index in range(1, 7)
    ]
    result = build_daily_candidate_top5(
        deep_rows=deep, daily_signals=[], fallback_rows=fallback, limit=5,
    )
    assert len(result) == 5
    assert len({row["code"] for row in result}) == 5
    assert result[-1]["user_visible_level"] == "RESEARCH_PENDING"
    assert all(row["formal_buy_eligible"] is False for row in result)


def test_daily_candidate_top5_never_fills_with_hard_rejects() -> None:
    result = build_daily_candidate_top5(
        deep_rows=[], daily_signals=[],
        fallback_rows=[{
            "code": f"00000{index}", "quant_rank": index,
            "quant_status": "HARD_REJECT", "hard_blockers": "price_limit_risk",
        } for index in range(1, 7)],
        limit=5,
    )

    assert result == []


def test_daily_candidate_top5_prioritizes_formal_buy_even_when_ranked_sixth() -> None:
    deep_rows = [
        {"code": f"00000{index}", "actionability_rank": index, "user_visible_level": "CONDITION_WATCH"}
        for index in range(1, 6)
    ] + [{
        "code": "000006", "actionability_rank": 6,
        "user_visible_level": "STRICT_REVIEW_READY",
        "risk_budget_initial_position_pct": 2.0,
        "risk_budget_max_position_pct": 5.0,
    }]
    signals = [
        {"code": f"00000{index}", "signal_action": "WATCH_ONLY"}
        for index in range(1, 6)
    ] + [{"code": "000006", "signal_action": "BUY_IF_TRIGGERED"}]

    result = build_daily_candidate_top5(
        deep_rows=deep_rows, daily_signals=signals, limit=5,
    )

    assert result[0]["code"] == "000006"
    assert result[0]["formal_buy_eligible"] is True
    assert len(result) == 5


def test_daily_candidate_top5_ranks_closest_safe_strict_candidate_first() -> None:
    high_score_far = {
        "code": "600690", "stock_name": "高分但较远", "actionability_rank": 1,
        "user_visible_level": "RESEARCH_WATCH", "strict_gate_fail_count": 7,
        "strict_gate_failed": (
            "price_percentile_le_35;exit_profile_passed;exit_profile_sample_count;"
            "exit_profile_recent_2y_samples;exit_profile_confidence;real_rr_1_8;ready_plan"
        ),
        "missing_conditions": "near_ma60",
    }
    close = {
        "code": "603658", "stock_name": "更接近", "actionability_rank": 5,
        "user_visible_level": "CONDITION_WATCH", "strict_gate_fail_count": 3,
        "strict_gate_failed": "exit_profile_passed;exit_profile_sample_count;exit_profile_confidence",
    }
    unsafe = {
        "code": "600332", "stock_name": "事件高风险", "actionability_rank": 2,
        "user_visible_level": "CONDITION_WATCH", "strict_gate_fail_count": 3,
        "strict_gate_failed": "exit_profile_passed;event_risk_known;event_risk_not_high",
    }
    signals = [
        {"code": row["code"], "signal_action": "WATCH_ONLY", "signal_reason": "strict_gates_not_passed"}
        for row in (high_score_far, close, unsafe)
    ]

    result = build_daily_candidate_top5(
        deep_rows=[high_score_far, unsafe, close], daily_signals=signals, limit=3,
    )

    assert [row["code"] for row in result] == ["603658", "600690", "600332"]
    assert result[1]["missing_conditions"] == high_score_far["strict_gate_failed"]
    assert result[0]["strict_gate_failure_family_count"] == 1
    assert result[-1]["strict_safety_blocker_count"] == 2


def test_daily_signals_emit_strict_buy_and_cancel_when_previous_row_disappears() -> None:
    current_strict = {
        **_candidate(), **_plan(), "code": "000001", "stock_name": "严格候选",
        "user_visible_level": "STRICT_REVIEW_READY", "preferred_plan": "pullback",
        "raw_latest_close": 10.5, "latest_trade_date": "2026-07-17",
        "pullback_entry_low": 10.1, "pullback_entry_high": 10.4,
        "pullback_stop_price": 9.6, "pullback_logic_invalidation_price": 9.5,
        "pullback_target_1": 11.5, "pullback_target_2": 12.0,
        "risk_budget_initial_position_pct": 2.0, "risk_budget_max_position_pct": 5.0,
    }
    current_watch = {
        **current_strict, "code": "000002", "stock_name": "观察候选",
        "user_visible_level": "CONDITION_WATCH", "missing_conditions": "industry_evidence",
        "risk_budget_initial_position_pct": 0.0, "risk_budget_max_position_pct": 0.0,
    }
    previous = {
        "000003": {
            **current_strict, "code": "000003", "stock_name": "昨日严格候选",
            "user_visible_level": "STRICT_REVIEW_READY",
            "plan_rule_version": RULE_VERSION,
            "latest_trade_date": "2026-07-16",
            "signal_observed_through_date": "2026-07-16",
        }
    }
    signals = build_daily_signals(
        current_rows=[current_strict, current_watch], previous=previous,
        current_market_rows=[{
            "code": "000003", "latest_trade_date": "2026-07-17",
            "raw_latest_open": 10.5, "raw_latest_high": 10.6,
            "raw_latest_low": 10.2, "raw_latest_close": 10.4,
            "adjustment_ratio": 1.0,
            "adjusted_latest_open": 10.5, "adjusted_latest_high": 10.6,
            "adjusted_latest_low": 10.2, "adjusted_latest_close": 10.4,
            "adjusted_latest_volume": 1_000.0, "ma20": 10.1, "ma60": 10.0,
        }],
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )
    by_code = {row["code"]: row for row in signals}
    assert by_code["000001"]["signal_action"] == "BUY_IF_TRIGGERED"
    assert by_code["000002"]["signal_action"] == "WATCH_ONLY"
    assert by_code["000003"]["signal_action"] == "HOLD_REVIEW"
    assert by_code["000003"]["current_lifecycle_state"] == "POSITION_REVIEW"
    assert by_code["000003"]["signal_reason"] == "pullback_entry_observed_active_evidence_stale"
    assert by_code["000003"]["position_confirmation_required"] is True
    assert by_code["000003"]["live_exit_policy_state"]
    assert by_code["000003"]["signal_data_status"] == "ACTIVE_EVIDENCE_STALE"
    assert by_code["000002"]["risk_budget_initial_position_pct"] == 0.0


def test_breakout_confirmation_same_bar_replay_stays_buy_then_waits_for_next_open() -> None:
    plan = {
        **_candidate(),
        "code": "000001", "stock_name": "突破测试", "user_visible_level": "STRICT_REVIEW_READY",
        "preferred_plan": "breakout", "latest_trade_date": "2026-07-28",
        "plan_rule_version": RULE_VERSION,
        "signal_observed_through_date": "2026-07-28",
        "raw_latest_open": 9.9, "raw_latest_high": 10.1, "raw_latest_low": 9.8,
        "raw_latest_close": 10.0, "raw_latest_volume": 900.0,
        "breakout_trigger_price": 10.1, "breakout_max_chase_price": 10.5,
        "breakout_required_volume": 1_000.0, "breakout_stop_price": 9.5,
        "breakout_logic_invalidation_price": 9.4, "breakout_target_1": 11.5,
        "breakout_target_2": 12.0, "risk_budget_initial_position_pct": 2.0,
        "risk_budget_max_position_pct": 5.0, "signal_lifecycle_state": "ENTRY_PENDING",
    }
    initial = build_daily_signals(
        current_rows=[plan], previous={}, as_of=date(2026, 7, 28),
        next_trade_date=date(2026, 7, 29),
    )[0]
    assert initial["signal_action"] == "WATCH_ONLY"
    assert initial["signal_reason"] == "breakout_close_confirmation_pending"

    confirmation_row = {
        **plan, "latest_trade_date": "2026-07-29", "raw_latest_open": 10.0,
        "raw_latest_high": 10.4, "raw_latest_low": 9.8, "raw_latest_close": 10.3,
        "raw_latest_volume": 1_500.0,
    }
    confirmed = build_daily_signals(
        current_rows=[confirmation_row], previous={"000001": plan},
        as_of=date(2026, 7, 29), next_trade_date=date(2026, 7, 30),
    )[0]
    assert confirmed["signal_action"] == "BUY_IF_TRIGGERED"
    assert confirmed["signal_reason"] == "breakout_close_confirmed_next_open_pending"
    assert confirmed["current_lifecycle_state"] == "BREAKOUT_CONFIRMED_ENTRY_PENDING"
    assert confirmed["breakout_confirmation_observed_today"] is True
    assert confirmed["trigger_observed_today"] is False

    confirmed_state = _build_signal_state_rows(
        current_rows=[confirmation_row], previous={"000001": plan},
        daily_signals=[confirmed], current_market_rows=[confirmation_row],
        as_of=date(2026, 7, 29),
    )[0]
    confirmed_replay = build_daily_signals(
        current_rows=[confirmation_row], previous={"000001": confirmed_state},
        as_of=date(2026, 7, 29), next_trade_date=date(2026, 7, 30),
    )[0]
    assert confirmed_replay["signal_action"] == "BUY_IF_TRIGGERED"
    assert confirmed_replay["signal_reason"] == "breakout_close_confirmed_next_open_pending"
    assert confirmed_replay["current_lifecycle_state"] == "BREAKOUT_CONFIRMED_ENTRY_PENDING"
    assert confirmed_replay["breakout_confirmation_observed_today"] is True

    execution = build_actionable_execution_list(
        strict_rows=[confirmation_row], daily_signals=[confirmed],
        next_trade_date=date(2026, 7, 30),
    )
    assert len(execution) == 1
    assert execution[0]["entry_low"] == 10.1
    assert execution[0]["entry_high"] == 10.5
    assert "上一完整交易日已经收盘放量确认" in execution[0]["trigger_condition"]

    frozen = {
        **plan, "latest_trade_date": "2026-07-29",
        "signal_observed_through_date": "2026-07-29",
        "signal_lifecycle_state": "BREAKOUT_CONFIRMED_ENTRY_PENDING",
    }
    entry_day = {
        **confirmation_row, "latest_trade_date": "2026-07-30", "raw_latest_open": 10.2,
        "raw_latest_high": 10.6, "raw_latest_low": 9.8, "raw_latest_close": 10.4,
        "adjustment_ratio": 1.0,
        "adjusted_latest_open": 10.2, "adjusted_latest_high": 10.6,
        "adjusted_latest_low": 9.8, "adjusted_latest_close": 10.4,
        "adjusted_latest_volume": 1_500.0, "ma20": 10.0, "ma60": 9.8,
    }
    observed = build_daily_signals(
        current_rows=[entry_day], previous={"000001": frozen},
        as_of=date(2026, 7, 30), next_trade_date=date(2026, 7, 31),
    )[0]
    assert observed["signal_action"] == "HOLD_REVIEW"
    assert observed["trigger_observed_today"] is True
    assert observed["current_lifecycle_state"] == "ENTRY_TRIGGER_OBSERVED"

    gap_entry = {**entry_day, "raw_latest_open": 10.8, "raw_latest_low": 10.6}
    cancelled = build_daily_signals(
        current_rows=[gap_entry], previous={"000001": frozen},
        as_of=date(2026, 7, 30), next_trade_date=date(2026, 7, 31),
    )[0]
    assert cancelled["signal_action"] == "CANCEL_BUY_REVIEW"
    assert cancelled["signal_reason"] == "breakout_next_open_above_max_chase"


def test_daily_signal_cancels_buy_review_when_strict_qualification_is_lost() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试", "user_visible_level": "STRICT_REVIEW_READY",
            "preferred_plan": "pullback", "pullback_stop_price": 10.0,
            "pullback_logic_invalidation_price": 9.8,
            "plan_rule_version": RULE_VERSION,
            "latest_trade_date": "2026-07-16",
            "signal_observed_through_date": "2026-07-16",
        }
    }
    current = {
        **previous["000001"], "user_visible_level": "CONDITION_WATCH",
        "raw_latest_close": 10.5, "latest_trade_date": "2026-07-17",
        "missing_conditions": "market_regime_not_red",
        "risk_budget_initial_position_pct": 0.0, "risk_budget_max_position_pct": 0.0,
    }
    signal = build_daily_signals(
        current_rows=[current], previous=previous,
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]
    assert signal["signal_action"] == "CANCEL_BUY_REVIEW"
    assert signal["signal_reason"] == "strict_signal_lost:market_regime_not_red"
    assert signal["risk_budget_max_position_pct"] == 0.0


def test_exit_threshold_same_bar_replay_stays_sell() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试", "user_visible_level": "STRICT_REVIEW_READY",
            "preferred_plan": "pullback", "pullback_stop_price": 10.0,
            "pullback_logic_invalidation_price": 9.8,
            "signal_lifecycle_state": "ENTRY_TRIGGER_OBSERVED",
            "latest_trade_date": "2026-07-16",
            "signal_observed_through_date": "2026-07-16",
        }
    }
    current = {
        **previous["000001"], "raw_latest_close": 9.7, "latest_trade_date": "2026-07-17",
        "missing_conditions": "", "risk_budget_initial_position_pct": 2.0,
        "risk_budget_max_position_pct": 5.0,
    }
    signal = build_daily_signals(
        current_rows=[current], previous=previous,
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]
    assert signal["signal_action"] == "SELL_EXIT"
    assert signal["risk_budget_initial_position_pct"] == 0.0
    assert signal["risk_budget_max_position_pct"] == 0.0
    assert signal["signal_reason"] == "previous_logic_invalidation_breached"
    assert signal["stop_price"] == 10.0
    assert signal["position_confirmation_required"] is True

    state = _build_signal_state_rows(
        current_rows=[current], previous=previous, daily_signals=[signal],
        current_market_rows=[current], as_of=date(2026, 7, 17),
    )[0]
    replay = build_daily_signals(
        current_rows=[current], previous={"000001": state},
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]
    assert replay["signal_action"] == "SELL_EXIT"
    assert replay["signal_reason"] == "previous_logic_invalidation_breached"
    assert replay["current_lifecycle_state"] == "EXIT_THRESHOLD_BREACHED"


def test_daily_signal_detects_intraday_stop_even_if_close_recovers() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试", "user_visible_level": "STRICT_REVIEW_READY",
            "preferred_plan": "pullback", "pullback_stop_price": 10.0,
            "pullback_logic_invalidation_price": 9.8,
            "signal_lifecycle_state": "ENTRY_TRIGGER_OBSERVED",
            "latest_trade_date": "2026-07-16",
            "signal_observed_through_date": "2026-07-16",
        }
    }
    current = {
        **previous["000001"], "raw_latest_close": 10.2, "raw_latest_low": 9.9,
        "latest_trade_date": "2026-07-17",
        "risk_budget_initial_position_pct": 2.0, "risk_budget_max_position_pct": 5.0,
    }
    signal = build_daily_signals(
        current_rows=[current], previous=previous,
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]
    assert signal["signal_action"] == "SELL_EXIT"
    assert signal["latest_price"] == 10.2
    assert signal["threshold_observation_price"] == 9.9


def test_pending_pullback_invalidation_same_bar_replay_stays_cancelled() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试", "user_visible_level": "STRICT_REVIEW_READY",
            "preferred_plan": "pullback", "pullback_stop_price": 10.0,
            "pullback_logic_invalidation_price": 9.8,
            "signal_lifecycle_state": "ENTRY_PENDING",
            "plan_rule_version": RULE_VERSION,
            "latest_trade_date": "2026-07-16",
            "signal_observed_through_date": "2026-07-16",
        }
    }
    current = {
        **previous["000001"], "raw_latest_close": 9.7, "latest_trade_date": "2026-07-17",
        "risk_budget_initial_position_pct": 2.0, "risk_budget_max_position_pct": 5.0,
    }
    signal = build_daily_signals(
        current_rows=[current], previous=previous,
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]
    assert signal["signal_action"] == "CANCEL_BUY_REVIEW"
    assert signal["signal_reason"] == "entry_invalidated_before_position_confirmation"
    assert signal["current_lifecycle_state"] == "ENTRY_INVALIDATED"

    state = _build_signal_state_rows(
        current_rows=[current], previous=previous, daily_signals=[signal],
        current_market_rows=[current], as_of=date(2026, 7, 17),
    )[0]
    replay = build_daily_signals(
        current_rows=[current], previous={"000001": state},
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]
    assert replay["signal_action"] == "CANCEL_BUY_REVIEW"
    assert replay["signal_reason"] == "entry_invalidated_before_position_confirmation"
    assert replay["current_lifecycle_state"] == "ENTRY_INVALIDATED"


def test_observed_entry_trigger_moves_pending_signal_to_manual_hold_review() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试", "user_visible_level": "STRICT_REVIEW_READY",
            "preferred_plan": "pullback", "pullback_entry_low": 10.0,
            "pullback_entry_high": 10.4, "pullback_stop_price": 9.5,
            "pullback_logic_invalidation_price": 9.3,
            "signal_lifecycle_state": "ENTRY_PENDING",
            "plan_rule_version": RULE_VERSION,
            "latest_trade_date": "2026-07-16",
            "signal_observed_through_date": "2026-07-16",
        }
    }
    current = {
        **previous["000001"], "raw_latest_open": 10.5,
        "raw_latest_close": 10.2, "raw_latest_low": 10.1,
        "raw_latest_high": 10.5, "latest_trade_date": "2026-07-17",
        "adjustment_ratio": 1.0,
        "adjusted_latest_open": 10.5, "adjusted_latest_close": 10.2,
        "adjusted_latest_low": 10.1, "adjusted_latest_high": 10.5,
        "adjusted_latest_volume": 1_000.0, "ma20": 10.0, "ma60": 9.8,
        "risk_budget_initial_position_pct": 2.0, "risk_budget_max_position_pct": 5.0,
    }
    signal = build_daily_signals(
        current_rows=[current], previous=previous,
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]
    assert signal["signal_action"] == "HOLD_REVIEW"
    assert signal["trigger_observed_today"] is True
    assert signal["current_lifecycle_state"] == "ENTRY_TRIGGER_OBSERVED"
    assert signal["position_confirmation_required"] is True


def _initialized_live_exit_case() -> tuple[dict, dict, dict]:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试", "user_visible_level": "STRICT_REVIEW_READY",
            "preferred_plan": "pullback", "exit_profile_entry_mode": "pullback",
            "trend_confirmation_level": "MEDIUM",
            "pullback_entry_low": 10.0, "pullback_entry_high": 10.4,
            "pullback_stop_price": 9.5, "pullback_logic_invalidation_price": 9.3,
            "pullback_target_1": 11.5, "pullback_target_2": 12.0,
            "signal_lifecycle_state": "ENTRY_PENDING", "plan_rule_version": RULE_VERSION,
            "latest_trade_date": "2026-07-16", "signal_observed_through_date": "2026-07-16",
        }
    }
    entry_row = {
        **previous["000001"], "latest_trade_date": "2026-07-17",
        "raw_latest_open": 10.5, "raw_latest_high": 10.6,
        "raw_latest_low": 10.1, "raw_latest_close": 10.2,
        "adjustment_ratio": 1.0,
        "adjusted_latest_open": 10.5, "adjusted_latest_high": 10.6,
        "adjusted_latest_low": 10.1, "adjusted_latest_close": 10.2,
        "adjusted_latest_volume": 1_000.0, "ma20": 10.0, "ma60": 9.8,
        "risk_budget_initial_position_pct": 2.0, "risk_budget_max_position_pct": 5.0,
    }
    signal = build_daily_signals(
        current_rows=[entry_row], previous=previous,
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]
    state = _build_signal_state_rows(
        current_rows=[entry_row], previous=previous, daily_signals=[signal],
        current_market_rows=[entry_row], as_of=date(2026, 7, 17),
    )[0]
    return entry_row, signal, state


def test_live_balanced_exit_initializes_when_reference_entry_is_observed() -> None:
    _entry_row, signal, state = _initialized_live_exit_case()

    assert signal["signal_action"] == "HOLD_REVIEW"
    assert signal["current_lifecycle_state"] == "ENTRY_TRIGGER_OBSERVED"
    assert signal["assumed_entry_price"] == 10.4
    assert signal["entry_reference_adjusted_price"] == 10.4
    assert signal["exit_policy_adjusted_stop_price"] == 9.5
    assert signal["entry_adjustment_ratio"] == 1.0
    assert signal["live_exit_policy_version"] == LIVE_BALANCED_EXIT_POLICY_VERSION
    assert signal["live_exit_policy_status"] == "ACTIVE"
    assert signal["live_exit_holding_sessions"] == 1
    assert signal["live_exit_policy_state"]["execution_status"] == REFERENCE_EXECUTION_STATUS
    assert signal["live_exit_policy_state"]["execution_confirmation_required"] is True
    assert state["live_exit_policy_state"] == signal["live_exit_policy_state"]


def test_live_balanced_exit_same_day_replay_does_not_advance_state() -> None:
    entry_row, signal, state = _initialized_live_exit_case()
    history = _mapping_history([("2026-07-17", 10.2)])

    replay = build_daily_signals_production(
        current_rows=[entry_row], previous={"000001": state},
        adjusted_histories={"000001": history}, raw_histories={"000001": history},
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]
    replay_state = _build_signal_state_rows(
        current_rows=[entry_row], previous={"000001": state}, daily_signals=[replay],
        current_market_rows=[entry_row], as_of=date(2026, 7, 17),
    )[0]

    assert replay["signal_action"] == signal["signal_action"] == "HOLD_REVIEW"
    assert replay["signal_reason"] == signal["signal_reason"]
    assert replay["signal_input_version"] == signal["signal_input_version"]
    assert replay["_same_observation_replay"] is True
    assert replay["live_exit_holding_sessions"] == 1
    assert replay["live_exit_policy_state"] == signal["live_exit_policy_state"]
    assert replay_state["live_exit_policy_state"] == state["live_exit_policy_state"]


def test_live_balanced_exit_emits_sell_on_next_complete_bar_and_replays_idempotently() -> None:
    entry_row, _entry_signal, entry_state = _initialized_live_exit_case()
    exit_row = {
        **entry_row, "latest_trade_date": "2026-07-20",
        "raw_latest_open": 9.7, "raw_latest_high": 9.8,
        "raw_latest_low": 9.1, "raw_latest_close": 9.6,
        "adjusted_latest_open": 9.7, "adjusted_latest_high": 9.8,
        "adjusted_latest_low": 9.1, "adjusted_latest_close": 9.6,
        "adjusted_latest_volume": 1_200.0, "ma20": 10.0, "ma60": 9.8,
    }
    sell = build_daily_signals(
        current_rows=[exit_row], previous={"000001": entry_state},
        as_of=date(2026, 7, 20), next_trade_date=date(2026, 7, 21),
    )[0]

    assert sell["signal_action"] == "SELL_EXIT"
    assert sell["signal_reason"] == "balanced_exit_triggered:STOP_LOSS"
    assert sell["current_lifecycle_state"] == "EXIT_THRESHOLD_BREACHED"
    assert sell["position_confirmation_required"] is True
    assert sell["live_exit_policy_status"] == "EXIT_TRIGGERED"
    assert sell["live_exit_holding_sessions"] == 2
    assert sell["live_exit_policy_state"]["exit_trigger_trade_date"] == "2026-07-20"

    exit_state = _build_signal_state_rows(
        current_rows=[exit_row], previous={"000001": entry_state}, daily_signals=[sell],
        current_market_rows=[exit_row], as_of=date(2026, 7, 20),
    )[0]
    replay = build_daily_signals(
        current_rows=[exit_row], previous={"000001": exit_state},
        as_of=date(2026, 7, 20), next_trade_date=date(2026, 7, 21),
    )[0]

    assert replay["signal_action"] == "SELL_EXIT"
    assert replay["signal_reason"] == "balanced_exit_triggered:STOP_LOSS"
    assert replay["live_exit_holding_sessions"] == 2
    assert replay["live_exit_policy_state"] == sell["live_exit_policy_state"]


def test_live_logic_invalidation_matches_profile_state_machine() -> None:
    entry_bar = {
        "date": "2026-07-17", "open": 10.0, "high": 10.1, "low": 9.9,
        "close": 10.0, "volume": 1_000.0, "ma20": 9.9, "ma60": 9.8,
    }
    initialized = evaluate_live_balanced_v7_exit(
        entry_price=10.0,
        stop_loss=9.7,
        logic_invalidation_price=9.58,
        trend_confirmation_level="MEDIUM",
        previous_state=None,
        bar=entry_bar,
    )
    previous = {
        "000001": {
            "code": "000001", "stock_name": "逻辑失效测试",
            "user_visible_level": "STRICT_REVIEW_READY", "preferred_plan": "pullback",
            "pullback_entry_low": 9.8, "pullback_entry_high": 10.0,
            "pullback_stop_price": 9.7, "pullback_logic_invalidation_price": 9.58,
            "pullback_target_1": 11.0, "pullback_target_2": 11.5,
            "signal_lifecycle_state": "ENTRY_TRIGGER_OBSERVED",
            "plan_rule_version": RULE_VERSION,
            "latest_trade_date": "2026-07-17",
            "signal_observed_through_date": "2026-07-17",
            "entry_observation_trade_date": "2026-07-17",
            "entry_reference_adjusted_price": 10.0,
            "exit_policy_adjusted_stop_price": 9.7,
            "entry_adjustment_ratio": 1.0,
            "entry_setup_trend_confirmation_level": "MEDIUM",
            "live_exit_policy_state": initialized["state"],
        },
    }
    current = {
        **previous["000001"], "latest_trade_date": "2026-07-20",
        "raw_latest_open": 9.7, "raw_latest_high": 9.8,
        "raw_latest_low": 9.5, "raw_latest_close": 9.55,
        "adjustment_ratio": 1.0,
        "adjusted_latest_open": 9.7, "adjusted_latest_high": 9.8,
        "adjusted_latest_low": 9.5, "adjusted_latest_close": 9.55,
        "adjusted_latest_volume": 1_200.0, "ma20": 9.8, "ma60": 9.7,
    }
    history = _mapping_history([
        ("2026-07-17", 10.0), ("2026-07-20", 9.55),
    ])

    signal = build_daily_signals_production(
        current_rows=[current], previous=previous,
        adjusted_histories={"000001": history}, raw_histories={"000001": history},
        as_of=date(2026, 7, 20), next_trade_date=date(2026, 7, 21),
    )[0]

    assert signal["signal_action"] == "SELL_EXIT"
    assert signal["signal_reason"] == "balanced_exit_triggered:LOGIC_INVALIDATION"
    assert signal["live_exit_policy_state"]["exit_reason"] == "LOGIC_INVALIDATION"
    assert signal["exit_earliest_trade_date"] == "2026-07-21"


def test_live_balanced_exit_adjustment_ratio_change_requires_manual_review() -> None:
    entry_row, _entry_signal, entry_state = _initialized_live_exit_case()
    corporate_action_row = {
        **entry_row, "latest_trade_date": "2026-07-20", "adjustment_ratio": 2.0,
        "entry_date_adjustment_ratio_status": "OK",
        "entry_date_adjustment_ratio_current": 2.0,
        "raw_latest_open": 10.3, "raw_latest_high": 10.5,
        "raw_latest_low": 10.1, "raw_latest_close": 10.4,
        "adjusted_latest_open": 5.15, "adjusted_latest_high": 5.25,
        "adjusted_latest_low": 5.05, "adjusted_latest_close": 5.2,
        "adjusted_latest_volume": 1_200.0, "ma20": 5.0, "ma60": 4.9,
    }
    review = build_daily_signals(
        current_rows=[corporate_action_row], previous={"000001": entry_state},
        as_of=date(2026, 7, 20), next_trade_date=date(2026, 7, 21),
    )[0]

    assert review["signal_action"] == "HOLD_REVIEW"
    assert review["signal_reason"] == "live_exit_policy_review:adjustment_ratio_changed"
    assert review["signal_data_status"] == "LIVE_EXIT_STATE_REQUIRES_REVIEW"
    assert review["current_lifecycle_state"] == "POSITION_REVIEW"
    assert review["position_confirmation_required"] is True
    assert review["live_exit_policy_status"] == "CORPORATE_ACTION_REVIEW"
    assert review["live_exit_policy_reason"] == "adjustment_ratio_changed"
    assert review["live_exit_policy_state"] == entry_state["live_exit_policy_state"]


def test_qfq_rebase_at_entry_date_blocks_false_split_sell_with_latest_ratio_unchanged() -> None:
    entry_row, _entry_signal, entry_state = _initialized_live_exit_case()
    split_row = {
        **entry_row, "latest_trade_date": "2026-07-20", "adjustment_ratio": 1.0,
        "raw_latest_open": 5.2, "raw_latest_high": 5.3,
        "raw_latest_low": 5.0, "raw_latest_close": 5.2,
        "adjusted_latest_open": 5.2, "adjusted_latest_high": 5.3,
        "adjusted_latest_low": 5.0, "adjusted_latest_close": 5.2,
        "adjusted_latest_volume": 1_200.0, "ma20": 5.1, "ma60": 5.0,
    }
    adjusted = _mapping_history([
        ("2026-07-17", 5.1), ("2026-07-20", 5.2),
    ])
    raw = _mapping_history([
        ("2026-07-17", 10.2), ("2026-07-20", 5.2),
    ])

    review = build_daily_signals_production(
        current_rows=[split_row], previous={"000001": entry_state},
        adjusted_histories={"000001": adjusted}, raw_histories={"000001": raw},
        as_of=date(2026, 7, 20), next_trade_date=date(2026, 7, 21),
    )[0]

    assert review["signal_action"] == "HOLD_REVIEW"
    assert review["signal_reason"] == "live_exit_policy_review:adjustment_ratio_changed"
    assert review["current_lifecycle_state"] == "POSITION_REVIEW"
    assert review["live_exit_policy_status"] == "CORPORATE_ACTION_REVIEW"


def test_entry_basis_change_precedes_stale_raw_stop_during_run_gap() -> None:
    entry_row, _entry_signal, entry_state = _initialized_live_exit_case()
    split_row = {
        **entry_row, "latest_trade_date": "2026-07-22", "adjustment_ratio": 1.0,
        "raw_latest_open": 5.2, "raw_latest_high": 5.3,
        "raw_latest_low": 4.8, "raw_latest_close": 5.0,
        "adjusted_latest_open": 5.2, "adjusted_latest_high": 5.3,
        "adjusted_latest_low": 4.8, "adjusted_latest_close": 5.0,
        "adjusted_latest_volume": 1_200.0, "ma20": 5.1, "ma60": 5.0,
    }
    adjusted = _mapping_history([
        ("2026-07-17", 5.1), ("2026-07-22", 5.0),
    ])
    raw = _mapping_history([
        ("2026-07-17", 10.2), ("2026-07-22", 5.0),
    ])

    review = build_daily_signals_production(
        current_rows=[split_row], previous={"000001": entry_state},
        adjusted_histories={"000001": adjusted}, raw_histories={"000001": raw},
        as_of=date(2026, 7, 22), next_trade_date=date(2026, 7, 23),
    )[0]

    assert review["signal_action"] == "SELL_EXIT"
    assert review["signal_reason"] == "balanced_or_frozen_hard_exit_with_run_gap"
    assert "RUN_GAP" in review["signal_data_status"]


def test_missing_entry_date_mapping_fails_closed_and_does_not_advance_state() -> None:
    entry_row, _entry_signal, entry_state = _initialized_live_exit_case()
    current = {
        **entry_row, "latest_trade_date": "2026-07-20", "adjustment_ratio": 1.0,
        "raw_latest_open": 10.3, "raw_latest_high": 10.5,
        "raw_latest_low": 10.1, "raw_latest_close": 10.4,
        "adjusted_latest_open": 10.3, "adjusted_latest_high": 10.5,
        "adjusted_latest_low": 10.1, "adjusted_latest_close": 10.4,
        "adjusted_latest_volume": 1_200.0, "ma20": 10.1, "ma60": 10.0,
    }
    adjusted = _mapping_history([("2026-07-20", 10.4)])
    raw = _mapping_history([
        ("2026-07-17", 10.2), ("2026-07-20", 10.4),
    ])

    review = build_daily_signals_production(
        current_rows=[current], previous={"000001": entry_state},
        adjusted_histories={"000001": adjusted}, raw_histories={"000001": raw},
        as_of=date(2026, 7, 20), next_trade_date=date(2026, 7, 21),
    )[0]
    state = _build_signal_state_rows(
        current_rows=[current], previous={"000001": entry_state}, daily_signals=[review],
        current_market_rows=[current], as_of=date(2026, 7, 20),
    )[0]

    assert review["signal_action"] == "HOLD_REVIEW"
    assert review["signal_reason"] == "live_exit_policy_review:entry_adjustment_basis_missing"
    assert review["signal_bar_processed"] is False
    assert state["signal_observed_through_date"] == "2026-07-17"
    assert state["unresolved_signal_gap"] is True


def test_pending_plan_qfq_rebase_cancels_before_any_entry_trigger() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试",
            "user_visible_level": "STRICT_REVIEW_READY", "preferred_plan": "pullback",
            "exit_profile_entry_mode": "pullback", "pullback_entry_low": 10.0,
            "pullback_entry_high": 10.4, "pullback_stop_price": 9.5,
            "pullback_logic_invalidation_price": 9.3,
            "signal_lifecycle_state": "ENTRY_PENDING", "plan_rule_version": RULE_VERSION,
            "signal_plan_origin_trade_date": "2026-07-17",
            "signal_plan_adjustment_ratio": 1.0,
            "latest_trade_date": "2026-07-17", "signal_observed_through_date": "2026-07-17",
        }
    }
    current = {
        **previous["000001"], "latest_trade_date": "2026-07-20",
        "adjustment_ratio": 1.0, "raw_latest_open": 5.2,
        "raw_latest_high": 5.3, "raw_latest_low": 5.0, "raw_latest_close": 5.2,
    }
    adjusted = _mapping_history([
        ("2026-07-17", 5.1), ("2026-07-20", 5.2),
    ])
    raw = _mapping_history([
        ("2026-07-17", 10.2), ("2026-07-20", 5.2),
    ])

    signal = build_daily_signals_production(
        current_rows=[current], previous=previous,
        adjusted_histories={"000001": adjusted}, raw_histories={"000001": raw},
        as_of=date(2026, 7, 20), next_trade_date=date(2026, 7, 21),
    )[0]

    assert signal["signal_action"] == "CANCEL_BUY_REVIEW"
    assert signal["signal_reason"] == "signal_plan_adjustment_ratio_changed"
    assert signal["current_lifecycle_state"] == "ENTRY_CANCELLED"
    assert signal["trigger_observed_today"] is False


def test_exact_factor_prevents_rounded_qfq_noise_from_cancelling_plan() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试",
            "user_visible_level": "STRICT_REVIEW_READY", "preferred_plan": "pullback",
            "exit_profile_entry_mode": "pullback", "pullback_entry_low": 10.0,
            "pullback_entry_high": 10.4, "pullback_stop_price": 9.5,
            "pullback_logic_invalidation_price": 9.3,
            "signal_lifecycle_state": "ENTRY_PENDING", "plan_rule_version": RULE_VERSION,
            "signal_plan_origin_trade_date": "2026-07-17",
            "signal_plan_adjustment_ratio": 1.0,
            "latest_trade_date": "2026-07-17",
            "signal_observed_through_date": "2026-07-17",
        }
    }
    current = {
        **previous["000001"], "latest_trade_date": "2026-07-20",
        "adjustment_ratio": 1.001, "raw_latest_open": 10.8,
        "raw_latest_high": 10.9, "raw_latest_low": 10.6,
        "raw_latest_close": 10.8,
    }
    exact = _mapping_history([
        ("2026-07-17", 10.01), ("2026-07-20", 10.8),
    ])
    exact["adjustment_ratio"] = 1.0
    raw = _mapping_history([
        ("2026-07-17", 10.01), ("2026-07-20", 10.8),
    ])

    signal = build_daily_signals_production(
        current_rows=[current], previous=previous,
        adjusted_histories={"000001": exact}, raw_histories={"000001": raw},
        as_of=date(2026, 7, 20), next_trade_date=date(2026, 7, 21),
    )[0]

    assert price_mapping_ratio_at_date(
        exact, raw, trade_date="2026-07-17",
    ) == 1.0
    assert signal["signal_reason"] == "entry_trigger_still_pending"
    assert signal["signal_plan_adjustment_ratio_current"] == 1.0


def test_same_trade_date_price_correction_moves_position_to_review() -> None:
    entry_row, _entry_signal, entry_state = _initialized_live_exit_case()
    normal = {
        **entry_row, "latest_trade_date": "2026-07-20", "adjustment_ratio": 1.0,
        "raw_latest_open": 10.3, "raw_latest_high": 10.6,
        "raw_latest_low": 10.1, "raw_latest_close": 10.4,
        "adjusted_latest_open": 10.3, "adjusted_latest_high": 10.6,
        "adjusted_latest_low": 10.1, "adjusted_latest_close": 10.4,
        "adjusted_latest_volume": 1_200.0, "ma20": 10.1, "ma60": 10.0,
    }
    history = _mapping_history([
        ("2026-07-17", 10.2), ("2026-07-20", 10.4),
    ])
    first = build_daily_signals_production(
        current_rows=[normal], previous={"000001": entry_state},
        adjusted_histories={"000001": history}, raw_histories={"000001": history},
        as_of=date(2026, 7, 20), next_trade_date=date(2026, 7, 21),
    )[0]
    state = _build_signal_state_rows(
        current_rows=[normal], previous={"000001": entry_state}, daily_signals=[first],
        current_market_rows=[normal], as_of=date(2026, 7, 20),
    )[0]
    corrected = {
        **normal, "raw_latest_low": 9.0, "adjusted_latest_low": 9.0,
    }

    review = build_daily_signals_production(
        current_rows=[corrected], previous={"000001": state},
        adjusted_histories={"000001": history}, raw_histories={"000001": history},
        as_of=date(2026, 7, 20), next_trade_date=date(2026, 7, 21),
    )[0]

    assert review["signal_action"] == "HOLD_REVIEW"
    assert review["signal_reason"] == "same_trade_date_input_changed_position_review"
    assert review["signal_bar_processed"] is False


def test_pullback_open_below_entry_band_cancels_without_trigger() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试", "user_visible_level": "STRICT_REVIEW_READY",
            "preferred_plan": "pullback", "exit_profile_entry_mode": "pullback",
            "pullback_entry_low": 10.0, "pullback_entry_high": 10.4,
            "pullback_stop_price": 9.5, "pullback_logic_invalidation_price": 9.3,
            "signal_lifecycle_state": "ENTRY_PENDING",
            "plan_rule_version": RULE_VERSION,
            "latest_trade_date": "2026-07-16",
            "signal_observed_through_date": "2026-07-16",
        }
    }
    current = {
        **previous["000001"], "latest_trade_date": "2026-07-17",
        "raw_latest_open": 9.8, "raw_latest_high": 10.2,
        "raw_latest_low": 9.7, "raw_latest_close": 9.9,
    }

    signal = build_daily_signals(
        current_rows=[current], previous=previous,
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]

    assert signal["signal_action"] == "CANCEL_BUY_REVIEW"
    assert signal["signal_reason"] == "pullback_open_below_entry_band"
    assert signal["current_lifecycle_state"] == "ENTRY_CANCELLED"
    assert signal["trigger_observed_today"] is False
    assert signal["assumed_entry_price"] in {None, ""}


def test_one_price_pullback_bar_cancels_without_reference_position() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试",
            "user_visible_level": "STRICT_REVIEW_READY", "preferred_plan": "pullback",
            "exit_profile_entry_mode": "pullback", "pullback_entry_low": 10.0,
            "pullback_entry_high": 10.4, "pullback_stop_price": 9.5,
            "pullback_logic_invalidation_price": 9.3,
            "signal_lifecycle_state": "ENTRY_PENDING", "plan_rule_version": RULE_VERSION,
            "latest_trade_date": "2026-07-16",
            "signal_observed_through_date": "2026-07-16",
        }
    }
    current = {
        **previous["000001"], "latest_trade_date": "2026-07-17",
        "raw_latest_open": 10.2, "raw_latest_high": 10.2,
        "raw_latest_low": 10.2, "raw_latest_close": 10.2,
    }

    signal = build_daily_signals(
        current_rows=[current], previous=previous,
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]

    assert signal["signal_action"] == "CANCEL_BUY_REVIEW"
    assert signal["signal_reason"] == "pullback_locked_one_price_unexecutable"
    assert signal["current_lifecycle_state"] == "ENTRY_CANCELLED"
    assert signal["assumed_entry_price"] in {None, ""}
    assert signal["live_exit_policy_state"] in {None, ""}


def test_factor_change_cannot_be_overwritten_by_same_day_entry_and_stop() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试",
            "user_visible_level": "STRICT_REVIEW_READY", "preferred_plan": "pullback",
            "exit_profile_entry_mode": "pullback", "pullback_entry_low": 10.0,
            "pullback_entry_high": 10.4, "pullback_stop_price": 9.5,
            "pullback_logic_invalidation_price": 9.3,
            "signal_lifecycle_state": "ENTRY_PENDING", "plan_rule_version": RULE_VERSION,
            "signal_plan_adjustment_ratio": 1.0,
            "signal_plan_origin_trade_date": "2026-07-16",
            "latest_trade_date": "2026-07-16",
            "signal_observed_through_date": "2026-07-16",
        }
    }
    current = {
        **previous["000001"], "latest_trade_date": "2026-07-17",
        "raw_latest_open": 10.2, "raw_latest_high": 10.5,
        "raw_latest_low": 9.2, "raw_latest_close": 10.1,
        "adjustment_ratio": 1.001,
        "signal_plan_adjustment_ratio_status": "OK",
        "signal_plan_adjustment_ratio_current": 1.001,
    }

    signal = build_daily_signals(
        current_rows=[current], previous=previous,
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]

    assert signal["signal_action"] == "CANCEL_BUY_REVIEW"
    assert signal["signal_reason"] == "signal_plan_adjustment_ratio_changed"
    assert signal["current_lifecycle_state"] == "ENTRY_CANCELLED"
    assert signal["assumed_entry_price"] in {None, ""}
    assert signal["live_exit_policy_state"] in {None, ""}


def test_pullback_entry_and_stop_on_same_bar_emits_t1_exit_and_keeps_state() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试", "user_visible_level": "STRICT_REVIEW_READY",
            "preferred_plan": "pullback", "exit_profile_entry_mode": "pullback",
            "pullback_entry_low": 10.0, "pullback_entry_high": 10.4,
            "pullback_stop_price": 9.5, "pullback_logic_invalidation_price": 9.3,
            "signal_lifecycle_state": "ENTRY_PENDING",
            "plan_rule_version": RULE_VERSION,
            "latest_trade_date": "2026-07-16",
            "signal_observed_through_date": "2026-07-16",
        }
    }
    current = {
        **previous["000001"], "latest_trade_date": "2026-07-17",
        "raw_latest_open": 10.5, "raw_latest_high": 10.6,
        "raw_latest_low": 9.2, "raw_latest_close": 10.1,
        "adjustment_ratio": 1.0,
        "adjusted_latest_open": 10.5, "adjusted_latest_high": 10.6,
        "adjusted_latest_low": 9.2, "adjusted_latest_close": 10.1,
        "adjusted_latest_volume": 1_000.0, "ma20": 10.0, "ma60": 9.8,
        "trend_confirmation_level": "MEDIUM",
    }

    signal = build_daily_signals(
        current_rows=[current], previous=previous,
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]

    assert signal["signal_action"] == "SELL_EXIT"
    assert signal["signal_reason"] == "entry_and_exit_same_day_t1:STOP_LOSS"
    assert signal["current_lifecycle_state"] == "EXIT_THRESHOLD_BREACHED"
    assert signal["trigger_observed_today"] is True
    assert signal["position_confirmation_required"] is True
    assert signal["exit_earliest_trade_date"] == "2026-07-20"
    assert signal["exit_execution_timing"] == "NEXT_TRADE_SESSION_OPEN"
    assert signal["entry_reference_adjusted_price"] == pytest.approx(10.4)
    assert signal["live_exit_policy_state"]["exit_reason"] == "STOP_LOSS"


def test_pending_pullback_plan_cancels_when_current_mode_changes_to_breakout() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试", "user_visible_level": "STRICT_REVIEW_READY",
            "preferred_plan": "pullback", "exit_profile_entry_mode": "pullback",
            "pullback_entry_low": 10.0, "pullback_entry_high": 10.4,
            "pullback_stop_price": 9.5, "pullback_logic_invalidation_price": 9.3,
            "signal_lifecycle_state": "ENTRY_PENDING",
            "plan_rule_version": RULE_VERSION,
            "latest_trade_date": "2026-07-16",
            "signal_observed_through_date": "2026-07-16",
        }
    }
    current = {
        **previous["000001"], "latest_trade_date": "2026-07-17",
        "preferred_plan": "breakout", "exit_profile_entry_mode": "breakout",
        "breakout_trigger_price": 11.0, "breakout_max_chase_price": 11.3,
        "breakout_required_volume": 1_000.0, "breakout_stop_price": 10.4,
        "breakout_logic_invalidation_price": 10.3,
        "raw_latest_open": 10.6, "raw_latest_high": 10.8,
        "raw_latest_low": 10.5, "raw_latest_close": 10.7, "raw_latest_volume": 900.0,
    }

    signal = build_daily_signals(
        current_rows=[current], previous=previous,
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]

    assert signal["signal_action"] == "CANCEL_BUY_REVIEW"
    assert signal["signal_reason"] == "entry_plan_mode_changed"
    assert signal["current_lifecycle_state"] == "ENTRY_CANCELLED"
    assert signal["preferred_plan"] == "pullback"


def test_unversioned_legacy_pending_plan_cancels_as_incompatible() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试", "user_visible_level": "STRICT_REVIEW_READY",
            "preferred_plan": "pullback", "exit_profile_entry_mode": "pullback",
            "pullback_entry_low": 10.0, "pullback_entry_high": 10.4,
            "pullback_stop_price": 9.5, "pullback_logic_invalidation_price": 9.3,
            "signal_lifecycle_state": "ENTRY_PENDING",
            "latest_trade_date": "2026-07-16",
            "signal_observed_through_date": "2026-07-16",
        }
    }
    current = {
        **previous["000001"], "latest_trade_date": "2026-07-17",
        "raw_latest_open": 10.8, "raw_latest_high": 10.9,
        "raw_latest_low": 10.6, "raw_latest_close": 10.7,
    }

    signal = build_daily_signals(
        current_rows=[current], previous=previous,
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]

    assert signal["signal_action"] == "CANCEL_BUY_REVIEW"
    assert signal["signal_reason"] == "entry_plan_rule_version_incompatible"
    assert signal["current_lifecycle_state"] == "ENTRY_CANCELLED"


def test_fixed_pending_plan_expires_on_tenth_processed_bar_without_trigger() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试", "user_visible_level": "STRICT_REVIEW_READY",
            "preferred_plan": "pullback", "exit_profile_entry_mode": "pullback",
            "pullback_entry_low": 10.0, "pullback_entry_high": 10.4,
            "pullback_stop_price": 9.5, "pullback_logic_invalidation_price": 9.3,
            "pullback_target_1": 11.5, "plan_id": "plan:frozen",
            "entry_plan_age_sessions": 9, "signal_lifecycle_state": "ENTRY_PENDING",
            "plan_rule_version": RULE_VERSION,
            "latest_trade_date": "2026-07-16",
            "signal_observed_through_date": "2026-07-16",
        }
    }
    current = {
        **previous["000001"], "latest_trade_date": "2026-07-17",
        "pullback_entry_low": 8.8, "pullback_entry_high": 9.2,
        "pullback_stop_price": 8.0, "pullback_logic_invalidation_price": 7.8,
        "raw_latest_open": 11.0, "raw_latest_high": 11.2,
        "raw_latest_low": 10.8, "raw_latest_close": 11.0,
    }

    signal = build_daily_signals(
        current_rows=[current], previous=previous,
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]

    assert signal["signal_action"] == "CANCEL_BUY_REVIEW"
    assert signal["signal_reason"] == "entry_trigger_window_expired"
    assert signal["current_lifecycle_state"] == "ENTRY_CANCELLED"
    assert signal["entry_plan_age_sessions"] == 10
    assert signal["entry_low"] == 10.0
    assert signal["stop_price"] == 9.5
    assert signal["plan_id"] == "plan:frozen"


def test_missing_watchlist_row_uses_current_market_price_for_active_exit() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试", "user_visible_level": "STRICT_REVIEW_READY",
            "preferred_plan": "pullback", "pullback_stop_price": 10.0,
            "pullback_logic_invalidation_price": 9.8,
            "signal_lifecycle_state": "ENTRY_TRIGGER_OBSERVED",
            "latest_trade_date": "2026-07-16",
            "signal_observed_through_date": "2026-07-16",
        }
    }
    signal = build_daily_signals(
        current_rows=[], previous=previous,
        current_market_rows=[{
            "code": "000001", "raw_latest_close": 9.7,
            "latest_trade_date": "2026-07-17",
        }],
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]
    assert signal["signal_action"] == "SELL_EXIT"
    assert signal["signal_data_status"] == "ACTIVE_EVIDENCE_STALE"
    assert signal["latest_price"] == 9.7


def test_triggered_plan_is_frozen_when_current_recalculation_moves_stop() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试", "user_visible_level": "STRICT_REVIEW_READY",
            "preferred_plan": "pullback", "pullback_entry_low": 10.0,
            "pullback_entry_high": 10.4, "pullback_stop_price": 10.0,
            "pullback_logic_invalidation_price": 9.8, "pullback_target_1": 11.5,
            "signal_lifecycle_state": "ENTRY_TRIGGER_OBSERVED",
            "latest_trade_date": "2026-07-16",
            "signal_observed_through_date": "2026-07-16",
        }
    }
    current = {
        **previous["000001"], "latest_trade_date": "2026-07-17",
        "raw_latest_close": 10.5, "raw_latest_low": 10.2, "raw_latest_high": 10.7,
        "pullback_entry_low": 8.8, "pullback_entry_high": 9.2,
        "pullback_stop_price": 8.0, "pullback_logic_invalidation_price": 7.8,
        "pullback_target_1": 10.8, "risk_budget_initial_position_pct": 2.0,
        "risk_budget_max_position_pct": 5.0,
    }

    signal = build_daily_signals(
        current_rows=[current], previous=previous,
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]
    state = _build_signal_state_rows(
        current_rows=[current], previous=previous, daily_signals=[signal],
        current_market_rows=[current], as_of=date(2026, 7, 17),
    )[0]

    assert signal["signal_action"] == "HOLD_REVIEW"
    assert signal["stop_price"] == 10.0
    assert state["pullback_stop_price"] == 10.0
    assert state["signal_plan_origin_trade_date"] == "2026-07-16"


def test_monitored_orphan_is_persisted_and_can_exit_on_later_run(tmp_path: Path) -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试", "user_visible_level": "STRICT_REVIEW_READY",
            "preferred_plan": "pullback", "pullback_stop_price": 10.0,
            "pullback_logic_invalidation_price": 9.8,
            "signal_lifecycle_state": "POSITION_REVIEW",
            "latest_trade_date": "2026-07-16",
            "signal_observed_through_date": "2026-07-16",
        }
    }
    friday_market = [{
        "code": "000001", "latest_trade_date": "2026-07-17",
        "raw_latest_close": 10.5, "raw_latest_low": 10.2,
    }]
    friday_signal = build_daily_signals(
        current_rows=[], previous=previous, current_market_rows=friday_market,
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]
    state_rows = _build_signal_state_rows(
        current_rows=[], previous=previous, daily_signals=[friday_signal],
        current_market_rows=friday_market, as_of=date(2026, 7, 17),
    )
    state_file = tmp_path / "last_all_a_state.json"
    _changes([], state_file, state_rows=state_rows)
    persisted = json.loads(state_file.read_text(encoding="utf-8"))["by_code"]

    assert persisted["000001"]["signal_lifecycle_state"] == "POSITION_REVIEW"
    monday_signal = build_daily_signals(
        current_rows=[], previous=persisted,
        current_market_rows=[{
            "code": "000001", "latest_trade_date": "2026-07-20",
            "raw_latest_close": 9.9, "raw_latest_low": 9.7,
        }],
        as_of=date(2026, 7, 20), next_trade_date=date(2026, 7, 21),
    )[0]
    assert monday_signal["signal_action"] == "SELL_EXIT"
    assert monday_signal["stop_price"] == 10.0


def test_previous_only_same_trade_date_correction_requires_position_review() -> None:
    entry_row, _entry_signal, entry_state = _initialized_live_exit_case()
    normal = {
        **entry_row, "latest_trade_date": "2026-07-20", "adjustment_ratio": 1.0,
        "raw_latest_open": 10.3, "raw_latest_high": 10.6,
        "raw_latest_low": 10.1, "raw_latest_close": 10.4,
        "adjusted_latest_open": 10.3, "adjusted_latest_high": 10.6,
        "adjusted_latest_low": 10.1, "adjusted_latest_close": 10.4,
        "adjusted_latest_volume": 1_200.0, "ma20": 10.1, "ma60": 10.0,
    }
    history = _mapping_history([
        ("2026-07-17", 10.2), ("2026-07-20", 10.4),
    ])
    first = build_daily_signals_production(
        current_rows=[], previous={"000001": entry_state}, current_market_rows=[normal],
        adjusted_histories={"000001": history}, raw_histories={"000001": history},
        as_of=date(2026, 7, 20), next_trade_date=date(2026, 7, 21),
    )[0]
    state = _build_signal_state_rows(
        current_rows=[], previous={"000001": entry_state}, daily_signals=[first],
        current_market_rows=[normal], as_of=date(2026, 7, 20),
    )[0]
    corrected = {**normal, "raw_latest_low": 9.0, "adjusted_latest_low": 9.0}

    review = build_daily_signals_production(
        current_rows=[], previous={"000001": state}, current_market_rows=[corrected],
        adjusted_histories={"000001": history}, raw_histories={"000001": history},
        as_of=date(2026, 7, 20), next_trade_date=date(2026, 7, 21),
    )[0]

    assert review["signal_action"] == "CANCEL_BUY_REVIEW"
    assert review["signal_reason"] == "same_trade_date_input_changed_position_review"
    assert review["current_lifecycle_state"] == "POSITION_REVIEW"
    assert review["signal_bar_processed"] is False


def test_previous_only_breakout_entry_and_stop_same_day_emits_t1_exit_with_state() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试",
            "user_visible_level": "STRICT_REVIEW_READY", "preferred_plan": "breakout",
            "exit_profile_entry_mode": "breakout", "breakout_trigger_price": 10.1,
            "breakout_max_chase_price": 10.5, "breakout_stop_price": 9.5,
            "breakout_logic_invalidation_price": 9.4,
            "signal_lifecycle_state": "BREAKOUT_CONFIRMED_ENTRY_PENDING",
            "plan_rule_version": RULE_VERSION,
            "signal_plan_origin_trade_date": "2026-07-17",
            "signal_plan_adjustment_ratio": 1.0,
            "latest_trade_date": "2026-07-17", "signal_observed_through_date": "2026-07-17",
        }
    }
    market = {
        "code": "000001", "latest_trade_date": "2026-07-20", "adjustment_ratio": 1.0,
        "raw_latest_open": 10.2, "raw_latest_high": 10.6,
        "raw_latest_low": 9.2, "raw_latest_close": 10.4,
        "adjusted_latest_open": 10.2, "adjusted_latest_high": 10.6,
        "adjusted_latest_low": 9.2, "adjusted_latest_close": 10.4,
        "adjusted_latest_volume": 1_200.0, "ma20": 10.1, "ma60": 10.0,
    }
    history = _mapping_history([
        ("2026-07-17", 10.0), ("2026-07-20", 10.4),
    ])

    review = build_daily_signals_production(
        current_rows=[], previous=previous, current_market_rows=[market],
        adjusted_histories={"000001": history}, raw_histories={"000001": history},
        as_of=date(2026, 7, 20), next_trade_date=date(2026, 7, 21),
    )[0]

    assert review["signal_action"] == "SELL_EXIT"
    assert review["signal_reason"] == "entry_and_exit_same_day_t1:STOP_LOSS"
    assert review["current_lifecycle_state"] == "EXIT_THRESHOLD_BREACHED"
    assert review["trigger_observed_today"] is True
    assert review["entry_reference_adjusted_price"] == pytest.approx(10.2)
    assert review["exit_earliest_trade_date"] == "2026-07-21"
    assert review["live_exit_policy_state"]["exit_reason"] == "STOP_LOSS"


def test_previous_only_breakout_entry_same_day_replay_is_idempotent() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试",
            "user_visible_level": "STRICT_REVIEW_READY", "preferred_plan": "breakout",
            "exit_profile_entry_mode": "breakout", "breakout_trigger_price": 10.1,
            "breakout_max_chase_price": 10.5, "breakout_stop_price": 9.5,
            "breakout_logic_invalidation_price": 9.4,
            "signal_lifecycle_state": "BREAKOUT_CONFIRMED_ENTRY_PENDING",
            "plan_rule_version": RULE_VERSION,
            "signal_plan_origin_trade_date": "2026-07-17",
            "signal_plan_adjustment_ratio": 1.0,
            "latest_trade_date": "2026-07-17", "signal_observed_through_date": "2026-07-17",
        }
    }
    market = {
        "code": "000001", "latest_trade_date": "2026-07-20", "adjustment_ratio": 1.0,
        "raw_latest_open": 10.2, "raw_latest_high": 10.6,
        "raw_latest_low": 9.8, "raw_latest_close": 10.4,
        "adjusted_latest_open": 10.2, "adjusted_latest_high": 10.6,
        "adjusted_latest_low": 9.8, "adjusted_latest_close": 10.4,
        "adjusted_latest_volume": 1_200.0, "ma20": 10.1, "ma60": 10.0,
    }
    history = _mapping_history([
        ("2026-07-17", 10.0), ("2026-07-20", 10.4),
    ])
    first = build_daily_signals_production(
        current_rows=[], previous=previous, current_market_rows=[market],
        adjusted_histories={"000001": history}, raw_histories={"000001": history},
        as_of=date(2026, 7, 20), next_trade_date=date(2026, 7, 21),
    )[0]
    state = _build_signal_state_rows(
        current_rows=[], previous=previous, daily_signals=[first],
        current_market_rows=[market], as_of=date(2026, 7, 20),
    )[0]
    replay = build_daily_signals_production(
        current_rows=[], previous={"000001": state}, current_market_rows=[market],
        adjusted_histories={"000001": history}, raw_histories={"000001": history},
        as_of=date(2026, 7, 20), next_trade_date=date(2026, 7, 21),
    )[0]

    assert first["signal_action"] == replay["signal_action"] == "HOLD_REVIEW"
    assert replay["signal_reason"] == first["signal_reason"]
    assert replay["signal_input_version"] == first["signal_input_version"]
    assert replay["live_exit_holding_sessions"] == 1
    assert replay["_same_observation_replay"] is True


@pytest.mark.parametrize(
    (
        "lifecycle", "expected_action", "expected_lifecycle",
        "expected_reason", "expected_data_status",
    ),
    [
        (
            "ENTRY_PENDING", "SELL_EXIT", "EXIT_THRESHOLD_BREACHED",
            "run_gap_possible_entry_and_frozen_threshold_breached",
            "RUN_GAP_REQUIRES_POSITION_CONFIRMATION",
        ),
        (
            "ENTRY_TRIGGER_OBSERVED", "SELL_EXIT", "EXIT_THRESHOLD_BREACHED",
            "balanced_or_frozen_hard_exit_with_run_gap",
            "RUN_GAP_REQUIRES_REVIEW",
        ),
    ],
)
def test_run_gap_only_emits_sell_for_observed_position_with_clear_hard_stop(
    lifecycle: str, expected_action: str, expected_lifecycle: str,
    expected_reason: str, expected_data_status: str,
) -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试", "user_visible_level": "STRICT_REVIEW_READY",
            "preferred_plan": "pullback", "pullback_entry_low": 10.0,
            "pullback_entry_high": 10.4, "pullback_stop_price": 9.5,
            "pullback_logic_invalidation_price": 9.3,
            "signal_lifecycle_state": lifecycle,
            "plan_rule_version": RULE_VERSION,
            "latest_trade_date": "2026-07-23",
            "signal_observed_through_date": "2026-07-23",
        }
    }
    current = {
        **previous["000001"], "latest_trade_date": "2026-07-27",
        "raw_latest_close": 9.0, "raw_latest_low": 8.8, "raw_latest_high": 10.5,
        "risk_budget_initial_position_pct": 2.0, "risk_budget_max_position_pct": 5.0,
    }

    signal = build_daily_signals(
        current_rows=[current], previous=previous,
        as_of=date(2026, 7, 27), next_trade_date=date(2026, 7, 28),
    )[0]

    assert signal["signal_action"] == expected_action
    assert signal["signal_data_status"] == expected_data_status
    assert signal["current_lifecycle_state"] == expected_lifecycle
    assert signal["signal_reason"] == expected_reason
    assert signal["position_confirmation_required"] is True


def test_signal_state_does_not_advance_observed_date_across_run_gap() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试", "user_visible_level": "STRICT_REVIEW_READY",
            "preferred_plan": "pullback", "exit_profile_entry_mode": "pullback",
            "pullback_entry_low": 10.0, "pullback_entry_high": 10.4,
            "pullback_stop_price": 9.5, "pullback_logic_invalidation_price": 9.3,
            "signal_lifecycle_state": "ENTRY_PENDING",
            "plan_rule_version": RULE_VERSION,
            "latest_trade_date": "2026-07-23",
            "signal_observed_through_date": "2026-07-23",
        }
    }
    current = {
        **previous["000001"], "latest_trade_date": "2026-07-27",
        "raw_latest_open": 10.8, "raw_latest_high": 10.9,
        "raw_latest_low": 10.6, "raw_latest_close": 10.7,
    }
    signal = build_daily_signals(
        current_rows=[current], previous=previous,
        as_of=date(2026, 7, 27), next_trade_date=date(2026, 7, 28),
    )[0]
    state = _build_signal_state_rows(
        current_rows=[current], previous=previous, daily_signals=[signal],
        current_market_rows=[current], as_of=date(2026, 7, 27),
    )[0]

    assert signal["signal_data_status"] == "RUN_GAP_REQUIRES_POSITION_CONFIRMATION"
    assert state["signal_observed_through_date"] == "2026-07-23"
    assert state["scan_as_of_date"] == "2026-07-27"
    assert state["unresolved_signal_gap"] is True


def test_same_as_of_rerun_does_not_replay_plan_creation_bar_as_entry_trigger() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试", "user_visible_level": "STRICT_REVIEW_READY",
            "preferred_plan": "pullback", "pullback_entry_low": 10.0,
            "pullback_entry_high": 10.4, "pullback_stop_price": 9.5,
            "pullback_logic_invalidation_price": 9.3,
            "signal_lifecycle_state": "ENTRY_PENDING",
            "plan_rule_version": RULE_VERSION,
            "latest_trade_date": "2026-07-17",
            "signal_observed_through_date": "2026-07-17",
        }
    }
    current = {
        **previous["000001"], "raw_latest_close": 10.2,
        "raw_latest_low": 10.1, "raw_latest_high": 10.5,
        "risk_budget_initial_position_pct": 2.0, "risk_budget_max_position_pct": 5.0,
    }

    signal = build_daily_signals(
        current_rows=[current], previous=previous,
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]

    assert signal["signal_action"] == "BUY_IF_TRIGGERED"
    assert signal["current_lifecycle_state"] == "ENTRY_PENDING"
    assert signal["trigger_observed_today"] is False


def test_new_frozen_plan_same_day_rerun_keeps_identical_input_version() -> None:
    current = {
        **_candidate(), "code": "000001", "stock_name": "测试",
        "user_visible_level": "STRICT_REVIEW_READY", "preferred_plan": "pullback",
        "exit_profile_entry_mode": "pullback", "latest_trade_date": "2026-07-17",
        "adjustment_ratio": 1.0, "raw_latest_open": 10.8,
        "raw_latest_high": 10.9, "raw_latest_low": 10.6, "raw_latest_close": 10.7,
        "pullback_entry_low": 10.0, "pullback_entry_high": 10.4,
        "pullback_stop_price": 9.5, "pullback_logic_invalidation_price": 9.3,
    }
    history = _mapping_history([("2026-07-17", 10.7)])
    first = build_daily_signals_production(
        current_rows=[current], previous={},
        adjusted_histories={"000001": history}, raw_histories={"000001": history},
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]
    state = _build_signal_state_rows(
        current_rows=[current], previous={}, daily_signals=[first],
        current_market_rows=[current], as_of=date(2026, 7, 17),
    )[0]
    replay = build_daily_signals_production(
        current_rows=[current], previous={"000001": state},
        adjusted_histories={"000001": history}, raw_histories={"000001": history},
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]

    assert first["signal_action"] == replay["signal_action"] == "BUY_IF_TRIGGERED"
    assert replay["signal_reason"] == first["signal_reason"]
    assert replay["signal_input_version"] == first["signal_input_version"]
    assert replay["_same_observation_replay"] is True


def test_no_hardcoded_sample_stocks_in_all_a_module() -> None:
    text = Path("src/strategies/genge_opportunity_discovery/all_a_full_scan.py").read_text(encoding="utf-8")
    for token in ("牧原股份", "TCL科技", "002714", "000100"):
        assert token not in text


def test_disclaimer_and_no_broker_or_order_calls() -> None:
    text = Path("src/strategies/genge_opportunity_discovery/all_a_full_scan.py").read_text(encoding="utf-8")
    assert "仅用于公开数据研究观察和人工复核，不构成买入或卖出建议，不应自动交易。" in text
    for forbidden_call in ("place_order(", "submit_order(", "cancel_order(", "order_api."):
        assert forbidden_call not in text.lower()
