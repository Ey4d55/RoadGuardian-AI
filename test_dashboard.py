"""Streamlit AppTest coverage; requires Streamlit from requirements.txt."""
import json
import base64
import io
from pathlib import Path
import tempfile
import time
import unittest

from streamlit.testing.v1 import AppTest

from engine import evaluate
from roadguardian_views import BRIDGE_VIEW, RESPONSE_VIEW, VALIDATION_VIEW
from safety_workflow import CrossingDemo


class DashboardTests(unittest.TestCase):
    def test_bench_corrupt_counts_dimensions_and_commands_are_rejected(self):
        base = dict(edge_active=False, preview_only=True, camera_connected=True,
                    esp32_connected=True, counts={"car": 1}, command="G")
        cases = [{"counts": []}, {"counts": {"car": -1}}, {"road_width_cm": []},
                 {"tabletop_test": "yes"}, {"command": "B"},
                 {"tabletop_test": True, "tabletop": {"reason": "clear", "command": "R"}}]
        for change in cases:
            (self.root / "edge_status.json").write_text(json.dumps({**base, **change, "updated_at": time.time()}))
            app = self.app.run()
            app.radio(key="source").set_value("الرؤية الحية").run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.metric), 0)

    def test_invalid_jpeg_does_not_crash_monitor(self):
        (self.root / "edge_status.json").write_text(json.dumps({
            "updated_at": time.time(), "edge_active": False, "preview_only": True,
            "camera_connected": True, "esp32_connected": False,
            "frame_jpeg": base64.b64encode(b"\xff\xd8invalid").decode("ascii")
        }))
        app = self.app.run()
        app.radio(key="source").set_value("الرؤية الحية").run()
        self.assertFalse(app.exception)
        self.assertFalse(app.get("image"))
        self.assertTrue(any("بانتظار صورة" in x.value for x in app.info))

    def test_camera_frame_disappears_when_telemetry_is_stale(self):
        from PIL import Image
        buffer = io.BytesIO()
        Image.new("RGB", (32, 24), "navy").save(buffer, format="JPEG")
        state = {"updated_at": time.time(), "edge_active": False, "preview_only": True,
                 "camera_connected": True, "esp32_connected": True,
                 "frame_jpeg": base64.b64encode(buffer.getvalue()).decode("ascii")}
        status = self.root / "edge_status.json"
        status.write_text(json.dumps(state), encoding="utf-8")
        app = self.app.run()
        app.radio(key="source").set_value("الرؤية الحية").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("image")), 1)
        state["updated_at"] = time.time() - 10
        status.write_text(json.dumps(state), encoding="utf-8")
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("image")), 0)

    def test_uncalibrated_preview_has_counts_without_risk_estimates(self):
        (self.root / "edge_status.json").write_text(json.dumps({
            "updated_at": time.time(), "edge_active": False, "preview_only": True,
            "camera_connected": True, "esp32_connected": True,
            "measurement_valid": False, "command": "R",
            "counts": {"person": 1, "car": 0, "truck": 0},
        }), encoding="utf-8")
        app = self.app.run()
        app.radio(key="source").set_value("الرؤية الحية").run()
        self.assertFalse(app.exception)
        self.assertEqual([m.label for m in app.metric], ["أشخاص", "سيارات", "شاحنات"])
        self.assertTrue(any("احترازي" in w.value for w in app.warning))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = Path(__file__).with_name("dashboard.py").read_text(encoding="utf-8")
        source = source.replace("ROOT = Path(__file__).resolve().parent", f"ROOT = Path({str(self.root)!r})")
        assets = Path(__file__).resolve().parent / "assets"
        source = source.replace('ASSETS = Path(__file__).resolve().parent / "assets"', f"ASSETS = Path({str(assets)!r})")
        self.app = AppTest.from_string(source, default_timeout=15)

    def test_pedestrian_first_and_new_views(self):
        app = self.app.run()
        self.assertEqual(app.selectbox(key="scenario_picker").value, "CHILD_CROSSING")
        app.radio(key="view").set_value(BRIDGE_VIEW).run()
        self.assertFalse(app.exception)
        self.assertTrue(any("توقف" in e.value for e in app.error))
        app.checkbox(key="demo_route").uncheck().run()
        self.assertTrue(any("لا يوجد مسار" in e.value for e in app.warning))
        app.number_input(key="bridge_demo_height").set_value(4.0).run()
        self.assertFalse(app.error)
        app.radio(key="view").set_value(RESPONSE_VIEW).run()
        app.button(key="request_crossing").click().run()
        self.assertTrue(app.button(key="confirm_crossing").disabled)
        app.session_state["crossing_demo"] = CrossingDemo("REQUESTED", time.monotonic() - 4)
        app.run()
        app.button(key="confirm_crossing").click().run()
        self.assertEqual(app.session_state["crossing_demo"].phase, "WALK_DEMO")
        app.button(key="fault_crossing").click().run()
        self.assertEqual(app.session_state["crossing_demo"].phase, "FAULT")
        app.radio(key="source").set_value("الرؤية الحية").run()
        self.assertFalse(app.exception)
        self.assertFalse(any(b.key == "confirm_crossing" for b in app.button))

    def test_validation_no_fabricated_results_and_separate_samples(self):
        app = self.app.run()
        app.radio(key="view").set_value(VALIDATION_VIEW).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "0")
        self.assertEqual(app.metric[1].value, "—")
        app.text_input(key="trial_notes").set_value("rehearsal video A")
        app.selectbox(key="trial_observed").set_value("صدر إنذار الخطر الصحيح")
        next(b for b in app.button if b.label == "تسجيل التجربة").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "0")  # Physical filter excludes simulation.
        app.radio(key="trial_filter").set_value("محاكاة برمجية").run()
        self.assertEqual(app.metric[0].value, "1")
        self.assertEqual(app.metric[1].value, "100.0%")
        self.assertEqual(app.metric[2].value, "—")

    def test_all_scenarios_without_csv(self):
        app = self.app.run()
        self.assertFalse(app.exception)
        for scenario in ["NORMAL", "CHILD_CROSSING", "AMBULANCE", "CLOUD_OFFLINE", "CONGESTION", "TRUCK_OVERHEIGHT"]:
            app.selectbox[0].set_value(scenario).run()
            self.assertFalse(app.exception, scenario)
        self.assertEqual(len(app.get("iframe")), 1)
        content = app.get("iframe")[0].proto.srcdoc
        self.assertIn("BRIDGE_CRITICAL", content)
        self.assertIn("ECOTWIN / DECISION IMPACT", content)
        self.assertFalse(any(b.key == "next_event" for b in app.button))
        self.assertFalse(any("تفاصيل القياسات" in x.label for x in app.expander))

    def test_stale_status_is_not_connected(self):
        (self.root / "edge_status.json").write_text(json.dumps({
            "updated_at": time.time() - 30, "edge_active": True, "esp32_connected": True}))
        app = self.app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any("غير متصل" in item.proto.body for item in app.sidebar.get("html")))
        app.radio(key="source").set_value("الرؤية الحية").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 0)

    def test_live_bridge_event(self):
        event = dict(truck_present=True, truck_height_m=5, scene_scale=20,
                     truck_height_physical_m=0.25)
        (self.root / "edge_status.json").write_text(json.dumps({
            "updated_at": time.time(), "edge_active": True, "esp32_connected": True,
            "measurement_valid": True, "event": event, "outcome": evaluate(event),
            "command": "B", "inference_ms": 42, "detections": 1}))
        app = self.app.run()
        app.radio(key="source").set_value("الرؤية الحية").run()
        self.assertFalse(app.exception)
        self.assertIn("الشاحنة تتجاوز", app.error[0].value)
        self.assertEqual(app.metric[2].value, "5.00 m")
        self.assertTrue(any(item.proto.body.count('device-state online') == 2 for item in app.sidebar.get("html")))
        self.assertTrue(any("1:20" in item.value for item in app.info))
        self.assertTrue(any("25.0" in item.value for item in app.caption))

    def test_navigation_and_reset(self):
        app = self.app.run()
        animation = app.get("iframe")[0].proto.srcdoc
        self.assertIn('id="play"', animation)
        self.assertIn('id="reset"', animation)
        self.assertNotIn("SEETATHON", "".join(x.proto.body for x in app.get("html")))
        app.radio(key="view").set_value("مقارنة السيناريوهات").run()
        self.assertFalse(app.exception)
        self.assertTrue(any('analysis-row' in item.proto.body for item in app.get("html")))
        app.radio(key="view").set_value("دليل العرض").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.expander), 3)
        self.assertTrue(any("Terminal" in x.value for x in app.markdown))

    def test_ecotwin_safety_and_missing_live_data(self):
        app = self.app.run()
        app.radio(key="view").set_value("تحليل الأثر · EcoTwin").run()
        self.assertFalse(app.exception)
        for scenario in ["NORMAL", "CHILD_CROSSING", "AMBULANCE", "CLOUD_OFFLINE", "CONGESTION", "TRUCK_OVERHEIGHT"]:
            app.selectbox(key="eco_scenario").set_value(scenario).run()
            self.assertFalse(app.exception, scenario)
        self.assertIn("الجسر", app.error[0].value)
        app.number_input(key="eco_after").set_value(0).run()
        self.assertFalse(app.exception)
        self.assertIn("الجسر", app.error[0].value)
        app.radio(key="source").set_value("الرؤية الحية").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("بانتظار بيانات" in item.value for item in app.info))

    def test_corrupt_or_inconsistent_live_snapshots(self):
        event = dict(truck_present=True, truck_height_m=5)
        valid = dict(updated_at=time.time(), edge_active=True, esp32_connected=True,
                     measurement_valid=True, event=event, outcome=evaluate(event), command="B")
        cases = [[], {**valid, "outcome": {}}, {**valid, "event": {}},
                 {**valid, "edge_active": "False"}, {**valid, "command": "X"},
                 {**valid, "event": {**event, "scene_scale": "broken"}},
                 {**valid, "event": {**event, "pedestrian_present": "unknown"}},
                 {**valid, "event": {**event, "model_confidence": float('nan')}}]
        for snapshot in cases:
            with self.subTest(snapshot=snapshot):
                (self.root / "edge_status.json").write_text(json.dumps(snapshot))
                app = self.app.run()
                app.radio(key="source").set_value("الرؤية الحية").run()
                self.assertFalse(app.exception)
                self.assertEqual(len(app.metric), 0)
                app.radio(key="view").set_value("تحليل الأثر · EcoTwin").run()
                self.assertFalse(app.exception)

    def test_unknown_measurements_never_get_success_or_eco_chart(self):
        event = dict(distance_m=999, relative_speed_kmh=0, pedestrian_present=False,
                     ambulance_present=False, cloud_online=False, model_confidence=0)
        (self.root / "edge_status.json").write_text(json.dumps(dict(
            updated_at=time.time(), edge_active=True, esp32_connected=False,
            measurement_valid=False, event=event, outcome=evaluate(event), command="R", detections=0)))
        app = self.app.run()
        app.radio(key="source").set_value("الرؤية الحية").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.success), 0)
        self.assertTrue(any("لا يمكن تأكيد" in item.value for item in app.warning))
        app.radio(key="view").set_value("تحليل الأثر · EcoTwin").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get('iframe')), 0)


if __name__ == "__main__":
    unittest.main()
