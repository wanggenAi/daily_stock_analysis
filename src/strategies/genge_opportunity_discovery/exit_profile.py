"""Deterministic balanced-exit profile generation for opportunity discovery."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXIT_PROFILE_COLUMNS = [
    "code",
    "stock_name",
    "balanced_exit_historical_profile",
    "signal_count",
    "avg_balanced_exit_net_return_60d",
    "win_rate_balanced_exit_60d",
    "avg_balanced_exit_max_drawdown_250d",
    "source_signal_details",
    "generated_at",
    "rule",
]


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    return text.zfill(6) if text.isdigit() else text


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _candidate_signal_files(source_dirs: Iterable[str | Path]) -> list[Path]:
    files: list[Path] = []
    for source_dir in source_dirs:
        root = Path(source_dir)
        if not root.exists():
            continue
        files.extend(root.glob("**/signal_details.csv"))
    return sorted(set(files), key=lambda path: path.stat().st_mtime, reverse=True)


def _status_for(values: list[float], drawdowns: list[float]) -> str:
    if len(values) < 2:
        return "NOT_AVAILABLE"
    avg_return = sum(values) / len(values)
    win_rate = sum(1 for value in values if value > 0) / len(values) * 100.0
    avg_drawdown = sum(drawdowns) / len(drawdowns) if drawdowns else None
    if avg_return >= 0 and win_rate >= 45 and (avg_drawdown is None or avg_drawdown >= -12):
        return "PASSED"
    if avg_return >= -4 and win_rate >= 30 and (avg_drawdown is None or avg_drawdown >= -18):
        return "DEGRADED"
    return "FAILED"


def generate_exit_profile_from_reports(
    *,
    output_file: str | Path,
    source_dirs: Iterable[str | Path] = ("reports",),
    max_files: int = 3,
) -> tuple[Path, dict[str, Any]]:
    """Generate a per-stock exit profile from existing historical signal files.

    This only aggregates already-produced historical walk-forward rows. It does
    not rerun backtests, optimize parameters, or inspect current opportunity
    signals.
    """

    files = _candidate_signal_files(source_dirs)[: max(0, int(max_files))]
    by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_by_code: dict[str, str] = {}
    for path in files:
        try:
            with path.open(encoding="utf-8") as file:
                reader = csv.DictReader(file)
                fields = set(reader.fieldnames or [])
                return_column = "balanced_hybrid_60d_exit_exit_adjusted_net_return_60d"
                drawdown_column = "balanced_hybrid_60d_exit_exit_adjusted_max_drawdown_250d"
                if return_column not in fields:
                    return_column = "exit_adjusted_net_return_60d"
                if drawdown_column not in fields:
                    drawdown_column = "exit_adjusted_max_drawdown_250d"
                for row in reader:
                    code = _normalize_code(row.get("code"))
                    if not code:
                        continue
                    value = _number(row.get(return_column))
                    if value is None:
                        continue
                    by_code[code].append(
                        {
                            "stock_name": row.get("stock_name") or "",
                            "return": value,
                            "drawdown": _number(row.get(drawdown_column)),
                        }
                    )
                    source_by_code.setdefault(code, str(path))
        except OSError:
            continue

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    for code, samples in sorted(by_code.items()):
        values = [float(item["return"]) for item in samples if item.get("return") is not None]
        drawdowns = [float(item["drawdown"]) for item in samples if item.get("drawdown") is not None]
        status = _status_for(values, drawdowns)
        rows.append(
            {
                "code": code,
                "stock_name": next((item.get("stock_name") for item in samples if item.get("stock_name")), ""),
                "balanced_exit_historical_profile": status,
                "signal_count": len(values),
                "avg_balanced_exit_net_return_60d": round(sum(values) / len(values), 4) if values else "",
                "win_rate_balanced_exit_60d": round(sum(1 for value in values if value > 0) / len(values) * 100.0, 4) if values else "",
                "avg_balanced_exit_max_drawdown_250d": round(sum(drawdowns) / len(drawdowns), 4) if drawdowns else "",
                "source_signal_details": source_by_code.get(code, ""),
                "generated_at": generated_at,
                "rule": "avg_return>=0/win_rate>=45/drawdown>=-12 => PASSED; avg_return>=-4/win_rate>=30/drawdown>=-18 => DEGRADED; else FAILED",
            }
        )

    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=EXIT_PROFILE_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    distribution = Counter(row["balanced_exit_historical_profile"] for row in rows)
    summary = {
        "exit_profile_file": str(path),
        "source_signal_detail_files": [str(path) for path in files],
        "generated": True,
        "row_count": len(rows),
        "distribution": dict(distribution),
    }
    return path, summary


def load_exit_profile_distribution(path: str | Path | None) -> dict[str, int]:
    if not path or not Path(path).exists():
        return {"NOT_AVAILABLE": 0}
    counts: Counter[str] = Counter()
    with Path(path).open(encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            status = str(row.get("balanced_exit_historical_profile") or row.get("exit_profile_status") or "NOT_AVAILABLE").strip().upper()
            counts[status or "NOT_AVAILABLE"] += 1
    for status in ("PASSED", "DEGRADED", "NOT_AVAILABLE", "FAILED"):
        counts.setdefault(status, 0)
    return dict(counts)
