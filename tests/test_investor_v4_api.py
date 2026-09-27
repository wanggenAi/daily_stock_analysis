"""V4 read-only API routing and no-cache contract."""
import json

from api.v1.endpoints import investor_v4
from api.v1.router import router


def test_investor_v4_is_registered_under_existing_versioned_api():
    paths = {route.path for route in router.routes}
    assert "/investor-v4/latest" in paths


def test_route_returns_no_cache_and_dated_non_actionable_payload(monkeypatch):
    monkeypatch.setattr(investor_v4, "latest_report", lambda: {
        "status": "AVAILABLE_DATED_READ_ONLY",
        "delivery": "LOCAL_DATED_ONLY",
        "hand_off": {
            "market_session_as_of": "2026-09-24",
            "formal_buy_now": [], "holdings": [],
            "feeds": {"market_eod": {"status": "STALE_OR_UNVERIFIED"}},
        },
        "opening_decision_ready": False,
        "execution_allowed": False,
        "warnings": ["LIVE_GITHUB_MAIN_NOT_CONFIGURED"],
    })
    response = investor_v4.get_latest_v4_report()
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    result = json.loads(response.body)
    assert result["hand_off"]["market_session_as_of"] == "2026-09-24"
    assert result["execution_allowed"] is False
    assert result["hand_off"]["formal_buy_now"] == []
