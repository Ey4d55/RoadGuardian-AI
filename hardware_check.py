# Install: python -m pip install "pyserial>=3.5,<4"
"""LED-only wiring check; stop the vision process and Serial Monitor first.

Run: python hardware_check.py --port COM3
This sends explicit test commands; it is NOT a camera-detection demonstration.
ACK verifies firmware receipt, not LED wiring. Inspect each light yourself.
"""
import argparse
import logging
import time

from vision_serial_bridge import SerialLink

STEPS = [(b"G", "NORMAL: white GPIO33 only"),
         (b"R", "PEDESTRIAN: red GPIO25 only"),
         (b"B", "BRIDGE: GPIO26 blinks, red GPIO25 stays ON"),
         (b"E", "PRIORITY: green GPIO27 only")]


def run_step(link, command, description, clock=time.monotonic, sleep=time.sleep):
    """Allow board boot/reconnect, then sustain a visibly inspectable 3s step."""
    print(f"\nTEST {command.decode()} - Expected: {description}", flush=True)
    started = clock()
    while not link.tick(command, clock()):
        if clock() - started >= 10:
            raise RuntimeError(f"No firmware ACK for {command.decode()}: {link.error}")
        sleep(0.1)
    print("Firmware ACK received; inspect LEDs now.", flush=True)
    until = clock() + 3
    while clock() < until:
        if not link.tick(command, clock()):
            raise RuntimeError(f"Connection lost during {command.decode()}: {link.error}")
        sleep(0.1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM3")
    args = parser.parse_args()
    import serial
    logging.basicConfig(level=logging.WARNING)
    link = SerialLink(serial, args.port, 115200)
    exit_code = 0
    try:
        for command, description in STEPS:
            run_step(link, command, description)
        print("\nWATCHDOG TEST: no commands for 3 seconds. Expect green OFF and red ON by 2 seconds.", flush=True)
        time.sleep(3)
        print("Command/ACK checks complete. Confirm LED and watchdog behavior visually.", flush=True)
    except (RuntimeError, KeyboardInterrupt) as exc:
        print(f"\nCheck interrupted: {exc}", flush=True)
        exit_code = 1
    finally:
        link.tick(b"R", time.monotonic())
        link.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
