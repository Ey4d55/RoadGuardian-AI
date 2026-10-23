"""Hardware-free regression tests: python -m unittest -v test_engine"""
import csv
import math
from pathlib import Path
import tempfile
import types
import unittest

from engine import as_bool, evaluate
from vision_serial_bridge import (ACTION_BYTES, AlertHold, PairMotion, SerialLink,
                                  estimate_geometry, scene_event, write_status)

BASE = dict(distance_m=40, relative_speed_kmh=30, pedestrian_present=0,
            ambulance_present=0, cloud_online=1, model_confidence=0.95)


class EngineTests(unittest.TestCase):
    def test_legacy(self):
        self.assertEqual(evaluate(BASE)["level"], "NORMAL")
        self.assertEqual(evaluate({**BASE, "distance_m": 3, "pedestrian_present": 1})["level"], "CRITICAL")
        self.assertEqual(evaluate({**BASE, "ambulance_present": 1})["level"], "EMERGENCY_PRIORITY")
        self.assertTrue(evaluate({**BASE, "cloud_online": 0})["edge_active"])

    def test_bridge_boundary(self):
        for height, expected in [(4.49, "NORMAL"), (4.5, "NORMAL"), (4.5001, "BRIDGE_CRITICAL")]:
            with self.subTest(height=height):
                self.assertEqual(evaluate({**BASE, "truck_present": True, "truck_height_m": height})["level"], expected)
        self.assertEqual(evaluate({**BASE, "truck_present": False, "truck_height_m": 9})["level"], "NORMAL")

    def test_bridge_overrides_every_other_rule(self):
        result = evaluate({**BASE, "pedestrian_present": True, "ambulance_present": True,
                           "distance_m": 0.1, "truck_present": True, "truck_height_m": 5})
        self.assertEqual((result["level"], result["action"]), ("BRIDGE_CRITICAL", "LOCAL_BRIDGE_ALERT"))
        self.assertEqual(evaluate({"truck_present": True, "truck_height_m": 5})["action"], "LOCAL_BRIDGE_ALERT")

    def test_invalid_inputs(self):
        for value in [float("nan"), float("inf"), -1]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                evaluate({**BASE, "truck_present": True, "truck_height_m": value})
        with self.assertRaises(ValueError):
            evaluate(BASE, warning_ttc=2, critical_ttc=2)
        with self.assertRaises(ValueError):
            evaluate({**BASE, "model_confidence": 1.1})
        self.assertFalse(as_bool("False"))
        self.assertTrue(as_bool("1"))

    def test_csv_compatibility(self):
        with Path(__file__).with_name("events.csv").open() as source:
            rows = list(csv.DictReader(source))
        self.assertEqual(len(rows), 300)
        for row in rows:
            self.assertIn(evaluate(row)["action"], ACTION_BYTES)


class VisionTests(unittest.TestCase):
    def test_no_detections_is_unknown_not_confirmed_clear(self):
        event, outcome, uncertain = scene_event([], PairMotion(), 1)
        self.assertTrue(uncertain)
        self.assertEqual(outcome["level"], "NORMAL")  # Rules vs. sensor certainty.

    def test_model_scale_bridge_thresholds(self):
        for physical, equivalent, level in [(0.20, 4.0, "NORMAL"), (0.225, 4.5, "NORMAL"),
                                             (0.25, 5.0, "BRIDGE_CRITICAL")]:
            with self.subTest(physical=physical):
                objects = [dict(class_id=7, id=1, confidence=0.9, geometry=(0, 1, physical))]
                event, outcome, uncertain = scene_event(objects, PairMotion(), 1, 20)
                self.assertAlmostEqual(event["truck_height_m"], equivalent)
                self.assertAlmostEqual(event["truck_height_physical_m"], physical)
                self.assertEqual(outcome["level"], level)
                self.assertEqual(objects[0]["geometry"], (0, 1, physical))
                self.assertFalse(uncertain)

    def test_scale_preserves_ttc_and_scales_speed(self):
        outcomes = []
        for scale in (1, 20):
            objects = [dict(class_id=0, id=1, confidence=0.9, geometry=(0, 1, 0.06)),
                       dict(class_id=2, id=2, confidence=0.9, geometry=(0, 2, 0.08))]
            motion = PairMotion()
            scene_event(objects, motion, 1, scale)
            objects[1]["geometry"] = (0, 1.8, 0.08)
            event, outcome, _ = scene_event(objects, motion, 1.5, scale)
            outcomes.append(outcome)
            self.assertAlmostEqual(event["distance_m"], 0.8 * scale)
            self.assertAlmostEqual(event["relative_speed_kmh"], 1.44 * scale)
        self.assertEqual(outcomes[0]["ttc_s"], outcomes[1]["ttc_s"])

    def test_invalid_scale(self):
        for scale in (0, -20, float("inf"), float("nan")):
            with self.subTest(scale=scale), self.assertRaises(ValueError):
                scene_event([], PairMotion(), 0, scale)

    def test_geometry_is_not_assumed_truck_height(self):
        # Camera 2m above road, f=800px, horizon=400. Truck: 400px tall, foot y=560.
        x, z, height = estimate_geometry((400, 160, 600, 560), 1000, 800, 2, 800, 400)
        self.assertAlmostEqual(x, 0)
        self.assertAlmostEqual(z, 10)
        self.assertAlmostEqual(height, 5)
        self.assertIsNone(estimate_geometry((0, 160, 600, 560), 1000, 800, 2, 800, 400))
        self.assertIsNone(estimate_geometry((400, 160, 600, 400), 1000, 800, 2, 800, 400))

    def test_pair_speed_and_dropout(self):
        motion = PairMotion()
        self.assertIsNone(motion.update((1, 2), 10, 1))
        self.assertAlmostEqual(motion.update((1, 2), 8, 1.5), 4)
        self.assertIsNone(motion.update((1, 2), 7, 4))
        motion.expire(6)
        self.assertFalse(motion.previous)

    def test_tallest_truck_wins(self):
        objects = [dict(class_id=7, id=i, confidence=0.9, geometry=(0, 10, height))
                   for i, height in enumerate([3, 5, 4])]
        event, outcome, uncertain = scene_event(objects, PairMotion(), 1)
        self.assertEqual(event["truck_height_m"], 5)
        self.assertEqual(outcome["level"], "BRIDGE_CRITICAL")
        self.assertFalse(uncertain)

    def test_pair_distance_not_distance_to_camera(self):
        motion = PairMotion()
        objects = [dict(class_id=0, id=1, confidence=0.9, geometry=(0, 20, 1.7)),
                   dict(class_id=2, id=2, confidence=0.9, geometry=(0, 30, 1.5))]
        self.assertTrue(scene_event(objects, motion, 1)[2])
        objects[1]["geometry"] = (0, 28, 1.5)
        event, outcome, uncertain = scene_event(objects, motion, 1.5)
        self.assertEqual(event["distance_m"], 8)
        self.assertAlmostEqual(event["relative_speed_kmh"], 14.4)
        self.assertEqual(outcome["level"], "CRITICAL")
        self.assertFalse(uncertain)

    def test_alert_hold(self):
        hold = AlertHold()
        self.assertEqual(hold.update(b"B", 1), b"B")
        self.assertEqual(hold.update(b"R", 1.5), b"B")
        self.assertEqual(hold.update(b"R", 2.1), b"R")
        self.assertEqual(hold.update(b"G", 3.2), b"G")

    def test_atomic_snapshot(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            path = Path(temp) / "edge_status.json"
            write_status(path, edge_active=True)
            self.assertIn('"edge_active": true', path.read_text())
            self.assertFalse(path.with_suffix(".tmp").exists())


class FakeSerial:
    def __init__(self, *args, **kwargs):
        self.buffer = b""
        self.fail = False
        self.writes = []

    def reset_input_buffer(self):
        self.buffer = b""

    @property
    def in_waiting(self):
        return len(self.buffer)

    def read(self, count):
        data, self.buffer = self.buffer[:count], self.buffer[count:]
        return data

    def write(self, data):
        if self.fail:
            raise OSError("unplugged")
        self.writes.append(data)
        self.buffer += data
        return 1

    def close(self):
        pass


class SerialTests(unittest.TestCase):
    def test_ack_disconnect_and_reconnect(self):
        api = types.SimpleNamespace(Serial=FakeSerial, SerialException=OSError)
        link = SerialLink(api, "COM3", 115200)
        self.assertFalse(link.tick(b"B", 10))
        self.assertTrue(link.tick(b"B", 10.3))
        self.assertEqual(link.handle.writes, [b"B", b"B"])
        link.handle.fail = True
        self.assertFalse(link.tick(b"B", 10.6))
        self.assertIsNone(link.handle)
        self.assertFalse(link.tick(b"B", 11))
        self.assertFalse(link.tick(b"R", 14))
        self.assertTrue(link.tick(b"R", 14.3))

    def test_open_port_without_firmware_is_not_connected(self):
        class NoAck(FakeSerial):
            def read(self, count):
                self.buffer = b""
                return b""
        link = SerialLink(types.SimpleNamespace(Serial=NoAck, SerialException=OSError), "COM3", 115200)
        self.assertFalse(link.tick(b"G", 10))
        self.assertFalse(link.tick(b"G", 16))
        self.assertIsNone(link.handle)


if __name__ == "__main__":
    unittest.main()
