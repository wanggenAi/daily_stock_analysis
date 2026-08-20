"""Production adapter for live forward scenarios from the unified Postscan artifact.

Postscan already carries the exact All-A snapshot used by the hard-logic bridge.
This adapter reuses that snapshot for peer prices and industry labels, fetches
live analyst EPS consensus, writes ``forward_scenario_valuation.csv`` into the
artifact tree, and then lets ``strict_hard_logic_price_map`` consume it normally.

The adapter intentionally fails closed on missing artifact contracts but degrades
analyst-provider outages to incomplete forward valuation.  A provider outage must
not fabricate EPS/PE and must not destroy the reference-only valuation fallback.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from . import forward_scenario_valuation as core
from .valuation_model_routing import find_latest_routing_source


PRODUCTION_PRICE_FIELDS = (
    "raw_latest_close",
    "latest_price",
    "current_price",
    "latest_close",
    "adjusted_latest_close",
    "close_price",
    "price",
    "close",
    "last_price",
    "收盘价",
    "最新价",
)


def _choose_path(root: Path, filename: str, preferred_token: str = "") -> Path | None:
    candidates = sorted(path for path in root.glob(f"**/{filename}") if path.is_file())
    if not candidates:
        return None
    if preferred_token:
        preferred = [path for path in candidates if preferred_token in str(path)]
        if preferred:
            return preferred[-1]
    return candidates[-1]


def _price(row: Mapping[str, Any]) -> float | None:
    for field in PRODUCTION_PRICE_FIELDS:
        value = core._positive(row.get(field))
        if value is not None:
            return value
    return None


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = ["current_price"] + [field for field in core.OUTPUT_COLUMNS if field != "current_price"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _read_as_of(report_dir: Path) -> date:
    payload = json.loads(
        (report_dir / "valuation_research_summary.json").read_text(encoding="utf-8")
    )
    value = str(payload.get("as_of_date") or "").strip()
    if not value:
        raise ValueError("valuation research as_of_date is unavailable")
    return date.fromisoformat(value)


def write_postscan_forward_scenarios(
    *,
    artifact_root: Path,
    output_dir: Path,
    cache_dir: Path,
    min_target_institutions: int = core.DEFAULT_MIN_TARGET_INSTITUTIONS,
    min_peer_reports: int = core.DEFAULT_MIN_PEER_REPORTS,
    min_peer_samples: int = core.DEFAULT_MIN_PEER_SAMPLES,
    max_workers: int = 4,
) -> list[dict[str, Any]]:
    report_dir = find_latest_routing_source(artifact_root)
    routed_path = report_dir / "valuation_research_routed.csv"
    hard_source_path = _choose_path(
        artifact_root,
        "all_a_quant_screen.csv",
        "hard_logic_valuation_source",
    )
    raw_snapshot_path = _choose_path(
        artifact_root,
        "raw_all_a_universe.csv",
        "hard_logic_valuation_source",
    )
    if not routed_path.exists():
        raise FileNotFoundError(f"routed valuation research unavailable: {routed_path}")
    if hard_source_path is None:
        raise FileNotFoundError("hard_logic_valuation_source/all_a_quant_screen.csv unavailable")
    if raw_snapshot_path is None:
        raise FileNotFoundError("hard_logic_valuation_source/raw_all_a_universe.csv unavailable")

    routed_rows = core._read_csv(routed_path)
    hard_source_rows = core._read_csv(hard_source_path)
    raw_rows = core._read_csv(raw_snapshot_path)
    if not routed_rows or not hard_source_rows or not raw_rows:
        raise ValueError("postscan forward-scenario source artifact is empty")

    as_of = _read_as_of(report_dir)
    hard_pass_codes = sorted(
        {
            core._normalize_code(row.get("code"))
            for row in hard_source_rows
            if core._normalize_code(row.get("code"))
            and str(row.get("hard_logic_state") or "").strip().upper() == "PASS"
        }
    )

    provider_errors: list[str] = []
    try:
        em_frame = core._load_or_fetch_em(cache_dir, as_of=as_of)
    except Exception as exc:  # public provider outage -> no invented peer PE
        provider_errors.append(f"eastmoney:{type(exc).__name__}:{exc}")
        em_frame = pd.DataFrame()

    ths_frames = core._fetch_target_ths_frames(
        hard_pass_codes,
        cache_dir=cache_dir,
        as_of=as_of,
        max_workers=max_workers,
    )
    failed_ths = sum(frame is None or frame.empty for frame in ths_frames.values())
    if failed_ths:
        provider_errors.append(f"ths_failed_or_empty:{failed_ths}/{len(hard_pass_codes)}")

    # The production All-A scan uses raw_latest_close/adjusted_latest_close.
    # Core keeps generic aliases for portable tests, so widen aliases only for
    # this exact production adapter.
    original_price_fields = core.PRICE_FIELDS
    core.PRICE_FIELDS = PRODUCTION_PRICE_FIELDS
    try:
        rows = core.build_forward_scenario_rows(
            routed_rows=routed_rows,
            hard_logic_source_rows=hard_source_rows,
            raw_all_a_rows=raw_rows,
            em_forecast_frame=em_frame,
            ths_frames=ths_frames,
            as_of=as_of,
            min_target_institutions=min_target_institutions,
            min_peer_reports=min_peer_reports,
            min_peer_samples=min_peer_samples,
        )
    finally:
        core.PRICE_FIELDS = original_price_fields

    raw_by_code = {
        core._normalize_code(row.get("code") or row.get("代码")): row
        for row in raw_rows
        if core._normalize_code(row.get("code") or row.get("代码"))
    }
    for row in rows:
        row["current_price"] = _price(raw_by_code.get(core._normalize_code(row.get("code")), {}))

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "forward_scenario_valuation.csv", rows)

    summary = {
        "as_of_date": as_of.isoformat(),
        "row_count": len(rows),
        "hard_logic_pass_input_count": len(hard_pass_codes),
        "hard_logic_pass_output_count": sum(
            str(row.get("hard_logic_state") or "").upper() == "PASS" for row in rows
        ),
        "current_price_ready_count": sum(core._positive(row.get("current_price")) is not None for row in rows),
        "forward_eps_base_ready_count": sum(core._positive(row.get("forward_eps_base")) is not None for row in rows),
        "three_scenario_eps_ready_count": sum(
            all(
                core._positive(row.get(field)) is not None
                for field in ("forward_eps_bear", "forward_eps_base", "forward_eps_bull")
            )
            for row in rows
        ),
        "reasonable_pe_ready_count": sum(row.get("reasonable_pe_status") == "OK" for row in rows),
        "forward_base_fair_value_ready_count": sum(
            core._positive(row.get("scenario_fair_price_base")) is not None for row in rows
        ),
        "provider_status": "OK" if not provider_errors else "DEGRADED",
        "provider_errors": provider_errors,
        "peer_price_source": "postscan_raw_all_a_snapshot:raw_latest_close_first",
        "reasonable_pe_policy_version": core.POLICY_VERSION,
        "reasonable_pe_anchor": "same_industry_same_forecast_year_current_forward_pe_distribution",
        "historical_pe_used_for_reasonable_pe": False,
        "analyst_consensus_is_live_not_historical_pit": True,
        "historical_backtest_eligible": False,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    (output_dir / "forward_scenario_valuation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Live Forward Scenario Valuation",
        "",
        "Hard logic precedes valuation. Historical PE is not used to create reasonable PE.",
        "Analyst consensus is a live research input and is not eligible for historical walk-forward backtests.",
        "",
        f"- as_of: {summary['as_of_date']}",
        f"- hard-logic PASS inputs: {summary['hard_logic_pass_input_count']}",
        f"- current price ready: {summary['current_price_ready_count']}",
        f"- forward EPS base ready: {summary['forward_eps_base_ready_count']}",
        f"- three-scenario EPS ready: {summary['three_scenario_eps_ready_count']}",
        f"- reasonable PE ready: {summary['reasonable_pe_ready_count']}",
        f"- base fair value ready: {summary['forward_base_fair_value_ready_count']}",
        f"- provider status: {summary['provider_status']}",
        "",
    ]
    for row in rows:
        lines.append(
            f"- {row.get('code')} {row.get('stock_name')} | {row.get('industry')} | "
            f"price={row.get('current_price')} | "
            f"EPS={row.get('forward_eps_bear')}/{row.get('forward_eps_base')}/{row.get('forward_eps_bull')} | "
            f"PE={row.get('reasonable_pe_bear')}/{row.get('reasonable_pe_base')}/{row.get('reasonable_pe_bull')} | "
            f"fair={row.get('scenario_fair_price_bear')}/{row.get('scenario_fair_price_base')}/{row.get('scenario_fair_price_bull')} | "
            f"status={row.get('scenario_valuation_status')}"
        )
    (output_dir / "forward_scenario_valuation.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data/cache/forward_scenario_consensus"),
    )
    parser.add_argument("--min-target-institutions", type=int, default=core.DEFAULT_MIN_TARGET_INSTITUTIONS)
    parser.add_argument("--min-peer-reports", type=int, default=core.DEFAULT_MIN_PEER_REPORTS)
    parser.add_argument("--min-peer-samples", type=int, default=core.DEFAULT_MIN_PEER_SAMPLES)
    parser.add_argument("--max-workers", type=int, default=4)
    args = parser.parse_args(argv)
    rows = write_postscan_forward_scenarios(
        artifact_root=args.artifact_root,
        output_dir=args.output_dir,
        cache_dir=args.cache_dir,
        min_target_institutions=args.min_target_institutions,
        min_peer_reports=args.min_peer_reports,
        min_peer_samples=args.min_peer_samples,
        max_workers=args.max_workers,
    )
    print(f"forward_scenario_postscan={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
