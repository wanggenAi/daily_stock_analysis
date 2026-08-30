import json

from src.era_radar.live_production import run_live_production
from src.era_radar.live_world_bank import INDICATORS, WorldBankChinaStructuralCollector


AS_OF = "2026-08-30T10:00:10Z"


def wb_payload(code):
    rows = [
        {"date": str(year), "value": 10.0 + i}
        for i, year in enumerate(range(2018, 2026))
    ]
    return [{"page": 1}, rows]


def test_world_bank_live_collector_is_deterministic_and_pit_safe():
    def fetcher(url):
        assert url.startswith("https://api.worldbank.org/v2/")
        return wb_payload(url)

    collector = WorldBankChinaStructuralCollector(fetcher=fetcher, clock=lambda: "2026-08-30T10:00:00Z")
    rows = list(collector.collect(AS_OF))
    assert len(rows) == len(INDICATORS)
    assert all(item.retrieved_at == "2026-08-30T10:00:00Z" for item in rows)
    assert all(item.source_id == "world_bank" for item in rows)
    assert {item.topic_keys[0] for item in rows} == {item.trend_id for item in INDICATORS}


def test_live_production_persists_only_after_complete_success(tmp_path, monkeypatch):
    monkeypatch.setattr("src.era_radar.live_production.iso_now", lambda: AS_OF)
    collector = WorldBankChinaStructuralCollector(fetcher=lambda _url: wb_payload("x"), clock=lambda: "2026-08-30T10:00:00Z")
    result = run_live_production([collector], output_dir=tmp_path)
    assert result["status"] == "PERSISTED"
    assert result["formal_trading_authority"] is False
    assert json.loads((tmp_path / "latest.json").read_text())["no_auto_trade"] is True
    assert len(list((tmp_path / "evidence").glob("*.json"))) == 1


def test_partial_collector_failure_never_mutates_durable_truth(tmp_path, monkeypatch):
    monkeypatch.setattr("src.era_radar.live_production.iso_now", lambda: AS_OF)
    good = WorldBankChinaStructuralCollector(fetcher=lambda _url: wb_payload("x"), clock=lambda: "2026-08-30T10:00:00Z")
    first = run_live_production([good], output_dir=tmp_path)
    before = (tmp_path / "latest.json").read_text()

    class Broken:
        def collect(self, _as_of):
            raise RuntimeError("source outage")
            yield  # pragma: no cover

    second = run_live_production([good, Broken()], output_dir=tmp_path)
    assert first["status"] == "PERSISTED"
    assert second["status"] == "NO_PUBLISH_PARTIAL_COLLECTION"
    assert (tmp_path / "latest.json").read_text() == before


def test_all_collectors_failed_does_not_create_state(tmp_path, monkeypatch):
    monkeypatch.setattr("src.era_radar.live_production.iso_now", lambda: AS_OF)

    class Broken:
        def collect(self, _as_of):
            raise TimeoutError("timeout")
            yield  # pragma: no cover

    result = run_live_production([Broken()], output_dir=tmp_path)
    assert result["status"] == "NO_PUBLISH_PARTIAL_COLLECTION"
    assert not (tmp_path / "latest.json").exists()
