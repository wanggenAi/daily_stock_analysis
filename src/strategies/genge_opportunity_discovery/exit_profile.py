"""Deterministic balanced-exit profile generation for opportunity discovery."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


PROFILE_RULE_VERSION = "genge_opportunity_discovery_v1"


EXIT_PROFILE_COLUMNS = [
    "code",
    "stock_name",
    "balanced_exit_historical_profile",
    "signal_count",
    "avg_balanced_exit_net_return_60d",
    "win_rate_balanced_exit_60d",
    "avg_balanced_exit_max_drawdown_250d",
    "source_signal_details",
    "profile_data_end_date",
    "profile_rule_version",
    "profile_data_version",
    "profile_confidence",
    "recent_2y_sample_count",
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


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _file_version(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _report_data_end_date(path: Path) -> date | None:
    summary_path = path.parent / "summary.json"
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    diagnostics = summary.get("diagnostics") if isinstance(summary, Mapping) else None
    return _parse_date((diagnostics or {}).get("end_date")) or _parse_date(summary.get("end_date"))


def _status_for(values: list[float], drawdowns: list[float]) -> str:
    sample_count = len(values)
    if sample_count < 10:
        return "NOT_AVAILABLE"
    avg_return = sum(values) / len(values)
    win_rate = sum(1 for value in values if value > 0) / len(values) * 100.0
    avg_drawdown = sum(drawdowns) / len(drawdowns) if drawdowns else None
    if sample_count >= 20 and avg_return >= 0 and win_rate >= 45 and (avg_drawdown is None or avg_drawdown >= -12):
        return "PASSED"
    if avg_return >= -4 and win_rate >= 30 and (avg_drawdown is None or avg_drawdown >= -18):
        return "DEGRADED"
    return "FAILED"


def generate_exit_profile_from_reports(
    *,
    output_file: str | Path,
    source_dirs: Iterable[str | Path] = ("reports",),
    max_files: int = 3,
    seed_file: str | Path | None = "data/opportunity_snapshots/exit_profile_seed.csv",
) -> tuple[Path, dict[str, Any]]:
    """Generate a per-stock exit profile from existing historical signal files.

    This only aggregates already-produced historical walk-forward rows. It does
    not rerun backtests, optimize parameters, or inspect current opportunity
    signals.
    """

    files = _candidate_signal_files(source_dirs)[: max(0, int(max_files))]
    by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_by_code: dict[str, str] = {}
    data_version_by_code: dict[str, str] = {}
    data_end_by_code: dict[str, date] = {}
    for path in files:
        try:
            data_version = _file_version(path)
            report_data_end_date = _report_data_end_date(path)
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
                            "as_of_date": _parse_date(row.get("as_of_date")),
                        }
                    )
                    source_by_code.setdefault(code, str(path))
                    data_version_by_code.setdefault(code, data_version)
                    if report_data_end_date is not None:
                        data_end_by_code.setdefault(code, report_data_end_date)
        except OSError:
            continue

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    for code, samples in sorted(by_code.items()):
        values = [float(item["return"]) for item in samples if item.get("return") is not None]
        drawdowns = [float(item["drawdown"]) for item in samples if item.get("drawdown") is not None]
        sample_dates = [item["as_of_date"] for item in samples if item.get("as_of_date") is not None]
        profile_data_end_date = data_end_by_code.get(code) or (max(sample_dates) if sample_dates else None)
        recent_cutoff = profile_data_end_date - timedelta(days=730) if profile_data_end_date else None
        recent_2y_sample_count = (
            sum(1 for item in samples if item.get("as_of_date") and item["as_of_date"] >= recent_cutoff)
            if recent_cutoff else 0
        )
        status = _status_for(values, drawdowns)
        profile_confidence = "HIGH" if len(values) >= 100 else "MEDIUM" if len(values) >= 30 else "LOW"
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
                "profile_data_end_date": profile_data_end_date.isoformat() if profile_data_end_date else "",
                "profile_rule_version": PROFILE_RULE_VERSION,
                "profile_data_version": data_version_by_code.get(code, ""),
                "profile_confidence": profile_confidence,
                "recent_2y_sample_count": recent_2y_sample_count,
                "generated_at": generated_at,
                "rule": "signals<10 => NOT_AVAILABLE; signals 10-19 max DEGRADED; signals>=20 and avg_return>=0/win_rate>=45/drawdown>=-12 => PASSED; avg_return>=-4/win_rate>=30/drawdown>=-18 => DEGRADED; else FAILED",
            }
        )

    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows and seed_file and Path(seed_file).exists():
        shutil.copyfile(seed_file, path)
        with path.open(encoding="utf-8") as file:
            row_count = max(0, sum(1 for _ in file) - 1)
        return path, {
            "exit_profile_file": str(path),
            "source_signal_detail_files": [str(path) for path in files],
            "seed_file": str(seed_file),
            "generated": False,
            "seed_used": True,
            "profile_rule_version": PROFILE_RULE_VERSION,
            "row_count": row_count,
            "distribution": load_exit_profile_distribution(path),
        }
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
        "profile_rule_version": PROFILE_RULE_VERSION,
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
