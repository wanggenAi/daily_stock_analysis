import json
from urllib.error import HTTPError

import pytest

import src.era_radar.live_world_bank as live_world_bank


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_world_bank_transient_timeout_retries_and_recovers(monkeypatch):
    calls = []
    payload = [{"page": 1}, [{"date": "2025", "value": 1.0}]]

    def fake_urlopen(_request, timeout):
        calls.append(timeout)
        if len(calls) == 1:
            raise TimeoutError("read timed out")
        return FakeResponse(payload)

    monkeypatch.setattr(live_world_bank, "urlopen", fake_urlopen)
    result = live_world_bank._fetch_json(
        f"{live_world_bank.API_ROOT}/country/CHN",
        attempts=2,
        backoff_seconds=0,
    )
    assert result == payload
    assert calls == [20.0, 20.0]


def test_world_bank_transient_http_503_retries_and_recovers(monkeypatch):
    calls = []
    payload = [{"page": 1}, []]
    url = f"{live_world_bank.API_ROOT}/country/CHN"

    def fake_urlopen(_request, timeout):
        calls.append(timeout)
        if len(calls) == 1:
            raise HTTPError(url, 503, "service unavailable", None, None)
        return FakeResponse(payload)

    monkeypatch.setattr(live_world_bank, "urlopen", fake_urlopen)
    result = live_world_bank._fetch_json(url, attempts=3, backoff_seconds=0)
    assert result == payload
    assert len(calls) == 2


def test_world_bank_permanent_http_404_fails_without_retry(monkeypatch):
    calls = []
    url = f"{live_world_bank.API_ROOT}/country/CHN"

    def fake_urlopen(_request, timeout):
        calls.append(timeout)
        raise HTTPError(url, 404, "not found", None, None)

    monkeypatch.setattr(live_world_bank, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="HTTP 404"):
        live_world_bank._fetch_json(url, attempts=3, backoff_seconds=0)
    assert len(calls) == 1


def test_world_bank_retry_exhaustion_still_fails_closed(monkeypatch):
    calls = []
    url = f"{live_world_bank.API_ROOT}/country/CHN"

    def fake_urlopen(_request, timeout):
        calls.append(timeout)
        raise TimeoutError("read timed out")

    monkeypatch.setattr(live_world_bank, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="after 3 attempts"):
        live_world_bank._fetch_json(url, attempts=3, backoff_seconds=0)
    assert len(calls) == 3
