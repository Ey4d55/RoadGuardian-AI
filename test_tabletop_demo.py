import unittest
import json
import tempfile
from pathlib import Path
from tabletop_demo import StopLineDemo, load_road_region


class TabletopTests(unittest.TestCase):
    def test_invalid_measurements_and_repeated_time_fail_closed(self):
        for distance in (float("nan"), float("inf"), True, "0.1"):
            self.assertEqual(StopLineDemo().update(1, distance, 1)["command"], "R")
        demo = StopLineDemo()
        demo.update(1, .15, 1)
        self.assertEqual(demo.update(1, .14, 1)["reason"], "unknown")

    def test_road_region_rejects_crossing_or_degenerate_corners(self):
        valid = {"polygon": [[.2,.2],[.8,.2],[.8,.8],[.2,.8]], "crop": [0,0,1,1],
                 "length_m": .22, "width_m": .14}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "region.json"
            path.write_text(json.dumps(valid))
            self.assertEqual(load_road_region(path, True)["length_m"], .22)
            for changes in ({"polygon": [[0,0],[1,1],[0,1],[1,0]]},
                            {"polygon": [[0,0],[0,0],[1,1],[0,1]]},
                            {"length_m": float("nan")}, {"crop": [0,0,0,1]},
                            {"polygon": [[True,0],[1,0],[1,1],[0,1]]}):
                path.write_text(json.dumps({**valid, **changes}))
                with self.assertRaises(ValueError):
                    load_road_region(path, True)
    def test_track_change_far_away_is_not_a_stop_line_alert(self):
        demo = StopLineDemo()
        self.assertEqual(demo.update(1, .15, 1)["command"], "G")
        self.assertEqual(demo.update(2, .15, 1.5)["command"], "G")

    def test_missing_or_dark_frame_still_warns(self):
        demo = StopLineDemo()
        demo.update(1, .15, 1)
        self.assertEqual(demo.update(None, None, 1.2)["command"], "R")
        self.assertEqual(demo.update(1, .15, 1.3, False)["command"], "R")

    def test_approach_and_line_crossing(self):
        demo = StopLineDemo()
        demo.update(1, .15, 1)
        self.assertEqual(demo.update(1, .07, 1.5)["command"], "R")
        self.assertEqual(demo.update(2, -.01, 2)["command"], "R")
        self.assertEqual(demo.update(3, .15, 3)["command"], "G")
