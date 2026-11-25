import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "charge_history"))
from charge_history_backend import STATUS_BROKEN, STATUS_BUSY, STATUS_FREE, HistoryDatabase


class EndingSoonTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.database = HistoryDatabase(Path(directory.name) / "test.db")
        self.addCleanup(self.database.close)

    def record(self, station_id, *outlets, snapshot="2026-01-01T08:00:00.000+00:00"):
        self.database.record_station_snapshot(
            f"Station {station_id}", station_id,
            [
                {"outletNo": f"{station_id}-{serial}", "serial": serial,
                 "status": status, "used_min": minutes}
                for serial, (status, minutes) in enumerate(outlets, 1)
            ],
            snapshot,
        )

    def test_counts_only_busy_outlets_strictly_over_threshold(self):
        self.record(1, (STATUS_BUSY, 464), (STATUS_BUSY, 465))
        self.record(2, (STATUS_BUSY, 466), (STATUS_BUSY, 480), (STATUS_BUSY, None),
                    (STATUS_FREE, 500), (STATUS_BROKEN, 500))
        self.record(3)

        stations = self.database.list_stations()
        self.assertEqual({row["station_id"]: row["ending_soon_count"] for row in stations},
                         {1: 0, 2: 2, 3: 0})
        self.assertEqual(self.database.list_stations(search="Station 2"), [stations[1]])

    def test_uses_latest_sample_and_excludes_ended_sessions(self):
        self.record(1, (STATUS_BUSY, 465))
        self.assertEqual(self.database.list_stations()[0]["ending_soon_count"], 0)

        self.record(1, (STATUS_BUSY, 465), snapshot="2026-01-01T08:00:00.001+00:00")
        self.assertEqual(self.database.list_stations()[0]["ending_soon_count"], 1)

        self.record(1, (STATUS_FREE, None), snapshot="2026-01-01T08:01:00.000+00:00")
        self.assertEqual(self.database.list_stations()[0]["ending_soon_count"], 0)


if __name__ == "__main__":
    unittest.main()
