"""Illustrative toy-road stop-line test. NOT calibrated collision detection."""
from collections import deque
import json
import math
from pathlib import Path


def load_road_region(path, require_quad=False):
    """Reject degenerate/crossing polygons before computing a homography."""
    road = json.loads(Path(path).read_text(encoding="utf-8"))
    points, crop = road["polygon"], road["crop"]
    if (not isinstance(points, list) or len(points) < 3
            or (require_quad and len(points) != 4)
            or any(not isinstance(p, list) or len(p) != 2 for p in points)
            or not isinstance(crop, list) or len(crop) != 4):
        raise ValueError("Invalid road polygon or crop")
    values = crop + [v for p in points for v in p]
    if (any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values)
            or crop[0] >= crop[2] or crop[1] >= crop[3]):
        raise ValueError("Road coordinates must be normalized and crop nonempty")
    crosses = []
    for a, b, c in zip(points, points[1:] + points[:1], points[2:] + points[:2]):
        crosses.append((b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0]))
    if not (all(v > 1e-6 for v in crosses) or all(v < -1e-6 for v in crosses)):
        raise ValueError("Road corners must be distinct, ordered and strictly convex")
    for field, default in (("length_m", .30), ("width_m", .20)):
        value = road.get(field, default)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError("Road dimensions must be finite and positive")
        road[field] = float(value)
    return road


class StopLineDemo:
    def __init__(self):
        self.samples = deque(maxlen=30)
        self.track_id = None

    def update(self, track_id, distance_m, now, usable=True):
        unknown = dict(command="R", distance_cm=None, approach_cm_s=None,
                       time_to_line_s=None, reason="unknown")
        valid = (type(now) in (int, float) and math.isfinite(now)
                 and type(distance_m) in (int, float) and math.isfinite(distance_m))
        if (not usable or track_id is None or not valid
                or (self.samples and now <= self.samples[-1][0])):
            self.samples.clear()
            self.track_id = None
            return unknown
        if track_id != self.track_id or (self.samples and now - self.samples[-1][0] > 0.8):
            self.samples.clear()
            self.track_id = track_id
        self.samples.append((now, distance_m))
        while len(self.samples) > 1 and now - self.samples[0][0] > 0.8:
            self.samples.popleft()
        dt = now - self.samples[0][0]
        speed = max(0., (self.samples[0][1] - distance_m) / dt) if dt >= 0.35 else None
        ttc = max(0., distance_m) / speed if speed is not None and speed > 0.01 else None
        danger = distance_m <= 0.03 or (ttc is not None and ttc <= 2.)
        reason = "near_line" if danger else "warming_up" if speed is None else "clear"
        # Bench-only: rebuilding a track far from the line is not a line alert.
        # Missing detection / unusable camera still takes the unknown R branch.
        return dict(command="R" if danger else "G",
                    distance_cm=round(distance_m * 100, 1),
                    approach_cm_s=None if speed is None else round(speed * 100, 1),
                    time_to_line_s=None if ttc is None else round(ttc, 2), reason=reason)
