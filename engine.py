"""RoadGuardian AI decision engine; deterministic, hardware-independent rules."""
from math import isfinite
from typing import Any, Mapping

BRIDGE_MAX_HEIGHT_M = 4.5


def as_bool(value: Any) -> bool:
    """Accept real booleans and legacy CSV 0/1, never bool('False')."""
    if isinstance(value, str):
        value = value.strip().lower()
        if value in ("true", "1"):
            return True
        if value in ("false", "0"):
            return False
    elif isinstance(value, (bool, int, float)) and value in (0, 1):
        return bool(value)
    raise ValueError(f"Expected boolean or 0/1, got {value!r}")


def number(value: Any, name: str, minimum: float = 0.0) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number, not a boolean")
    result = float(value)
    if not isfinite(result) or result < minimum:
        raise ValueError(f"{name} must be finite and >= {minimum}")
    return result


def evaluate(event: Mapping[str, Any], warning_ttc: float = 4.0,
             critical_ttc: float = 2.0, warning_risk: float = 45.0,
             critical_risk: float = 75.0) -> dict[str, Any]:
    """Evaluate one observation; omitted truck fields preserve old CSV support.

    Bridge critical is resolved BEFORE pedestrian risk, ambulance priority,
    and validation of unrelated readings. Its risk=100 is a policy override,
    not a collision probability; TTC is not applicable (None).
    """
    truck = as_bool(event.get("truck_present", False))
    height = number(event["truck_height_m"], "truck_height_m") if truck else 0.0
    if truck and height > BRIDGE_MAX_HEIGHT_M:
        return dict(ttc_s=None, risk=100.0, level="BRIDGE_CRITICAL",
                    action="LOCAL_BRIDGE_ALERT", edge_active=True,
                    cloud_online=as_bool(event.get("cloud_online", False)),
                    truck_present=True, truck_height_m=height)

    warning_ttc = number(warning_ttc, "warning_ttc")
    critical_ttc = number(critical_ttc, "critical_ttc")
    warning_risk = number(warning_risk, "warning_risk")
    critical_risk = number(critical_risk, "critical_risk")
    if not (0 < critical_ttc < warning_ttc and 0 <= warning_risk < critical_risk <= 100):
        raise ValueError("Require 0 < critical_ttc < warning_ttc and 0 <= warning_risk < critical_risk <= 100")
    distance = number(event["distance_m"], "distance_m")
    speed = number(event["relative_speed_kmh"], "relative_speed_kmh")
    pedestrian = as_bool(event["pedestrian_present"])
    occupied = as_bool(event.get("crosswalk_occupied", False))
    ambulance = as_bool(event["ambulance_present"])
    confidence = number(event["model_confidence"], "model_confidence")
    if confidence > 1:
        raise ValueError("model_confidence must be <= 1")
    ttc = distance / (speed / 3.6) if speed > 0 else 999.0
    ttc_score = (1.0 if ttc <= critical_ttc else
                 max(0.0, min(1.0, (warning_ttc - ttc) / (warning_ttc - critical_ttc))))
    risk = round((35 * pedestrian + 40 * ttc_score + 15 * min(1.0, speed / 40)
                  + 10 * confidence) * (1 if pedestrian else 0.25), 1)
    if pedestrian and occupied:
        # Calibrated crosswalk occupied by a vehicle while pedestrians are
        # waiting/in the crossing. This is a warning policy, never a WALK grant.
        risk = max(risk, critical_risk)
        level, action = "CRITICAL", "LOCAL_RED_ALERT"
    elif pedestrian and (ttc <= critical_ttc or risk >= critical_risk):
        level, action = "CRITICAL", "LOCAL_RED_ALERT"
    elif pedestrian and (ttc <= warning_ttc or risk >= warning_risk):
        level, action = "WARNING", "LOCAL_AMBER_ALERT"
    elif ambulance:
        level, action = "EMERGENCY_PRIORITY", "PRIORITY_SIMULATION"
    else:
        level, action = "NORMAL", "MONITOR"
    return dict(ttc_s=round(ttc, 2), risk=risk, level=level, action=action,
                edge_active=True, cloud_online=as_bool(event.get("cloud_online", False)),
                truck_present=truck, truck_height_m=height)
