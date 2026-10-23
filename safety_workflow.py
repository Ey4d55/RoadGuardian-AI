"""Demo-only response workflow and auditable validation calculations.

This module has no serial output and cannot authorize a real crossing.
Timings are illustrative, not a traffic signal engineering specification.
"""
from dataclasses import dataclass, replace
from engine import number


@dataclass(frozen=True)
class CrossingDemo:
    phase: str = "IDLE"
    since: float = 0.0

    def step(self, action, now, *, transition_s=3.0, clearance_s=4.0,
             timeout_s=15.0):
        now = number(now, "time")
        if now < self.since:
            raise ValueError("Time must be monotonic")
        if action == "reset":
            return CrossingDemo(since=now)
        if action == "fault":
            return replace(self, phase="FAULT", since=now)
        if self.phase == "FAULT":
            return self
        elapsed = now - self.since
        # Expired requests cannot be revived by a late confirmation.
        if self.phase == "REQUESTED" and elapsed >= timeout_s:
            return replace(self, phase="FAULT", since=now)
        if self.phase == "IDLE" and action == "request":
            return replace(self, phase="REQUESTED", since=now)
        if self.phase == "REQUESTED" and action == "confirm" and elapsed >= transition_s:
            return replace(self, phase="WALK_DEMO", since=now)
        if self.phase == "WALK_DEMO" and action == "finish":
            return replace(self, phase="CLEARANCE", since=now)
        if self.phase == "CLEARANCE" and action == "release" and elapsed >= clearance_s:
            return replace(self, phase="IDLE", since=now)
        return self


def stopping_distance(speed_kmh, response_s, deceleration, margin_m):
    """User-supplied level-road illustration; no inferred road properties."""
    speed = number(speed_kmh, "speed") / 3.6
    response = number(response_s, "response")
    braking = number(deceleration, "deceleration")
    margin = number(margin_m, "margin")
    if braking == 0:
        raise ValueError("Deceleration must be positive")
    return speed * response + speed * speed / (2 * braking) + margin


def validation_metrics(rows):
    """Trial-level alert classification, NOT YOLO object-detection mAP.

    Unknown/indeterminate trials are excluded and reported separately.
    Latencies require recorded observations; no missing-to-zero conversion.
    """
    counts = dict(tp=0, tn=0, fp=0, fn=0, excluded=0)
    delays = []
    for row in rows:
        expected, observed = row.get("expected"), row.get("observed")
        if type(expected) is not bool or type(observed) is not bool:
            counts["excluded"] += 1
            continue
        counts["tp" if expected and observed else "fn" if expected else "fp" if observed else "tn"] += 1
        if expected and observed and row.get("alert_ms") is not None:
            delays.append(number(row["alert_ms"], "alert_ms"))
    total = sum(counts[k] for k in ("tp", "tn", "fp", "fn"))
    negatives = counts["fp"] + counts["tn"]
    positives = counts["tp"] + counts["fn"]
    return {**counts, "n": total,
            "accuracy": (counts["tp"] + counts["tn"]) / total if total else None,
            "false_alarm_rate": counts["fp"] / negatives if negatives else None,
            "recall": counts["tp"] / positives if positives else None,
            "mean_alert_ms": sum(delays) / len(delays) if delays else None,
            "timed_trials": len(delays)}
