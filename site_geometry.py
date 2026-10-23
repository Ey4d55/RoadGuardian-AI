"""Optional, site-calibrated ground zones for a fixed level camera.

Rectangles use PHYSICAL metres (X,Z), before scene scaling. Nothing is
enabled without a supplied configuration; example values are not calibration.
"""
import json
import math
from pathlib import Path


def load_site(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    result = {}
    for name in ("waiting", "crosswalk", "approach"):
        rect = data[name]
        if (not isinstance(rect, list) or len(rect) != 4 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in rect)):
            raise ValueError(f"Invalid {name} rectangle")
        x1, z1, x2, z2 = rect
        if not (x1 < x2 and 0 < z1 < z2):
            raise ValueError(f"Invalid {name} bounds")
        result[name] = tuple(rect)
    a, c = result["approach"], result["crosswalk"]
    if max(a[0], c[0]) >= min(a[2], c[2]) or not (a[1] >= c[3] or a[3] <= c[1]):
        raise ValueError("Approach must align with, and lie outside, crosswalk in Z")
    return result


def inside(point, rect):
    x, z = point[:2]
    return rect[0] <= x <= rect[2] and rect[1] <= z <= rect[3]


def approach_distance(point, site):
    """Distance to the entry boundary, only in the configured straight lane."""
    if not inside(point, site["approach"]):
        return None
    x, z = point[:2]
    cross = site["crosswalk"]
    if not cross[0] <= x <= cross[2]:
        return None
    return max(cross[1] - z, z - cross[3], 0.0)
