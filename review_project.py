"""Run software checks and write a shareable summary without private paths."""
import hashlib
import io
import json
from pathlib import Path
import platform
import unittest

ROOT = Path(__file__).resolve().parent


def main():
    import os
    os.chdir(ROOT)
    suite = unittest.defaultTestLoader.discover(str(ROOT), pattern="test_*.py")
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    (ROOT / "audit-current-results.txt").write_text(log.getvalue(), encoding="utf-8")
    from package_release import SOURCES
    files = {name for name, _ in SOURCES} | {p.name for p in ROOT.glob("test_*.py")}
    summary = dict(scope="Software only; no real camera, serial port or firmware upload",
                   python=platform.python_version(), tests=result.testsRun,
                   failures=len(result.failures), errors=len(result.errors),
                   skipped=len(result.skipped), passed=result.wasSuccessful(),
                   source_sha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                  for name in sorted(files)})
    report = ROOT / "reports" / "test-summary.json"
    report.parent.mkdir(exist_ok=True)
    report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Software review: {result.testsRun} tests; {len(result.failures)} failures; {len(result.errors)} errors.")
    print("Shareable summary: reports/test-summary.json")
    if not result.wasSuccessful():
        print(log.getvalue())
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
