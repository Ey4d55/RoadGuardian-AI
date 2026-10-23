"""Read-only environmental impact estimates; never issues or changes commands.

Idle-only model: vehicle count * mean waiting seconds / 3600 * L/hour.
Factors are explicit demo assumptions, not measurements or fleet calibration.
"""
import base64
import json
from pathlib import Path
from engine import BRIDGE_MAX_HEIGHT_M, number

ASSETS = Path(__file__).resolve().parent / "assets"


def impact(vehicle_count, wait_seconds, idle_lph=1.0, co2_kg_per_l=2.348):
    """Missing data stays unavailable. Reject invalid/nonfinite inputs."""
    if any(v is None for v in (vehicle_count, wait_seconds, idle_lph, co2_kg_per_l)):
        return None
    count = number(vehicle_count, "vehicle_count")
    if not count.is_integer():
        raise ValueError("vehicle_count must be an integer")
    wait = number(wait_seconds, "wait_seconds")
    rate = number(idle_lph, "idle_lph")
    factor = number(co2_kg_per_l, "co2_kg_per_l")
    fuel = count * wait / 3600 * rate
    return dict(vehicles=int(count), wait_s=wait, vehicle_seconds=count * wait,
                fuel_l=fuel, co2_kg=fuel * factor)


def payload(event, outcome, assumptions=None, simulated=True):
    """Compare assumed waiting only. Safety always comes from engine.evaluate.

    There is deliberately no safety/eco composite score and no eco->engine path.
    Live vision does not supply measured fleet idle time; no live estimate is made.
    """
    before = after = None
    if simulated and assumptions is not None:
        before = impact(assumptions["vehicles"], assumptions["before_s"],
                        assumptions["idle_lph"], assumptions["co2_kg_per_l"])
        after = impact(assumptions["vehicles"], assumptions["after_s"],
                       assumptions["idle_lph"], assumptions["co2_kg_per_l"])
    return dict(simulated=simulated, risk=float(outcome["risk"]), level=outcome["level"],
                action=outcome["action"], truck_height_m=outcome["truck_height_m"]
                if outcome["truck_present"] else None, bridge_limit=BRIDGE_MAX_HEIGHT_M,
                before=before, after=after,
                safety_locked=outcome["level"] in ("BRIDGE_CRITICAL", "CRITICAL", "WARNING"),
                assumptions=assumptions if simulated else None)


def component_html(data):
    """One self-contained offline component, with JSON safely embedded as data."""
    template = (ASSETS / "ecotwin.html").read_text(encoding="utf-8")
    font = base64.b64encode((ASSETS / "IBMPlexSansArabic-Regular.woff2").read_bytes()).decode()
    encoded = json.dumps(data, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c")
    return template.replace("__FONT_DATA__", font).replace("__ECO_DATA__", encoded)
