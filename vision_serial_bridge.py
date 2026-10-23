# Install: python -m pip install "opencv-python>=4.10,<5" "ultralytics>=8.3,<9" "pyserial>=3.5,<4" "lap>=0.5.12,<1"
"""Local YOLOv8n -> RoadGuardian rules -> ESP32 LED demonstrator.

Requires a fixed, LEVEL camera, flat ground, square pixels, negligible lens
distortion, visible object feet/roof, and calibration at the actual resolution.
Z = camera_height * focal_px / (bottom_y - horizon_y)
X = (box_center_x - image_center_x) * Z / focal_px
height = box_height_px * Z / focal_px
This uses ground geometry, NOT an assumed truck height (a circular estimate).
The whole camera view must cover only the relevant approach/crossing.
YOLO COCO cannot identify ambulances; live ambulance_present stays False.
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import math
import os
from pathlib import Path
import time

from engine import evaluate, number
from site_geometry import load_site, inside, approach_distance
from tabletop_demo import StopLineDemo, load_road_region

LOG = logging.getLogger("roadguardian")
STATUS_PATH = Path(__file__).with_name("edge_status.json")
ACTION_BYTES = {"LOCAL_RED_ALERT": b"R", "LOCAL_BRIDGE_ALERT": b"B",
                "PRIORITY_SIMULATION": b"E", "NORMAL": b"G", "MONITOR": b"G",
                "LOCAL_AMBER_ALERT": b"R"}  # Four-command protocol: warning -> red.
RANK = {"NORMAL": 0, "EMERGENCY_PRIORITY": 1, "WARNING": 2,
        "CRITICAL": 3, "BRIDGE_CRITICAL": 4}


def estimate_geometry(box, width, height, camera_height, focal, horizon):
    """Return (ground X, ground Z, object height), or None if unmeasurable."""
    x1, y1, x2, y2 = map(float, box)
    if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
        return None
    if x1 <= 2 or y1 <= 2 or x2 >= width - 2 or y2 >= height - 2:
        return None  # Clipped boxes must not be reported as safe heights.
    if x2 <= x1 or y2 <= y1 or y2 - horizon < 10:
        return None
    z = camera_height * focal / (y2 - horizon)
    return ((0.5 * (x1 + x2) - width / 2) * z / focal,
            z, (y2 - y1) * z / focal)


class PairMotion:
    """Estimate pedestrian/vehicle closing speed from persistent track pairs."""
    def __init__(self):
        self.previous = {}

    def update(self, key, distance, now):
        previous = self.previous.get(key)
        if previous is None or now - previous[0] > 1.5:
            self.previous[key] = (now, distance, None)
            return None
        dt = now - previous[0]
        if dt < 0.1:
            return previous[2]
        raw = (previous[1] - distance) / dt
        # Implausible jumps (ID swap/noisy geometry) invalidate speed.
        speed = None if abs(raw) > 60 else (
            raw if previous[2] is None else 0.5 * raw + 0.5 * previous[2])
        self.previous[key] = (now, distance, speed)
        return speed

    def expire(self, now):
        self.previous = {k: v for k, v in self.previous.items() if now - v[0] <= 1.5}


def scene_event(objects, motion, now, scene_scale=1.0, site=None):
    """Convert measured geometry to equivalent metres, then evaluate the scene.

    At 1:20, a measured 0.25m truck becomes 5m. Scale BOTH ground coordinates
    and height; closing speed scales consistently and TTC remains unchanged.
    The caller's physical measurements are never mutated.
    """
    scene_scale = number(scene_scale, "scene_scale")
    if scene_scale <= 0:
        raise ValueError("scene_scale must be > 0")
    if site is not None:
        site = {name: tuple(v * scene_scale for v in rect) for name, rect in site.items()}
    objects = [{**obj, "geometry": tuple(v * scene_scale for v in obj["geometry"])
                if obj["geometry"] is not None else None} for obj in objects]
    base = dict(distance_m=999.0, relative_speed_kmh=0.0, pedestrian_present=False,
                ambulance_present=False, cloud_online=False, model_confidence=0.0,
                truck_present=False, truck_height_m=0.0, scene_scale=scene_scale,
                truck_height_physical_m=None, height_source="camera_estimate",
                site_configured=site is not None, time_to_crosswalk_s=None,
                crosswalk_occupied=False)
    trucks = [o for o in objects if o["class_id"] == 7]
    measured = [o for o in trucks if o["geometry"] is not None]
    if measured:
        tallest = max(measured, key=lambda o: o["geometry"][2])
        base.update(truck_present=True, truck_height_m=tallest["geometry"][2],
                    truck_height_physical_m=tallest["geometry"][2] / scene_scale,
                    model_confidence=tallest["confidence"])
    # No detections is absence of evidence, not confirmation of a clear road.
    uncertain = not objects or any(o["geometry"] is None for o in objects)
    people = [o for o in objects if o["class_id"] == 0]
    vehicles = [o for o in objects if o["class_id"] in (2, 7)]
    motion.expire(now)
    # Compute vehicle-to-crosswalk motion once per frame, independent of the
    # number of pedestrians. Rectangles assume a straight approach along Z.
    vehicle_motion = {}
    if site is not None:
        people = [p for p in people if p["geometry"] is not None and
                  (inside(p["geometry"], site["waiting"]) or inside(p["geometry"], site["crosswalk"]))]
        for vehicle in vehicles:
            geometry = vehicle["geometry"]
            if geometry is None:
                continue
            occupied = inside(geometry, site["crosswalk"])
            distance = 0.0 if occupied else approach_distance(geometry, site)
            if distance is None:
                continue
            speed = motion.update(("crosswalk", vehicle["id"]), distance, now) if vehicle["id"] is not None else None
            vehicle_motion[id(vehicle)] = (distance, speed, occupied)
    # Preserve pedestrian presence even when no vehicle/pair can be evaluated.
    base["pedestrian_present"] = bool(people)
    if people and not measured:
        base["model_confidence"] = max(p["confidence"] for p in people)
    candidates = [(base, evaluate(base))]
    for person in people:
        for vehicle in vehicles:
            if person["geometry"] is None or vehicle["geometry"] is None:
                continue
            occupied = False
            if site is not None:
                measured_motion = vehicle_motion.get(id(vehicle))
                if measured_motion is None:
                    continue
                distance, speed, occupied = measured_motion
            else:
                distance = math.dist(person["geometry"][:2], vehicle["geometry"][:2])
                speed = None
                if person["id"] is not None and vehicle["id"] is not None:
                    speed = motion.update((person["id"], vehicle["id"]), distance, now)
            uncertain |= speed is None
            event = {**base, "distance_m": distance, "relative_speed_kmh": max(0, speed or 0) * 3.6,
                     "pedestrian_present": True,
                     "crosswalk_occupied": occupied,
                     "time_to_crosswalk_s": distance / speed if site is not None and speed is not None and speed > 0 else None,
                     "model_confidence": min(person["confidence"], vehicle["confidence"])}
            candidates.append((event, evaluate(event)))
    event, outcome = max(candidates, key=lambda pair: (RANK[pair[1]["level"]], pair[1]["risk"]))
    return event, outcome, uncertain


class AlertHold:
    """Escalate immediately; hold alerts briefly through detection flicker."""
    def __init__(self):
        self.command, self.until = b"G", 0.0

    def update(self, command, now):
        rank = {b"G": 0, b"E": 1, b"R": 2, b"B": 3}
        if rank[command] >= rank[self.command] or now >= self.until:
            self.command = command
            self.until = now + 1.0
        return self.command


class SerialLink:
    """Bounded I/O, periodic retry, heartbeat, and firmware acknowledgement."""
    def __init__(self, serial_module, port, baud):
        self.api, self.port, self.baud = serial_module, port, baud
        self.handle = None
        self.retry_at = self.opened_at = self.sent_at = 0.0
        self.ack_at = float("-inf")
        self.last_sent = None
        self.last_ack = None
        self.error = "Not connected"

    def close(self):
        if self.handle is not None:
            try:
                self.handle.close()
            except (self.api.SerialException, OSError):
                pass
        self.handle = None
        self.ack_at = float("-inf")
        self.last_sent = self.last_ack = None

    def tick(self, command, now):
        try:
            if self.handle is None and now >= self.retry_at:
                self.retry_at = now + 3.0
                self.handle = self.api.Serial(self.port, self.baud, timeout=0, write_timeout=0.1)
                self.handle.reset_input_buffer()
                self.opened_at = now
                self.error = "Waiting for firmware acknowledgement"
            if self.handle is None:
                return False
            received = self.handle.read(min(self.handle.in_waiting, 256))
            for byte in received:
                ack = bytes([byte])
                if ack == self.last_sent:
                    self.ack_at, self.last_ack = now, ack
                    self.error = ""
            if now - self.sent_at >= 0.2 or command != self.last_sent:
                if self.handle.write(command) != 1:
                    raise self.api.SerialException("Incomplete command write")
                self.last_sent, self.sent_at = command, now
            if now - self.opened_at > 5 and now - self.ack_at > 2:
                raise self.api.SerialException("Firmware acknowledgement timed out")
            return now - self.ack_at <= 1.5 and self.last_ack == command
        except (self.api.SerialException, OSError) as exc:
            self.error = str(exc)
            LOG.warning("ESP32 disconnected: %s; retrying", exc)
            self.close()
            self.retry_at = now + 3.0
            return False


_last_frame_publish = 0.0


def write_status(path, frame=None, **state):
    """Publish one coherent local frame/status snapshot, at most 5 previews/s.

    The latest frame is overwritten; no video archive is created. Control and
    inference keep running independently of this display publication limit.
    """
    global _last_frame_publish
    now = time.monotonic()
    if frame is not None:
        if now - _last_frame_publish < 0.2:
            return
        import cv2
        height, width = frame.shape[:2]
        if width > 960:
            frame = cv2.resize(frame, (960, round(height * 960 / width)))
        state["frame_dark"] = float(frame.mean()) < 2.0
        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
        if ok:
            state["frame_jpeg"] = base64.b64encode(jpeg).decode("ascii")
            state["frame_width"] = frame.shape[1]
            state["frame_height"] = frame.shape[0]
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps({"updated_at": time.time(), **state}, allow_nan=False), encoding="utf-8")
        # Windows readers may briefly hold the previous snapshot open.
        for attempt in range(3):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 2:
                    raise
                time.sleep(0.01)
        if frame is not None:
            _last_frame_publish = now
    except OSError as exc:
        LOG.warning("Cannot publish dashboard status: %s", exc)


def presence_test_command(person_count, usable_frame, now, last_person_at):
    """Bench test only: retain red for one second after the last detection."""
    if person_count > 0:
        last_person_at = now
    command = b"R" if not usable_frame or now - last_person_at < 1.0 else b"G"
    return command, last_person_at


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--camera-height-m", type=float)
    parser.add_argument("--focal-px", type=float)
    parser.add_argument("--horizon-y", type=float)
    parser.add_argument("--preview-only", action="store_true",
                        help="Uncalibrated detection/connection check; always sends R, no physical estimates")
    parser.add_argument("--presence-test", action="store_true",
                        help="Bench test only: person -> R, absent -> G; no collision assessment")
    parser.add_argument("--road-region", type=Path, help="Preview-only normalized road polygon and inference crop")
    parser.add_argument("--tabletop-test", action="store_true", help="Illustrative road/stop-line test using the supplied region dimensions")
    parser.add_argument("--scene-scale", type=float, default=1.0,
                        help="Real/model length ratio: 20 for 1:20; camera height stays PHYSICAL metres")
    parser.add_argument("--confidence", type=float, default=0.4)
    parser.add_argument("--no-display", action="store_true")
    parser.add_argument("--site-config", type=Path,
                        help="Calibrated waiting/crosswalk/approach rectangles in physical ground metres")
    args = parser.parse_args()
    if args.presence_test or args.tabletop_test:
        args.preview_only = True
    if args.tabletop_test and (not args.road_region or args.presence_test):
        parser.error("Tabletop test requires --road-region and cannot combine with --presence-test")
    if args.road_region and not args.preview_only:
        parser.error("Road overlay is a preview tool, not calibrated site geometry")
    if args.camera < 0:
        parser.error("Camera index must be nonnegative")
    if args.preview_only:
        if min(args.width, args.height, args.baud) <= 0 or not 0 < args.confidence <= 1:
            parser.error("Invalid preview parameters")
        return args
    if any(v is None for v in (args.camera_height_m, args.focal_px, args.horizon_y)):
        parser.error("Calibration is required unless --preview-only is selected")
    values = (args.camera_height_m, args.focal_px, args.horizon_y, args.confidence, args.scene_scale)
    if (not all(math.isfinite(v) for v in values) or args.camera_height_m <= 0
            or args.focal_px <= 0 or not 0 <= args.horizon_y < args.height
            or args.scene_scale <= 0 or not 0 < args.confidence <= 1
            or min(args.width, args.height, args.baud) <= 0):
        parser.error("Invalid calibration, image size, baud rate, or confidence")
    return args


def main():
    args = arguments()
    site_path = getattr(args, "site_config", None)
    site = load_site(site_path) if site_path else None
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Lazy imports keep pure geometry/protocol logic testable without a GPU/camera.
    import cv2
    import numpy as np
    import serial
    from ultralytics import YOLO

    road = load_road_region(args.road_region, args.tabletop_test) if args.road_region else None
    road_length = float(road.get("length_m", .30)) if road else .30
    road_width = float(road.get("width_m", .20)) if road else .20
    if not all(math.isfinite(v) and v > 0 for v in (road_length, road_width)):
        raise ValueError("Invalid road dimensions")
    stop_z = road_length * (22 / 30)
    tabletop = StopLineDemo()

    link = SerialLink(serial, args.port, args.baud)
    capture = None
    write_status(STATUS_PATH, edge_active=False, esp32_connected=False, message="Loading YOLOv8n")
    try:
        model = YOLO(args.model)
        motion, hold = PairMotion(), AlertHold()
        failures = 0
        last_person_at = float("-inf")
        while True:
            if capture is None:
                capture = cv2.VideoCapture(args.camera)
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
                capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                motion = PairMotion()
                tabletop = StopLineDemo()
                for tracker in getattr(model.predictor, "trackers", []):
                    tracker.reset()
            started = time.monotonic()
            ok, frame = capture.read()
            if not ok:
                connected = link.tick(b"R", time.monotonic())
                write_status(STATUS_PATH, edge_active=False, esp32_connected=connected,
                             message="Camera unavailable; retrying", command="R")
                capture.release()
                capture = None
                time.sleep(0.5)
                continue
            try:
                height, width = frame.shape[:2]
                if args.preview_only:
                    x0, y0, x1, y1 = (0, 0, width, height)
                    if road:
                        x0, y0, x1, y1 = [int(v * size) for v, size in zip(road["crop"], (width, height, width, height))]
                    input_frame = frame[y0:y1, x0:x1]
                    if args.tabletop_test:
                        result = model.track(input_frame, persist=True, tracker="bytetrack.yaml",
                                             classes=[2, 7], conf=args.confidence, verbose=False)[0]
                    else:
                        result = model.predict(input_frame, classes=[0, 2, 7], conf=args.confidence,
                                               verbose=False)[0]
                    counts = {name: 0 for name in ("person", "car", "truck")}
                    for box in result.boxes:
                        counts[result.names[int(box.cls[0].item())]] += 1
                    now = time.monotonic()
                    usable_frame = now - started <= 1.5 and float(input_frame.mean()) >= 2.0
                    command = b"R"
                    if args.presence_test:
                        command, last_person_at = presence_test_command(
                            counts["person"], usable_frame, now, last_person_at)
                    demo_state = None
                    geometry_ambiguous = False
                    line_pixels = None
                    if args.tabletop_test:
                        corners = np.float32([[x * width, y * height] for x, y in road["polygon"]])
                        ground = np.float32([[0, 0], [road_width, 0], [road_width, road_length], [0, road_length]])
                        transform = cv2.getPerspectiveTransform(corners, ground)
                        inverse = cv2.getPerspectiveTransform(ground, corners)
                        line_pixels = cv2.perspectiveTransform(np.float32([[[0, stop_z], [road_width, stop_z]]]), inverse)[0]
                        vehicles = []
                        for box in result.boxes:
                            if int(box.cls[0].item()) not in (2, 7):
                                continue
                            left, top, right, bottom = box.xyxy[0].cpu().tolist()
                            if box.id is None or left <= 2 or top <= 2 or right >= x1-x0-2 or bottom >= y1-y0-2:
                                geometry_ambiguous = True
                                continue
                            foot = np.float32([[[(left + right) / 2 + x0, bottom + y0]]])
                            gx, gz = cv2.perspectiveTransform(foot, transform)[0][0]
                            if 0 <= gx <= road_width and 0 <= gz <= road_length:
                                vehicles.append((stop_z - float(gz), int(box.id[0].item())))
                        distance, vehicle_id = min(vehicles) if vehicles else (None, None)
                        demo_state = tabletop.update(vehicle_id, distance, now, usable_frame and not geometry_ambiguous)
                        command = demo_state["command"].encode("ascii")
                    connected = link.tick(command, now)
                    preview = frame.copy()
                    preview[y0:y1, x0:x1] = result.plot()
                    if road:
                        points = np.array([[int(x * width), int(y * height)] for x, y in road["polygon"]], dtype=np.int32)
                        cv2.polylines(preview, [points], True, (80, 220, 240), 3)
                        cv2.putText(preview, "ROAD / DEMO REGION", (points[0][0], max(20, points[0][1]-12)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (80, 220, 240), 2)
                    if line_pixels is not None:
                        a, b = [tuple(map(int, p)) for p in line_pixels]
                        cv2.line(preview, a, b, (40, 80, 255), 3)
                        cv2.putText(preview, "VIRTUAL STOP", a, cv2.FONT_HERSHEY_SIMPLEX, .5, (40, 80, 255), 2)
                    write_status(STATUS_PATH, frame=preview, edge_active=False, camera_connected=True,
                                 preview_only=True, esp32_connected=connected,
                                 serial_error=link.error, command=command.decode(), measurement_valid=False,
                                 presence_test=args.presence_test, usable_frame=usable_frame,
                                 road_region=bool(road),
                                 tabletop_test=args.tabletop_test, tabletop=demo_state,
                                 road_length_cm=road_length * 100, road_width_cm=road_width * 100,
                                 geometry_ambiguous=geometry_ambiguous,
                                 counts=counts, message="Uncalibrated preview; precautionary red",
                                 inference_ms=round(1000 * (time.monotonic() - started), 1))
                    failures = 0
                    if not args.no_display:
                        cv2.putText(preview, f"SETUP ONLY | LED {command.decode()} | ESP32 {'ACK' if connected else 'OFFLINE'}",
                                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                        cv2.imshow("RoadGuardian AI - Q to quit", preview)
                        if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                            break
                    continue
                if (width, height) != (args.width, args.height):
                    raise ValueError(f"Camera returned {width}x{height}; recalibrate for this resolution")
                result = model.track(frame, persist=True, tracker="bytetrack.yaml",
                                     classes=[0, 2, 7], conf=args.confidence, verbose=False)[0]
                objects = []
                for box in result.boxes:
                    xyxy = box.xyxy[0].cpu().tolist()
                    objects.append(dict(class_id=int(box.cls[0].item()),
                                        id=int(box.id[0].item()) if box.id is not None else None,
                                        confidence=float(box.conf[0].item()),
                                        geometry=estimate_geometry(xyxy, width, height,
                                            args.camera_height_m, args.focal_px, args.horizon_y)))
                now = time.monotonic()
                event, outcome, uncertain = scene_event(objects, motion, started, args.scene_scale, site)
                stale = now - started > 1.5
                command = ACTION_BYTES.get(outcome["action"], b"R")
                if stale or (uncertain and command != b"B"):
                    command = b"R"
                command = hold.update(command, now)
                connected = link.tick(command, now)
                message = ("Frame too old" if stale else "No detections; road state unknown" if not objects
                           else "Geometry/speed unavailable" if uncertain
                           else "Live estimates from calibrated ground plane")
                preview = result.plot()
                write_status(STATUS_PATH, frame=preview if not stale else None,
                             edge_active=not stale, esp32_connected=connected,
                             message=message, serial_error=link.error, event=event, outcome=outcome,
                             command=command.decode(), measurement_valid=not uncertain and not stale,
                             detections=len(objects), inference_ms=round(1000 * (now - started), 1))
                failures = 0
                if not args.no_display:
                    cv2.putText(preview, f"{outcome['level']} | LED {command.decode()} | ESP32 {'ACK' if connected else 'OFFLINE'}",
                                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                    cv2.imshow("RoadGuardian AI - Q to quit", preview)
                    if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                        break
            except Exception as exc:
                failures += 1
                LOG.exception("Frame processing failed")
                connected = link.tick(b"R", time.monotonic())
                write_status(STATUS_PATH, edge_active=False, esp32_connected=connected,
                             message=str(exc), command="R")
                if failures >= 5:
                    raise RuntimeError("Five consecutive processing failures") from exc
                time.sleep(0.1)
    except KeyboardInterrupt:
        LOG.info("Stopped by operator")
    finally:
        link.tick(b"R", time.monotonic())
        link.close()
        if capture is not None:
            capture.release()
        cv2.destroyAllWindows()
        write_status(STATUS_PATH, edge_active=False, esp32_connected=False,
                     message="Vision stopped", command="R")


if __name__ == "__main__":
    main()
