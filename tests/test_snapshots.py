import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "charge_history"))
from charger_api import fetch_outlet_duration, fetch_station
from charge_history_backend import (
    STATUS_BROKEN, STATUS_BUSY, STATUS_FREE, SnapshotCollector, SnapshotStore, StationSnapshot,
)


STAMP = "2026-01-01T08:00:00.000+00:00"


def ports(*outlets):
    return [
        {"serial": serial, "status": status, "used_min": minutes}
        for serial, (status, minutes) in enumerate(outlets, 1)
    ]


class SnapshotStoreTest(unittest.TestCase):
    def setUp(self):
        self.store = SnapshotStore({"Campus A": 1, "Campus B": 2, "Campus C": 3})

    def test_initial_state_is_unknown_not_zero(self):
        rows = self.store.list_stations()
        self.assertEqual([row["sample_status"] for row in rows], ["waiting"] * 3)
        self.assertTrue(all(row["free_count"] is None for row in rows))
        self.assertEqual(self.store.list_outlets(1)["outlets"], [])
        self.assertIsNone(self.store.list_outlets(99))

    def test_counts_outlets_by_status(self):
        self.store.publish({
            1: StationSnapshot.from_outlets(STAMP, ports((STATUS_BUSY, 30))),
            2: StationSnapshot.from_outlets(STAMP, ports(
                (STATUS_BUSY, 60), (STATUS_BUSY, None), (STATUS_FREE, None), (STATUS_BROKEN, None),
            )),
            3: StationSnapshot.from_outlets(STAMP, []),
        }, set())
        rows = self.store.list_stations()
        self.assertEqual([row["busy_count"] for row in rows], [1, 2, 0])
        self.assertEqual([row["broken_count"] for row in rows], [0, 1, 0])
        self.assertEqual([row["free_count"] for row in rows], [0, 1, 0])
        self.assertEqual(rows[2]["sample_status"], "ready")
        self.assertEqual(rows[2]["outlet_count"], 0)
        self.assertEqual(self.store.list_stations(" CAMPUS B "), [rows[1]])

    def test_failed_round_preserves_timestamp_but_hides_old_status(self):
        before = StationSnapshot.from_outlets(STAMP, ports((STATUS_FREE, None)))
        self.store.publish({1: before}, {2, 3})
        self.store.publish({}, {1, 2, 3})
        first, second, _ = self.store.list_stations()
        self.assertEqual((first["sample_status"], first["last_seen_at"], first["free_count"]), ("stale", STAMP, None))
        self.assertEqual((second["sample_status"], second["last_seen_at"]), ("unavailable", None))
        self.assertEqual(self.store.list_outlets(1)["outlets"], [])
        self.assertEqual(self.store.totals()["ready_station_count"], 0)

        updated = StationSnapshot.from_outlets("2026-01-01T08:01:00.000+00:00", ports((STATUS_BUSY, 75)))
        self.store.publish({1: updated}, {2, 3})
        row = self.store.list_outlets(1)
        self.assertEqual(row["sample_status"], "ready")
        self.assertEqual(row["last_seen_at"], updated.sampled_at)
        self.assertEqual(row["outlets"], ports((STATUS_BUSY, 75)))
        self.assertEqual(self.store.list_stations()[0]["busy_count"], 1)

    def test_collector_distinguishes_empty_station_and_upstream_failure(self):
        station_map = {"Campus A": 1, "Campus B": 2}
        store = SnapshotStore(station_map)
        collector = SnapshotCollector(station_map, store, sample_interval_s=60, station_workers=2)
        with patch("charge_history_backend.fetch_station", side_effect=lambda sid: [] if sid == 1 else None) as fetch:
            result = collector.run_once()
            self.assertEqual(fetch.call_count, 2)
        self.assertEqual((result["status"], result["station_ok"], result["station_failed"]), ("partial", 1, 1))
        self.assertEqual([row["sample_status"] for row in store.list_stations()], ["ready", "unavailable"])


class UpstreamSnapshotTest(unittest.TestCase):
    @patch("charger_api.requests.get")
    def test_missing_duration_is_unknown_not_zero(self, request):
        request.side_effect = [
            Mock(status_code=200, **{"json.return_value": {"code": 1, "data": {}}}),
            Mock(status_code=200, **{"json.return_value": {"code": 1, "data": {"usedmin": "0"}}}),
        ]
        self.assertIsNone(fetch_outlet_duration("sample"))
        self.assertEqual(fetch_outlet_duration("sample"), 0)

    @patch("charger_api.fetch_outlet_duration", return_value=75)
    @patch("charger_api.requests.get")
    def test_only_requests_duration_for_busy_outlets(self, request, duration):
        request.return_value = Mock(status_code=200, **{"json.return_value": {"code": 1, "data": [
            {"outletSerialNo": "1", "outletNo": "free", "currentChargingRecordId": 1},
            {"outletSerialNo": "2", "outletNo": "busy", "currentChargingRecordId": 2},
        ]}})
        self.assertEqual(fetch_station(5), ports((STATUS_FREE, None), (STATUS_BUSY, 75)))
        duration.assert_called_once_with("busy")


if __name__ == "__main__":
    unittest.main()
