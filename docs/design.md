# Interface and system design

RoadGuardian uses an Arabic, right-to-left operations dashboard. SafeCross is the primary pedestrian demonstration, BridgeShield is secondary, and EcoTwin supports interpretation of simulated waiting time.

## Interface conventions

- IBM Plex Sans Arabic is bundled locally to avoid a font/CDN dependency.
- Arabic labels follow RTL layout; numbers, identifiers and units are isolated for LTR reading.
- Teal indicates primary actions. Hazard states include text labels alongside their colors.
- Native controls, visible keyboard focus and reduced-motion styles support interaction.
- The layout adapts to narrow screens and offers a collapsible sidebar. Useful manual review widths are 375, 768 and 1440 pixels; these are review targets, not an accessibility certification.
- Road schematics are labeled as illustrations rather than camera feeds. SVG views are embedded as image data URLs, with local fonts included where needed and dynamic text escaped.

## Data and output boundaries

| Path | Responsibility |
|---|---|
| `traffic_simulation.py` → `engine.evaluate` → dashboard/static scenes | Synthetic observations, animated movement and illustrative warnings |
| Camera → YOLO → geometry/rules → serial → ESP32 | Local vision experiments and demo LED commands |
| `edge_status.json` → dashboard | Latest local image and status snapshot; stale images are hidden |
| Waiting-time assumptions → EcoTwin | Read-only fuel/CO₂ estimates; no route to hardware commands |

Simulation playback never drives the ESP32. The response workflow uses simulated controller confirmation; neither an empty camera image nor a serial ACK grants crossing permission. Live connection indicators depend on fresh status and firmware acknowledgment rather than an open serial port alone.

The geometric vision path assumes a fixed, level camera and flat ground with calibration at the actual frame resolution. Tabletop road-region calibration is a separate experiment and does not replace site geometry. See the [hardware guide](hardware.md) for setup and the [validation record](validation.md) for evidence and limitations.
