# ACTION REQUIRED — IR Spectroscopy Control Interface (User Tasks Only)

Provide the following information or perform the listed actions. This file tracks only outstanding items needed from users in the lab.

## Connection Parameters (Per Device)
- Arduino MUX: Provide the exact USB port for the controller on each lab PC (e.g., COM3, /dev/ttyUSB0, /dev/cu.usbmodem*).
- Quantum Composers 9524: Confirm the correct COM port and baud rate per PC.
- Zurich HF2LI: Provide the actual device ID (e.g., dev1234) and LabOne server address (localhost or instrument IP).
- Daylight MIRcat: Confirm whether SDK is bundled in repo (./docs/sdks/daylight_mircat) or installed system‑wide; if installed, provide the path.
- PicoScope 5244D: Confirm PicoSDK is installed for all users on each lab PC.

## SDK Install/Path Confirmation
- Windows: Verify SDK install locations and bitness (64‑bit):
  - PicoSDK: C:\Program Files\Pico Technology\SDK.
  - MIRcat SDK: bundled path or installed path.
  - Zurich LabOne: install path and Python module availability.
- Set environment variables where applicable (optional overrides):
  - PICO_SDK_PATH, MIRCAT_SDK_PATH, and other <DEVICE>_SDK_PATH as needed.

## Wiring/Integration Details
- Nd:YAG via QC 9524:
  - Identify which QC 9524 channel(s) drive Q‑switch/fire TTL signals.
  - Provide timing parameters: thresholds, widths, delays, repetition rate, trigger sequence.
- Arduino MUX:
  - Provide number of positions, command format, and any limit/feedback behavior.

## Parameter Ranges To Confirm
- PicoScope 5244D: Supported voltage ranges per channel, timebase selections, trigger capabilities used in experiments.
- Zurich HF2LI: Frequency range, time constants, input ranges, demodulator settings used in the lab.
- Quantum Composers 9524: Valid ranges for duty cycle ON/OFF counts and any lab‑specific limits.

## Access and Accounts
- Ensure all lab users who will run the UI can:
  - Access the repo location with read/execute permissions.
  - Launch backend and frontend under their own profiles.
  - Access installed SDKs (install “for all users” or provide env vars per user).

## Test Expectations
- Specify which PC(s) are used for live tests and connected instruments.
- Provide a time window to perform a short live connection test per device.

## Next Immediate Steps
- PicoScope 5244D: proceed with Part D when ready (install PicoSDK, confirm SDK path); controller remains Phase‑1 for now.

- Quantum Composers 9524 (Signal Generator):
  - The module now performs live serial I/O (no simulation). Confirm the COM port and baud rate on each PC (`hardware_configuration.toml` → `[quantum_composers_9524]`).
  - Verify the command templates in `hardware_configuration.toml` under `[quantum_composers_9524.commands]` against your firmware. Adjust mnemonics if needed (e.g., `PER` vs `PERIOD`, `RUN?` vs a different query). No code changes required.
  - Validate min/max ranges for thresholds and amplitudes already captured in `hardware_configuration.toml`; add any missing items.
  - Confirm final channel mapping to devices (A/B/C/D to Nd:YAG Q-switch / fire, MIRcat trig in, HF2LI DI1) and provide default delays/widths if the lab has standards.
