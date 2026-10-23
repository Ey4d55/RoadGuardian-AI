"""Regression coverage for pedestrian-first workflow, zones and evidence."""
import json
from pathlib import Path
import tempfile
import unittest

from engine import evaluate
from safety_workflow import CrossingDemo, stopping_distance, validation_metrics
from site_geometry import load_site
from vision_serial_bridge import scene_event, PairMotion
from test_engine import BASE


class CrossingTests(unittest.TestCase):
    def test_no_direct_or_automatic_walk(self):
        demo = CrossingDemo()
        self.assertEqual(demo.step("confirm", 1).phase, "IDLE")
        demo = demo.step("request", 1)
        self.assertEqual(demo.step("confirm", 3.9).phase, "REQUESTED")
        self.assertEqual(demo.step("tick", 5).phase, "REQUESTED")
        self.assertEqual(demo.step("confirm", 5).phase, "WALK_DEMO")

    def test_timeout_and_late_confirmation_fail_closed(self):
        demo = CrossingDemo().step("request", 1)
        self.assertEqual(demo.step("confirm", 16).phase, "FAULT")
        self.assertEqual(demo.step("tick", 16).step("confirm", 17).phase, "FAULT")

    def test_clearance_and_fault(self):
        demo = CrossingDemo().step("request", 1).step("confirm", 5)
        self.assertEqual(demo.step("release", 6).phase, "WALK_DEMO")
        demo = demo.step("finish", 6)
        self.assertEqual(demo.step("release", 9).phase, "CLEARANCE")
        self.assertEqual(demo.step("release", 10).phase, "IDLE")
        for phase in ("IDLE", "REQUESTED", "WALK_DEMO", "CLEARANCE"):
            fault = CrossingDemo(phase, 0).step("fault", 1)
            self.assertEqual(fault.step("request", 2).phase, "FAULT")
            self.assertEqual(fault.step("reset", 3).phase, "IDLE")

    def test_stopping_example_and_invalid_values(self):
        self.assertAlmostEqual(stopping_distance(60, 2.5, 3, 30), 117.96296, places=4)
        for value in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                stopping_distance(60, 2.5, value, 30)

    def test_evidence_denominators_and_exclusions(self):
        rows = [dict(expected=True, observed=True, alert_ms=120),
                dict(expected=True, observed=False), dict(expected=False, observed=False),
                dict(expected=False, observed=True), dict(expected=True, observed=None)]
        result = validation_metrics(rows)
        self.assertEqual(result["n"], 4)
        self.assertEqual(result["excluded"], 1)
        for key in ("accuracy", "recall", "false_alarm_rate"):
            self.assertEqual(result[key], .5)
        self.assertEqual(result["mean_alert_ms"], 120)
        self.assertEqual(result["timed_trials"], 1)
        for key in ("accuracy", "recall", "false_alarm_rate", "mean_alert_ms"):
            self.assertIsNone(validation_metrics([])[key])
        self.assertIsNone(validation_metrics(rows[:1])["false_alarm_rate"])


class SiteTests(unittest.TestCase):
    def setUp(self):
        self.site = dict(waiting=(-.45, .8, -.2, 1.0),
                         crosswalk=(-.2, .8, .2, 1.0), approach=(-.2, 1, .2, 2.5))

    def objects(self, person_x=-.3, vehicle_z=2.0):
        return [dict(class_id=0, id=1, confidence=.9, geometry=(person_x, .9, .06)),
                dict(class_id=2, id=2, confidence=.9, geometry=(0, vehicle_z, .08))]

    def test_approach_time_scale_and_not_pair_distance(self):
        for scale in (1, 20):
            motion = PairMotion()
            self.assertTrue(scene_event(self.objects(), motion, 1, scale, self.site)[2])
            event, result, uncertain = scene_event(self.objects(vehicle_z=1.8), motion, 1.5, scale, self.site)
            self.assertAlmostEqual(event["distance_m"], .8 * scale)
            self.assertAlmostEqual(event["time_to_crosswalk_s"], 2)
            self.assertTrue(event["site_configured"])
            self.assertFalse(uncertain)

    def test_irrelevant_pedestrian_and_receding_vehicle(self):
        event, result, _ = scene_event(self.objects(person_x=2), PairMotion(), 1, 20, self.site)
        self.assertFalse(event["pedestrian_present"])
        motion = PairMotion()
        scene_event(self.objects(vehicle_z=1.8), motion, 1, 1, self.site)
        event, result, _ = scene_event(self.objects(vehicle_z=2), motion, 1.5, 1, self.site)
        self.assertIsNone(event["time_to_crosswalk_s"])
        self.assertEqual(event["relative_speed_kmh"], 0)

    def test_waiting_person_without_vehicle_remains_visible(self):
        event, result, uncertain = scene_event(self.objects()[:1], PairMotion(), 1, 20, self.site)
        self.assertTrue(event["pedestrian_present"])
        self.assertIsNone(event["time_to_crosswalk_s"])
        self.assertEqual(result["level"], "NORMAL")
        self.assertFalse(uncertain)

    def test_vehicle_in_crosswalk_and_bridge_priority(self):
        event, result, _ = scene_event(self.objects(vehicle_z=.9), PairMotion(), 1, 20, self.site)
        self.assertTrue(event["crosswalk_occupied"])
        self.assertEqual(result["level"], "CRITICAL")
        event.update(truck_present=True, truck_height_m=5)
        self.assertEqual(evaluate(event)["level"], "BRIDGE_CRITICAL")
        self.assertEqual(evaluate({**BASE, "crosswalk_occupied": True})["level"], "NORMAL")

    def test_invalid_site_never_silently_enables(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            path = Path(tmp) / "site.json"
            path.write_text(json.dumps(self.site))
            self.assertEqual(load_site(path), self.site)
            for bounds in ([0, 0, 0, 1], [0, .9, 1, 1.2], [False, 1, .2, 2.5], [0, 1, float('nan'), 2]):
                path.write_text(json.dumps({**self.site, "approach": bounds}))
                with self.assertRaises(ValueError):
                    load_site(path)


if __name__ == "__main__":
    unittest.main()
