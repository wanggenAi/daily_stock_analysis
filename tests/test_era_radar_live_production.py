import json

from src.era_radar.live_production import run_live_production
from src.era_radar.live_world_bank import INDICATORS, WorldBankChinaStructuralCollector


AS_OF = "2026-08-30T10:00:10Z"


def wb_payload(_code):
    rows = [{"date": str(year), "value": 10.0 + i} for i, year in enumerate(range(2018, 2026))]
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


def test_world_bank_forecast_row_is_excluded_from_observed_truth():
    def fetcher(_url):
        rows = [{"date": str(year), "value": float(year - 2000)} for year in range(2018, 2026)]
        rows.insert(0, {"date": "2027", "value": 9999.0, "obs_status": "F"})
        return [{"page": 1}, rows]

    collector = WorldBankChinaStructuralCollector(fetcher=fetcher, clock=lambda: "2026-08-30T10:00:00Z")
    rows = list(collector.collect(AS_OF))
    assert len(rows) == len(INDICATORS)
    assert all(":2025:" in item.evidence_id for item in rows)
    assert all(item.observed_at.startswith("2025-") for item in rows)


def test_digital_structural_driver_joins_digital_infrastructure_topic():
    internet = next(item for item in INDICATORS if item.code == "IT.NET.USER.ZS")
    assert internet.trend_id == "digital_infrastructure"


def test_live_production_persists_only_after_complete_success(tmp_path, monkeypatch):
    monkeypatch.setattr("src.era_radar.live_production.iso_now", lambda: AS_OF)
    collector = WorldBankChinaStructuralCollector(fetcher=lambda _url: wb_payload("x"), clock=lambda: "2026-08-30T10:00:00Z")
    result = run_live_production([collector], output_dir=tmp_path)
    assert result["status"] == "PERSISTED"
    assert result["formal_trading_authority"] is False
    assert json.loads((tmp_path / "latest.json").read_text())["no_auto_trade"] is True
    assert len(list((tmp_path / "evidence").glob("*.json"))) == 1


def test_unchanged_refetch_is_no_change_and_does_not_churn_state(tmp_path, monkeypatch):
    monkeypatch.setattr("src.era_radar.live_production.iso_now", lambda: AS_OF)
    first_collector = WorldBankChinaStructuralCollector(fetcher=lambda _url: wb_payload("x"), clock=lambda: "2026-08-30T10:00:00Z")
    first = run_live_production([first_collector], output_dir=tmp_path)
    before = (tmp_path / "latest.json").read_text()

    second_collector = WorldBankChinaStructuralCollector(fetcher=lambda _url: wb_payload("x"), clock=lambda: "2026-08-30T10:00:09Z")
    second = run_live_production([second_collector], output_dir=tmp_path)
    assert first["status"] == "PERSISTED"
    assert second["status"] == "NO_CHANGE"
    assert (tmp_path / "latest.json").read_text() == before
    assert len(list((tmp_path / "history").glob("*.json"))) == 1


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
