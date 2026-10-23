"""The animation must agree with engine decisions; no hardware I/O here."""
import unittest
from engine import evaluate
from traffic_simulation import SCENARIOS, simulation_data, component_html


class AnimationTests(unittest.TestCase):
    def test_every_frame_uses_actual_engine(self):
        for scenario in SCENARIOS:
            frames = simulation_data(scenario)["frames"]
            self.assertEqual(len(frames), 181)
            for frame in frames:
                self.assertEqual(frame["outcome"], evaluate(frame["event"]))
                if frame["command"] in ("R", "B"):
                    self.assertIn(frame["outcome"]["level"], ("WARNING", "CRITICAL", "BRIDGE_CRITICAL"))

    def test_pedestrian_alert_stops_the_simulated_vehicle_then_resumes(self):
        frames = simulation_data("CHILD_CROSSING")["frames"]
        self.assertEqual(frames[0]["command"], "G")
        self.assertEqual(frames[30]["command"], "R")
        self.assertEqual(frames[90]["speed"], 0)
        self.assertGreater(frames[90]["event"]["distance_m"], 0)
        self.assertEqual(frames[90]["x"], frames[100]["x"])
        self.assertEqual(frames[130]["command"], "G")
        self.assertGreater(frames[150]["speed"], 0)

    def test_bridge_and_offline_do_not_cancel_safety(self):
        bridge = simulation_data("TRUCK_OVERHEIGHT")["frames"]
        self.assertEqual(bridge[30]["command"], "B")
        self.assertEqual(bridge[-1]["speed"], 0)
        offline = simulation_data("CLOUD_OFFLINE")["frames"]
        self.assertFalse(offline[40]["outcome"]["cloud_online"])
        self.assertEqual(offline[40]["command"], "R")

    def test_eco_comparison_and_controls_are_explicit(self):
        data = simulation_data("CHILD_CROSSING")
        self.assertGreater(data["eco_after"]["co2_kg"], 0)
        html = component_html("CHILD_CROSSING")
        self.assertNotIn("__SIM_DATA__", html)
        self.assertNotIn("__FONT_DATA__", html)
        self.assertIn("requestAnimationFrame", html)
        self.assertIn('id="ecoShape"', html)
        self.assertIn('id="roadGreen"', html)
        self.assertNotIn('id="roadWhite"', html)
        with self.assertRaises(ValueError):
            simulation_data("INVALID")

    def test_pedestrian_crosses_only_while_vehicle_stopped_and_red(self):
        for scenario in ("CHILD_CROSSING", "CLOUD_OFFLINE"):
            frames = simulation_data(scenario)["frames"]
            crossing = [f for f in frames if f["crossing_confirmed"]]
            self.assertTrue(crossing)
            for frame in crossing:
                self.assertEqual(frame["command"], "R")
                self.assertEqual(frame["speed"], 0)
                self.assertTrue(frame["pedestrian"])
            self.assertGreater(crossing[0]["pedestrian_y"], crossing[-1]["pedestrian_y"])
            for frame in frames:
                # The complete enlarged actor's bounds remain in the SVG.
                self.assertGreaterEqual(frame["pedestrian_y"] - 60 * 1.3, 0)
                self.assertLessEqual(frame["pedestrian_y"] + 58 * 1.3, 470)
            self.assertTrue(all(abs(b["pedestrian_y"]-a["pedestrian_y"]) < 10
                                for a, b in zip(frames, frames[1:])))

    def test_eco_uses_same_timeline_and_accumulates_only_at_stop(self):
        data = simulation_data("CHILD_CROSSING")
        frames = data["frames"]
        self.assertEqual(frames[0]["eco_current"]["co2_kg"], 0)
        for previous, frame in zip(frames, frames[1:]):
            eco, before = frame["eco_current"], previous["eco_current"]
            self.assertGreaterEqual(eco["wait_s"], before["wait_s"])
            if frame["speed"] > 0:
                self.assertEqual(eco["co2_kg"], before["co2_kg"])
            self.assertAlmostEqual(eco["co2_kg"], eco["fuel_l"] * 2.348)
        self.assertEqual(data["eco_after"], frames[-1]["eco_current"])

    def test_congestion_has_six_cars_and_pedestrians_and_no_queue_overlap(self):
        data = simulation_data("CONGESTION")
        frames = data["frames"]
        self.assertEqual(data["assumptions"]["vehicles"], 6)
        self.assertEqual(len(frames[0]["vehicles"]), 6)
        self.assertEqual({v["direction"] for v in frames[0]["vehicles"]}, {-1, 1})
        self.assertEqual(frames[0]["pedestrian_opacity"], 1)
        crossing = [f for f in frames if f["crossing_confirmed"]]
        self.assertTrue(crossing)
        for frame in crossing:
            self.assertEqual(frame["command"], "R")
            self.assertTrue(all(v["speed"] == 0 for v in frame["vehicles"]))
        for frame in frames:
            for direction in (-1, 1):
                xs = sorted(v["x"] for v in frame["vehicles"] if v["direction"] == direction)
                self.assertTrue(all(b-a >= 124.9 for a, b in zip(xs, xs[1:])))
        self.assertTrue(all(v["speed"] > 0 for v in frames[-1]["vehicles"]))

    def test_congestion_eco_counts_each_visible_vehicle_wait(self):
        frames = simulation_data("CONGESTION")["frames"]
        for frame in frames:
            total = sum(v["waiting_s"] for v in frame["vehicles"])
            self.assertAlmostEqual(frame["eco_current"]["vehicle_seconds"], total)
            self.assertAlmostEqual(frame["eco_current"]["fuel_l"], total / 3600)
        self.assertGreater(frames[-1]["eco_current"]["co2_kg"], 0)

    def test_eco_matches_rendered_count_across_scenarios(self):
        from ecotwin import impact
        for scenario in SCENARIOS:
            data = simulation_data(scenario)
            count = 6 if scenario == "CONGESTION" else 1
            self.assertEqual(data["assumptions"]["vehicles"], count)
            self.assertEqual(data["eco_before"]["wait_s"], data["duration"])
            for frame in data["frames"]:
                eco = frame["eco_current"]
                self.assertEqual(eco["vehicles"], count)
                self.assertAlmostEqual(eco["co2_kg"],
                                       impact(1, eco["wait_s"])["co2_kg"] * count)
        single = simulation_data("CHILD_CROSSING")["frames"][90]["eco_current"]
        queue = simulation_data("CONGESTION")["frames"][90]["eco_current"]
        self.assertGreater(queue["co2_kg"], single["co2_kg"] * 5)

    def test_queue_approaches_briskly_and_stops_before_crosswalk(self):
        frames = simulation_data("CONGESTION")["frames"]
        for a, b in zip(frames[:30], frames[1:31]):
            for va, vb in zip(a["vehicles"], b["vehicles"]):
                self.assertAlmostEqual(abs(vb["x"] - va["x"]), 9, places=1)
        for frame in frames[40:120]:
            for vehicle in frame["vehicles"]:
                self.assertEqual(vehicle["speed"], 0)
                if vehicle["direction"] == -1:
                    self.assertGreaterEqual(vehicle["x"] - 55, 510)
                else:
                    self.assertLessEqual(vehicle["x"] + 55, 365)
