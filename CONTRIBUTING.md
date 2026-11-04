# Development and maintenance

Run commands from the repository root. Create the virtual environment and install dashboard dependencies using the [README quickstart](README.md#quickstart), then activate it:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# Linux / macOS
source .venv/bin/activate
```

## Software checks

```bash
python review_project.py
python package_release.py
```

The review runs the existing unittest suite, saves a local detailed log to `audit-current-results.txt` and writes `reports/test-summary.json` with result counts, the Python version and source hashes. For direct unittest output, use `python -m unittest discover -v`.

The checks use fake camera/serial devices and the dashboard dependencies. They do not download model weights, exercise real hardware, compile firmware or establish detection accuracy. Read [docs/validation.md](docs/validation.md) before describing test results.

[GitHub Actions](.github/workflows/ci.yml) installs `requirements-dashboard.txt`, runs both commands on Python 3.11 and uploads the source ZIP. Confirm the actual workflow result for the revision being reviewed.

## Source package

`package_release.py` uses an explicit file allowlist to create:

- `RoadGuardian_AI_Edge_Package.zip`: runtime source, tests, guides, static demo and local assets. It includes an Arduino-friendly `esp32_controller/esp32_controller.ino` copy.
- `COMPLETE_CODE.md`: generated text of the runtime sources. Edit the original files rather than this output.

The script verifies ZIP integrity and compares packaged files with their source bytes. Both outputs are ignored by Git. When moving or adding a required source, guide or asset, update the allowlist and run both software checks and packaging again. Documentation links must resolve in both the repository and the extracted ZIP.

## GitHub Pages

The static demo is served from `main:/docs`. It displays simulation and EcoTwin only; camera and ESP32 operation require local Python processes.

After changing the simulation, decision engine or shared HTML assets, regenerate the scenarios:

```bash
python build_pages.py
python review_project.py
python package_release.py
```

Review and include the updated `docs/scenes/*.html` files with the source change. `test_pages.py` checks that those exports match the generator. `docs/index.html` is the maintained entry page; `build_pages.py` only regenerates the scenes. `dist/` is excluded and is not a Pages deployment source. These commands do not push or publish anything.

## Local data

Keep camera frames, phone photos, videos, model weights, training datasets, dependencies, credentials and machine-specific `road_region.json` and `site.json` outside commits and source releases. `edge_status.json` can contain the latest camera image. Use the example configurations as templates and retain actual calibration locally.

Before sharing changes, inspect `git status --short`, the diff and ZIP contents. Do not force-add ignored private files. Preserve the explicit packaging allowlist rather than archiving the entire workspace.

## Documentation and evidence

Keep hardware commands in [docs/hardware.md](docs/hardware.md), current validation evidence in [docs/validation.md](docs/validation.md) and interface decisions in [docs/design.md](docs/design.md). Record test scope and evidence dates; do not promote simulation output or user observations to measured performance. Replace superseded statements instead of appending contradictory corrections.

No project-wide license has been selected. Keep [third-party notices](THIRD_PARTY_NOTICES.md) and the bundled font license intact. Model weights are installed separately and are not included in the source release.
