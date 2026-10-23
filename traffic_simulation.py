"""Animated, deterministic demonstration driven by the actual rule engine.

No camera, serial or network access. The driver response and waiting times
are scenario assumptions, not measured improvements or a traffic controller.
"""
import base64
import json
from pathlib import Path

from engine import evaluate
from ecotwin import impact

ASSETS = Path(__file__).resolve().parent / "assets"
SCENARIOS = {"NORMAL", "CHILD_CROSSING", "AMBULANCE", "CLOUD_OFFLINE", "CONGESTION", "TRUCK_OVERHEIGHT"}


def _smooth(value):
    value = max(0., min(1., value))
    return value * value * (3 - 2 * value)


def _pedestrian_pose(t, present_in_scene, vehicles_stopped, command):
    crossing = present_in_scene and 6.4 <= t < 11.6 and vehicles_stopped and command == "R"
    phase = ("approaching" if t < 3 else "waiting" if t < 6.4 else
             "crossing" if crossing else "cleared" if t >= 11.6 else "waiting") if present_in_scene else "absent"
    y = (390 - 17 * _smooth(t / 3) if t < 3 else
         373 - 273 * _smooth((t - 6.4) / 5.2) if crossing or t >= 11.6 else 373)
    opacity = _smooth(t / .7) * (1 - _smooth((t - 13.5) / 1.5)) if present_in_scene else 0.
    return dict(pedestrian_y=y, pedestrian_opacity=opacity, pedestrian_phase=phase,
                crossing_confirmed=crossing)


def _congestion_data():
    """Six individual vehicles in two queues, with delayed stop/start response."""
    vehicles = [dict(id=i, lane=lane, rank=rank, direction=direction, x=float(x),
                     velocity=float(speed), waiting_s=0.)
                for i, (lane, rank, direction, x, speed) in enumerate([
                    (0, 0, -1, 930, 90), (0, 1, -1, 1070, 90), (0, 2, -1, 1210, 90),
                    (1, 0, 1, -15, 90), (1, 1, 1, -155, 90), (1, 2, 1, -295, 90)])]
    frames = []
    for index in range(181):
        t = index / 10
        lead = vehicles[0]
        event = dict(distance_m=max(0., (lead["x"] - 420) / 12),
                     relative_speed_kmh=lead["velocity"] / 12 * 3.6,
                     pedestrian_present=3 <= t < 12, ambulance_present=False,
                     cloud_online=True, model_confidence=1., truck_present=False, truck_height_m=0.)
        outcome = evaluate(event)
        command = "R" if outcome["action"] in ("LOCAL_RED_ALERT", "LOCAL_AMBER_ALERT") else "G"
        stopped = all(v["velocity"] == 0 for v in vehicles)
        pose = _pedestrian_pose(t, True, stopped, command)
        # Keep the waiting actor visible in the congestion scene's first view.
        if t < .7:
            pose["pedestrian_opacity"] = 1.
        if index > 0:
            for vehicle in vehicles:
                if vehicle["velocity"] == 0:
                    vehicle["waiting_s"] = round(vehicle["waiting_s"] + .1, 1)
        vehicle_seconds = round(sum(v["waiting_s"] for v in vehicles), 1)
        eco = impact(len(vehicles), vehicle_seconds / len(vehicles))
        phase = ("توقف الطابور في الاتجاهين · عبور المشاة المبرمج" if pose["crossing_confirmed"] else
                 "حماية المشاة · المركبات تتوقف تباعًا" if command == "R" and not stopped else
                 "طابور المركبات متوقف · المشاة ينتظرون بدء العبور" if command == "R" else
                 "اكتمل العبور · انفراج الطابور تدريجيًا" if t >= 12 else
                 "مركبات تقترب من الاتجاهين · تتشكل الطوابير عند الأحمر")
        frames.append(dict(t=t, x=round(lead["x"], 2), speed=round(lead["velocity"] / 12 * 3.6, 1),
                           pedestrian=event["pedestrian_present"], command=command, event=event,
                           outcome=outcome, phase=phase, **pose, eco_current=eco,
                           vehicles=[dict(id=v["id"], x=round(v["x"], 2),
                                          y=281 if v["lane"] == 0 else 203,
                                          direction=v["direction"], speed=round(v["velocity"] / 12 * 3.6, 1),
                                          waiting_s=v["waiting_s"]) for v in vehicles]))
        # Follow each queue's leader with a staggered response; maintain gaps.
        for vehicle in vehicles:
            rank, lane = vehicle["rank"], vehicle["lane"]
            should_wait = (command == "R" and t >= 3.2 + rank * .1) or (
                t >= 12 and t < 12 + rank * .35)
            target = 0. if should_wait else 90.
            velocity = vehicle["velocity"]
            velocity = max(target, velocity - 18.) if velocity > target else min(target, velocity + 12.)
            next_x = vehicle["x"] + vehicle["direction"] * velocity * .1
            if rank:
                ahead = vehicles[vehicle["id"] - 1]
                limit = ahead["x"] - vehicle["direction"] * 125
                if (vehicle["direction"] == -1 and next_x < limit) or (vehicle["direction"] == 1 and next_x > limit):
                    next_x, velocity = limit, 0.
            vehicle["x"], vehicle["velocity"] = next_x, velocity
    return dict(scenario="CONGESTION", frames=frames, duration=18, dt=.1,
                eco_before=impact(6, 18), eco_after=frames[-1]["eco_current"],
                assumptions=dict(vehicles=6, idle_lph=1., co2_kg_per_l=2.348,
                                 before_s=18, after_s=frames[-1]["eco_current"]["wait_s"],
                                 waiting_source="per_vehicle"))


def simulation_data(scenario):
    if scenario not in SCENARIOS:
        raise ValueError("Unknown animated scenario")
    if scenario == "CONGESTION":
        return _congestion_data()
    frames, x, velocity, first_alert, waiting_s = [], 930.0, 90.0, None, 0.0
    for index in range(181):
        t = index / 10
        pedestrian = scenario in ("CHILD_CROSSING", "CLOUD_OFFLINE") and 3 <= t < 12
        truck_detected = scenario == "TRUCK_OVERHEIGHT" and t >= 3
        emergency = scenario == "AMBULANCE" and t >= 3
        event = dict(distance_m=max(0., (x - 420) / 12), relative_speed_kmh=velocity / 12 * 3.6,
                     pedestrian_present=pedestrian, ambulance_present=emergency,
                     # The actor's presence is known in this synthetic scene;
                     # this is not a measured detector-confidence value.
                     cloud_online=scenario != "CLOUD_OFFLINE", model_confidence=1.,
                     truck_present=truck_detected, truck_height_m=5. if truck_detected else 0.)
        outcome = evaluate(event)
        command = {"LOCAL_BRIDGE_ALERT": "B", "LOCAL_RED_ALERT": "R",
                   "LOCAL_AMBER_ALERT": "R", "PRIORITY_SIMULATION": "E"}.get(outcome["action"], "G")
        warning = command in ("R", "B")
        if warning and first_alert is None:
            first_alert = t
        has_pedestrian = scenario in ("CHILD_CROSSING", "CLOUD_OFFLINE")
        pose = _pedestrian_pose(t, has_pedestrian, velocity == 0, command)
        crossing = pose["crossing_confirmed"]
        if index > 0 and velocity == 0:
            waiting_s = round(waiting_s + .1, 1)
        # Count only the single vehicle actually represented in this scene.
        current_eco = impact(1, waiting_s)
        phase = ("توقف المركبة مؤكد داخل السيناريو · عبور المشاة مبرمج" if crossing else
                 "تنبيه الجسر · توقف قبل نقطة الخطر" if command == "B" else
                 "تنبيه المشاة · المركبة تستجيب في المحاكاة" if command == "R" else
                 "أولوية إسعاف تجريبية" if command == "E" else
                 "اكتمل عبور المشاة في السيناريو · استئناف المركبة" if first_alert is not None else
                 "المركبة تقترب · النظام يراقب")
        frames.append(dict(t=t, x=round(x, 2), speed=round(velocity / 12 * 3.6, 1),
                           pedestrian=pedestrian, command=command, event=event,
                           outcome=outcome, phase=phase, **pose, eco_current=current_eco))
        # Assumed driver reaction (0.2 s) then braking. Never an actuator command.
        if warning and t >= first_alert + .2:
            velocity = max(0., velocity - 18.)
        elif not warning:
            target = 90.
            velocity = min(target, velocity + 12.)
        x -= velocity * .1
    before = 18  # Same full-window idle reference for every scenario.
    return dict(scenario=scenario, frames=frames, duration=18, dt=.1,
                eco_before=impact(1, before), eco_after=frames[-1]["eco_current"],
                assumptions=dict(vehicles=1, idle_lph=1., co2_kg_per_l=2.348,
                                 before_s=before, after_s=waiting_s, waiting_source="per_vehicle"))


def component_html(scenario):
    data = simulation_data(scenario)
    encoded = json.dumps(data, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c")
    font = base64.b64encode((ASSETS / "IBMPlexSansArabic-Regular.woff2").read_bytes()).decode("ascii")
    return ((ASSETS / "traffic_simulation.html").read_text(encoding="utf-8")
            .replace("__FONT_DATA__", font).replace("__SIM_DATA__", encoded))
