"""Risk-capped production entrypoint with frozen V3.1 formal-BUY guard.

The legacy wrapper installs complete-event, opportunity-engine and risk-capped
policies. We intercept only its call into the risk-capped runner so the V3.1
guard is installed *after* the risk-capped classifier and therefore remains the
last authority on Formal BUY eligibility.
"""
from __future__ import annotations

from src.strategies.genge_opportunity_discovery import risk_capped_all_a_full_scan as risk_capped
from src.strategies.genge_opportunity_discovery import risk_capped_complete_event_scan as legacy
from src.strategies.genge_opportunity_discovery import v31_formal_signal_guard


def _guarded_risk_capped_main(argv: list[str] | None = None) -> int:
    risk_capped.install_policy()
    v31_formal_signal_guard.install()
    print("[ALL-A][V3.1] risk-capped-formal-buy-guard=enabled", flush=True)
    return risk_capped.core.main(argv)


def main(argv: list[str] | None = None) -> int:
    original = legacy.risk_capped.main
    legacy.risk_capped.main = _guarded_risk_capped_main
    try:
        return legacy.main(argv)
    finally:
        legacy.risk_capped.main = original


if __name__ == "__main__":
    raise SystemExit(main())
