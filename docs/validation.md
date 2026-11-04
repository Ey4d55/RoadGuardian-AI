# Validation record

RoadGuardian is an educational traffic-safety prototype with simulated scenarios and local LED experiments. Software checks and reported hardware observations have different scopes. Neither constitutes certification for road use or evidence of collision-prevention performance.

The hardware observations below were retained from the project record for **22–23 October 2026**. They were not repeated during the documentation cleanup on **25 October 2026**.

## Reported hardware observations

The previous record attributes these observations to user confirmation during setup, accompanied by serial ACK data and local status snapshots. Camera captures remain local and are not distributed with the repository. No controlled accuracy study or physical response-time measurements were recorded.

| Experiment | Reported observation | Evidence limit |
|---|---|---|
| Firmware upload | Upload to NodeMCU ESP-32S succeeded; `R` and `B` were received | Historical user confirmation; no new compile or flash during this cleanup |
| LED outputs | `R` held GPIO25 red on; `B` held red on and blinked GPIO26 | Visual user confirmation; ACK alone does not establish output state |
| Camera preview | Samsung S24 Ultra feed exposed as a Windows camera appeared in the dashboard with person detection | Specific setup only; complete operation without a network was not established |
| Person-presence mode | Red turned on with a person present and off after absence | Separate presence experiment; no collision assessment or crossing authorization |
| Toy-car stop line | Red turned on near the virtual stop line and off when the car moved back, from a suitable angle | Detection from directly in front remained unreliable |
| Tracking occlusion | Hiding the car caused a red fallback and a tracking-loss explanation | A warning about unavailable observations, not proof of pedestrian/vehicle conflict detection |
| Tabletop dimensions | User supplied a 22 × 14 cm notebook surface | Visual boundaries were approximate; estimated distances were not compared with ruler measurements |

These experiments must remain separate when presenting results. They do not establish that simultaneous pedestrian/vehicle protection was demonstrated in one physical scene.

## Software verification

From the repository root, with the dashboard dependencies installed in the active environment:

```bash
python review_project.py
python package_release.py
```

`review_project.py` discovers `test_*.py` and writes a machine-readable [test summary](../reports/test-summary.json) containing the Python version, counts, result and hashes of runtime sources and tests. Counts belong to that report rather than a manually maintained claim in this document. Check the source hashes before associating an older report with changed code. The local detailed log is `audit-current-results.txt`.

The CI workflow runs the same review and packaging commands on Python 3.11. Local verification has also used Python 3.13 and Streamlit 1.66.0. CI configuration describes the checks; its presence alone is not evidence of a successful remote run.

| Area | Software coverage |
|---|---|
| Decision engine | Strict bridge-height boundary above 4.5 m, warning priorities, invalid and nonfinite inputs, heuristic risk bounds |
| Geometry | Scale conversion, TTC consistency, site regions and input validation |
| Serial protocol | Command acknowledgment, disconnect/reconnect, stale ACK rejection and partial-write handling with fake devices |
| Vision loop | Synthetic detections, camera failure, stale observations and red fallback through mocked dependencies |
| Dashboard | View changes, invalid status data/images, stale camera-frame hiding and separation of simulation from live outputs |
| Tabletop mode | Road polygon validation, stop-line decisions and uncertainty for cropped or untracked vehicles |
| Simulation | Pedestrian crossing after simulated stops, spacing between queued vehicles, stop-line behavior and static-export parity |
| EcoTwin | Vehicle counts, individual waiting-time totals, proportional fuel/CO₂ calculations and independence from safety commands |
| Release | Required runtime files and local imports; packaging verifies ZIP contents against source files |

These tests do not open a physical camera or serial device, run an object-detection benchmark, compile/flash firmware or measure LED response time. The two-second firmware timeout is an implemented behavior; its physical timing still needs a recorded test.

## Simulation and EcoTwin interpretation

Each animation has an 18-second window. The congestion scene draws six vehicles in two directions with separate stop/start delays and waiting-time totals; individual scenes draw one vehicle. Pedestrian crossing is programmed to occur after the simulated vehicle stop and red indication. It is not confirmation from a physical controller.

EcoTwin sums the waiting time of the drawn vehicles. Its reference assumes the same vehicles idle for the full 18 seconds. Playback, pause, reset and seeking use the same clock for movement and cumulative impact.

Default idle consumption of **1.0 L/h** and a factor of **2.348 kg CO₂/L** are illustrative assumptions. The repository does not document a fleet-specific calibration or a source establishing those defaults for the demonstration. It does not measure driving emissions, NOx, PM2.5 or planetary-boundary effects, and the displayed comparison is not evidence of an achieved reduction. Live impact stays unavailable without fleet waiting-time data. EcoTwin never issues commands or modifies safety rules.

## Unverified capabilities and missing measurements

- Combined pedestrian and vehicle protection in one physical tabletop scene.
- Reliable toy-car detection across angles, particularly directly from the front; no custom model was trained.
- Detection accuracy, missed-hazard/false-negative rate and false-alarm rate on a defined reference dataset.
- End-to-end latency from a documented reference hazard to the physical warning output.
- Camera distance, speed and height estimates checked against independent measurements at multiple positions.
- Independent height-sensor integration and physical low/high truck trials.
- Automatic ambulance recognition; emergency priority is a simulation feature.
- Complete operation after disconnecting all networks while retaining the phone-camera path.
- Physical timeout, reconnect and full four-output behavior supported by recorded observations.
- Real traffic-signal integration, crossing permission and automatic vehicle stopping; these are outside the current prototype's validated scope.

The earlier review also stated that it could not recompile or reflash the firmware because `arduino-cli` was unavailable. Source recovery from a saved copy was a maintenance action, not a firmware validation result.

## Recording future experiments

Use the dashboard's manual validation view and export the CSV before closing the browser. Record the mode, source revision, camera/board setup, calibration, lighting, ground-truth condition, system response and an evidence reference. Keep physical trials separate from simulations and report unresolved trials explicitly.

The [pedestrian workflow guide](../PEDESTRIAN_FIRST.md) defines the existing metrics: false-alarm rate uses safe reference cases as its denominator, hazard-detection rate uses reference hazard cases, and missing denominators must remain unavailable. YOLO detection confidence is not test-set accuracy; frame processing time is not physical alert latency. Firmware ACK confirms command receipt, not that a vehicle stopped or a crossing is safe.

For demonstrations, present the animated scenarios, person-presence experiment and toy-car stop-line experiment as their respective modes. Label distances as estimates and distinguish a hazard warning from a warning caused by missing observations. Use the [hardware guide](hardware.md) for commands and the [physical-demo guide](../PHYSICAL_DEMO.md) for rehearsal procedures.
