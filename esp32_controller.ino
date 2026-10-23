/* RoadGuardian AI - ESP32 classic DevKit / WROOM-32, active-HIGH LEDs.
 * Each GPIO -> 220-330 ohm resistor -> LED anode; LED cathode -> GND.
 * R: pedestrian conflict (red vehicle-stop indicator), GPIO25.
 * B: bridge warning GPIO26 blinks at 2Hz AND red GPIO25 stays on.
 * E: emergency priority green GPIO27; all other LEDs OFF.
 * G: normal/monitor GPIO33; emergency green OFF.
 * RX: one ASCII byte, no newline required. TX: echo after applying outputs.
 * No delays: heartbeat timeout remains responsive during all modes.
 * Intended for low-current demo LEDs, not direct traffic-light loads.
 */
#include <Arduino.h>

constexpr uint8_t RED_LED = 25;
constexpr uint8_t BRIDGE_LED = 26;
constexpr uint8_t EMERGENCY_GREEN_LED = 27;
constexpr uint8_t NORMAL_LED = 33;
constexpr uint32_t COMMAND_TIMEOUT_MS = 2000;
constexpr uint32_t BRIDGE_BLINK_INTERVAL_MS = 250;

uint32_t lastCommandAt = 0;
bool receivedCommand = false;
bool timedOut = true;
char activeCommand = '\0';
uint32_t lastBridgeToggleAt = 0;
bool bridgeOn = false;

void applyCommand(char command) {
  // Repeated heartbeat commands must not restart the blinking phase.
  if (command == activeCommand) return;
  activeCommand = command;
  bridgeOn = command == 'B';
  lastBridgeToggleAt = millis();
  // Clear green first so mode transitions cannot overlap priority and red.
  digitalWrite(EMERGENCY_GREEN_LED, LOW);
  digitalWrite(NORMAL_LED, LOW);
  digitalWrite(RED_LED, (command == 'R' || command == 'B') ? HIGH : LOW);
  digitalWrite(BRIDGE_LED, bridgeOn ? HIGH : LOW);
  digitalWrite(EMERGENCY_GREEN_LED, command == 'E' ? HIGH : LOW);
  digitalWrite(NORMAL_LED, command == 'G' ? HIGH : LOW);
}

void setup() {
  pinMode(RED_LED, OUTPUT);
  pinMode(BRIDGE_LED, OUTPUT);
  pinMode(EMERGENCY_GREEN_LED, OUTPUT);
  pinMode(NORMAL_LED, OUTPUT);
  applyCommand('R');  // Boot into the visible fallback state.
  Serial.begin(115200);
}

void loop() {
  // Bound work per iteration so a noisy sender cannot starve the watchdog.
  for (uint8_t count = 0; count < 32 && Serial.available() > 0; ++count) {
    const char command = static_cast<char>(Serial.read());
    if (command == '\r' || command == '\n') continue;
    if (command == 'R' || command == 'B' || command == 'E' || command == 'G') {
      applyCommand(command);
      lastCommandAt = millis();
      receivedCommand = true;
      timedOut = false;
      Serial.write(static_cast<uint8_t>(command));
    } else {
      applyCommand('R');
      receivedCommand = false;
      timedOut = true;
    }
  }
  // Unsigned subtraction handles millis() wraparound.
  if ((!receivedCommand || static_cast<uint32_t>(millis() - lastCommandAt) >= COMMAND_TIMEOUT_MS)
      && !timedOut) {
    applyCommand('R');
    timedOut = true;
  }
  if (activeCommand == 'B'
      && static_cast<uint32_t>(millis() - lastBridgeToggleAt) >= BRIDGE_BLINK_INTERVAL_MS) {
    lastBridgeToggleAt = millis();
    bridgeOn = !bridgeOn;
    digitalWrite(BRIDGE_LED, bridgeOn ? HIGH : LOW);
  }
}
