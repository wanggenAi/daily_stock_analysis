"""Run the All-A production scanner with progress logging and V3.1 BUY guard."""
from __future__ import annotations

import time
from collections.abc import Iterable, Iterator
from typing import Any

from src.strategies.genge_opportunity_discovery import all_a_full_scan as scan
from src.strategies.genge_opportunity_discovery import v31_formal_signal_guard


LOG_EVERY_ITEMS = 50
LOG_EVERY_SECONDS = 12.0


def _eta_text(seconds: float | None) -> str:
    if seconds is None or seconds < 0 or seconds == float("inf"):
        return "NA"
    value = int(seconds)
    hours, rem = divmod(value, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class _ProgressIterable:
    def __init__(self, rows: list[dict[str, Any]], stage: str):
        self.rows = rows
        self.stage = stage

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self) -> Iterator[dict[str, Any]]:
        total = len(self.rows)
        started = last_log = time.monotonic()
        processed = 0
        for row in self.rows:
            processed += 1
            now = time.monotonic()
            if (
                processed == 1
                or processed == total
                or processed % LOG_EVERY_ITEMS == 0
                or now - last_log >= LOG_EVERY_SECONDS
            ):
                elapsed = max(now - started, 1e-9)
                rate = processed / elapsed
                remaining = max(0, total - processed)
                eta = remaining / rate if rate > 0 else None
                code = str(row.get("code") or "")
                pct = processed / max(1, total) * 100.0
                print(
                    f"[ALL-A][{self.stage}] {processed}/{total} {pct:.1f}% | "
                    f"{rate:.2f} items/s | ETA {_eta_text(eta)} | current={code}",
                    flush=True,
                )
                last_log = now
            yield row


def _wrap_quant_screen() -> None:
    original = scan.quant_screen

    def wrapped(
        universe_rows,
        qfq_histories,
        raw_histories,
        price_audits,
        benchmark_qfq,
        *,
        as_of,
        board_rules,
    ):
        rows = list(universe_rows)
        active = sum(not bool(row.get("exclusion_reason")) for row in rows)
        print(
            f"[ALL-A][QUANT] start total={len(rows)} active={active}",
            flush=True,
        )
        result = original(
            _ProgressIterable(rows, "QUANT"),
            qfq_histories,
            raw_histories,
            price_audits,
            benchmark_qfq,
            as_of=as_of,
            board_rules=board_rules,
        )
        print(f"[ALL-A][QUANT] done candidates={len(result)}", flush=True)
        return result

    scan.quant_screen = wrapped


def _wrap_as_completed() -> None:
    original = scan.as_completed
    batch_no = 0

    def wrapped(fs: Iterable, *args, **kwargs):
        nonlocal batch_no
        batch_no += 1
        futures = list(fs)
        total = len(futures)
        started = last_log = time.monotonic()
        processed = 0
        print(f"[ALL-A][ASYNC-{batch_no}] start total={total}", flush=True)
        for future in original(futures, *args, **kwargs):
            processed += 1
            now = time.monotonic()
            if (
                processed == total
                or processed % LOG_EVERY_ITEMS == 0
                or now - last_log >= LOG_EVERY_SECONDS
            ):
                elapsed = max(now - started, 1e-9)
                rate = processed / elapsed
                remaining = max(0, total - processed)
                eta = remaining / rate if rate > 0 else None
                pct = processed / max(1, total) * 100.0
                print(
                    f"[ALL-A][ASYNC-{batch_no}] {processed}/{total} {pct:.1f}% | "
                    f"{rate:.2f} tasks/s | ETA {_eta_text(eta)}",
                    flush=True,
                )
                last_log = now
            yield future
        print(f"[ALL-A][ASYNC-{batch_no}] done total={total}", flush=True)

    scan.as_completed = wrapped


def install_progress_hooks() -> None:
    _wrap_as_completed()
    _wrap_quant_screen()


def main(argv: list[str] | None = None) -> int:
    install_progress_hooks()
    original_classify = scan.classify_candidate
    v31_formal_signal_guard.install()
    print("[ALL-A][PROGRESS] instrumentation=enabled", flush=True)
    print("[ALL-A][V3.1] formal-buy-guard=enabled", flush=True)
    try:
        return scan.main(argv)
    finally:
        scan.classify_candidate = original_classify


if __name__ == "__main__":
    raise SystemExit(main())
