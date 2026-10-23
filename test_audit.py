"""Acceptance audit: main vision loop with fake devices; no physical I/O."""
import contextlib
import io
import types
import unittest
import numpy as np  # Import before patch.dict restores sys.modules between cases.
from unittest.mock import patch

import vision_serial_bridge as bridge
from engine import evaluate
from test_engine import BASE, FakeSerial


class VisionLoopAudit(unittest.TestCase):
    def run_loop(self, boxes, times, camera_ok=True):
        frame = np.zeros((800, 1000, 3), dtype=np.uint8)
        class Capture:
            def __init__(self):
                self.reads = 0
            def set(self, *args): pass
            def release(self): pass
            def read(self):
                self.reads += 1
                if self.reads > 1:
                    raise KeyboardInterrupt
                return camera_ok, frame
        capture = Capture()
        cv2 = types.SimpleNamespace(VideoCapture=lambda _: capture, CAP_PROP_FRAME_WIDTH=1,
            CAP_PROP_FRAME_HEIGHT=2, CAP_PROP_BUFFERSIZE=3, destroyAllWindows=lambda: None)
        model = types.SimpleNamespace(track=lambda *a, **k: [types.SimpleNamespace(boxes=boxes, plot=lambda: frame)], predictor=None)
        class Link:
            def __init__(self, *args): self.error = "offline"
            def tick(self, *args): return False
            def close(self): pass
        args = types.SimpleNamespace(port="TEST_ONLY", baud=115200, camera=0,
            model="mock.pt", width=1000, height=800, camera_height_m=2,
            focal_px=800, horizon_y=400, scene_scale=1, confidence=.4, no_display=True,
            road_region=None, tabletop_test=False, preview_only=False, presence_test=False)
        modules = {'cv2': cv2, 'serial': types.SimpleNamespace(),
                   'ultralytics': types.SimpleNamespace(YOLO=lambda _: model)}
        with patch.dict('sys.modules', modules), patch.object(bridge, 'arguments', return_value=args), \
             patch.object(bridge, 'SerialLink', Link), patch.object(bridge.time, 'monotonic', side_effect=times), \
             patch.object(bridge.time, 'sleep'), patch.object(bridge, 'write_status') as status:
            bridge.main()
        return [call.kwargs for call in status.call_args_list]

    @staticmethod
    def truck():
        value = lambda v: types.SimpleNamespace(item=lambda: v)
        coords = types.SimpleNamespace(cpu=lambda: types.SimpleNamespace(tolist=lambda: [400,160,600,560]))
        return types.SimpleNamespace(xyxy=[coords], cls=[value(7)], id=[value(1)], conf=[value(.9)])

    def test_empty_frame_requests_red(self):
        states = self.run_loop([], [1, 1.1, 2, 2.1])
        live = next(s for s in states if 'event' in s)
        self.assertEqual(live['command'], 'R')
        self.assertFalse(live['measurement_valid'])
        self.assertFalse(states[-1]['edge_active'])

    def test_bridge_live_loop_and_stale_frame(self):
        for times, command, active in [([1, 1.1, 2, 2.1], 'B', True), ([1, 3, 4, 5], 'R', False)]:
            with self.subTest(command=command):
                states = self.run_loop([self.truck()], times)
                live = next(s for s in states if 'event' in s)
                self.assertEqual(live['outcome']['level'], 'BRIDGE_CRITICAL')
                self.assertEqual(live['command'], command)
                self.assertEqual(live['edge_active'], active)
                self.assertEqual(states[-1]['command'], 'R')

    def test_camera_failure_requests_red(self):
        states = self.run_loop([], [1, 1.1, 2, 2.1], camera_ok=False)
        failure = next(s for s in states if s.get('message') == 'Camera unavailable; retrying')
        self.assertEqual(failure['command'], 'R')
        self.assertFalse(failure['edge_active'])


class RuleAndProtocolAudit(unittest.TestCase):
    def test_safety_priority_grid(self):
        for truck_height in (0, 4.5, 4.50001, 5):
            for distance in (0, .1, 3, 10, 100):
                for speed in (0, 5, 30, 100):
                    event = {**BASE, 'truck_present': True, 'truck_height_m': truck_height,
                             'pedestrian_present': True, 'ambulance_present': True,
                             'distance_m': distance, 'relative_speed_kmh': speed}
                    result = evaluate(event)
                    self.assertTrue(0 <= result['risk'] <= 100)
                    if truck_height > 4.5:
                        self.assertEqual(result['action'], 'LOCAL_BRIDGE_ALERT')
                    elif speed > 0 and distance / (speed / 3.6) <= 2:
                        self.assertEqual(result['action'], 'LOCAL_RED_ALERT')

    def test_old_ack_cannot_confirm_changed_command(self):
        link = bridge.SerialLink(types.SimpleNamespace(Serial=FakeSerial, SerialException=OSError), 'TEST_ONLY', 115200)
        self.assertFalse(link.tick(b'G', 10))
        self.assertFalse(link.tick(b'B', 10.3))
        self.assertTrue(link.tick(b'B', 10.6))

    def test_partial_write_disconnects(self):
        class Partial(FakeSerial):
            def write(self, data): return 0
        link = bridge.SerialLink(types.SimpleNamespace(Serial=Partial, SerialException=OSError), 'TEST_ONLY', 115200)
        self.assertFalse(link.tick(b'G', 10))
        self.assertIsNone(link.handle)


if __name__ == '__main__':
    unittest.main()
