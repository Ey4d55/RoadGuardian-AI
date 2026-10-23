"""Tests the LED check driver using a fake clock/link, without hardware I/O."""
import contextlib
import io
import unittest

from hardware_check import run_step


class Clock:
    def __init__(self):
        self.time = 0.0

    def now(self):
        return self.time

    def sleep(self, seconds):
        self.time += seconds


class Link:
    error = "No ACK"

    def __init__(self, connects):
        self.connects = connects
        self.calls = []

    def tick(self, command, now):
        self.calls.append((command, now))
        return self.connects and now >= 0.3


class HardwareCheckTests(unittest.TestCase):
    def test_boot_then_three_second_heartbeat(self):
        clock, link = Clock(), Link(True)
        with contextlib.redirect_stdout(io.StringIO()):
            run_step(link, b"B", "bridge", clock.now, clock.sleep)
        self.assertGreaterEqual(clock.time, 3.3)
        self.assertTrue(all(cmd == b"B" for cmd, _ in link.calls))
        self.assertLessEqual(max(b[1] - a[1] for a, b in zip(link.calls, link.calls[1:])), 0.101)

    def test_missing_ack_does_not_report_success(self):
        clock, link = Clock(), Link(False)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            run_step(link, b"G", "normal", clock.now, clock.sleep)
        self.assertGreaterEqual(clock.time, 10)


if __name__ == "__main__":
    unittest.main()
