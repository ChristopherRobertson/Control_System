# Day 1-4 Completion Report - 2026-06-15

## Git and Configuration

- Git commit hash: `NO_GIT_COMMIT` (`git rev-parse HEAD` fails because the repository has no initial commit).
- Config path: `/mnt/c/Users/Chris/Documents/GitHub/Control_System/hardware_configuration.yaml`
- Current config SHA-256 after adding spreadsheet-derived Arduino MUX topology, Arduino command protocol, PicoScope capability metadata, repo-local PicoSDK runtime path, and full PicoSDK serial: `09b0759147b79505a96066759b577ff992f24ade93d0bf7304ba99f6e1269a99`
- Earlier T660 and timing-recipe hardware readbacks used config SHA-256 `44a39df263298f67c32ff02c71501341ec74c3da6e5d7e1616b3e878be9104cb`, as recorded in their run manifests.
- `hardware_configuration.yaml` was updated after `docs/Wiring Table.xlsx` was added. Existing device entries were preserved; spreadsheet-derived Arduino MUX topology and independent PicoScope metadata were appended.
- Inventory/hash files written:
  - `config/config_inventory.txt`
  - `config/config_hash.txt`

## Files Created or Updated

UI/control repo:

- `.gitignore`
- `requirements.txt`
- `control_app/config_loader.py`
- `control_app/manifest.py`
- `control_app/devices/t660_service.py`
- `control_app/devices/arduino_mux_service.py`
- `control_app/devices/picoscope_service.py`
- `control_app/workflows/timing_recipe_manager.py`
- `control_app/workflows/arduino_mux_diagnostic.py`
- `control_app/workflows/picoscope_settings_test.py`
- `control_app/devices/arduino_mux_firmware/arduino_mux_firmware.ino`
- `control_app/devices/arduino_mux_firmware/README.md`
- `control_app/__init__.py`
- `control_app/devices/__init__.py`
- `control_app/workflows/__init__.py`
- `control_app/ui/__init__.py`
- `config/run_manifest.schema.json`
- `config/config_inventory.txt`
- `config/config_hash.txt`
- `hardware_configuration.yaml`
- `recipes/safe_idle.yaml`
- `recipes/timing_calibration.yaml`
- `recipes/pump_probe_single_point.yaml`
- `recipes/picoscope_settings_test.yaml`
- `tests/hardware_checks/_common.py`
- `tests/hardware_checks/check_config_inventory.py`
- `tests/hardware_checks/check_forbidden_ui_imports.py`
- `tests/hardware_checks/check_t660_reproducibility.py`
- `tests/hardware_checks/check_timing_recipes.py`
- `tests/hardware_checks/check_arduino_mux_diagnostic.py`
- `tests/hardware_checks/check_picoscope_settings_apply.py`
- `logs/mircat_sdk_inventory_20260615.md`
- `logs/20260615_arduino_mux_command_log.txt`
- `logs/20260616_picoscope_settings_test_command_log.txt`
- `runs/20260615_t660_reproducibility/*`
- `runs/20260615_timing_recipe_readbacks/*`
- `runs/20260615_arduino_mux_diagnostic/*`
- `runs/20260616_picoscope_settings_test/*`
- `vendor/picosdk/win64/*`

External Article path only:

- `/mnt/c/Users/Chris/Documents/UC Davis/SETI/Thesis/Article 1 - Review of Scientific Instruments/RSI_Draft_v3.docx`
- `/mnt/c/Users/Chris/Documents/UC Davis/SETI/Thesis/Article 1 - Review of Scientific Instruments/RSI_Draft_v2.1.docx`
- `/mnt/c/Users/Chris/Documents/UC Davis/SETI/Thesis/Article 1 - Review of Scientific Instruments/Open_Decisions.md`
- `/mnt/c/Users/Chris/Documents/UC Davis/SETI/Thesis/Article 1 - Review of Scientific Instruments/Figures/Figure_1_system_block_schematic_draft.svg`
- `/mnt/c/Users/Chris/Documents/UC Davis/SETI/Thesis/Article 1 - Review of Scientific Instruments/Figures/Figure_2_timing_diagram_draft.svg`
- `/mnt/c/Users/Chris/Documents/UC Davis/SETI/Thesis/Article 1 - Review of Scientific Instruments/Tables/Figure_Data_Dependencies.xlsx`
- `/mnt/c/Users/Chris/Documents/UC Davis/SETI/Thesis/Article 1 - Review of Scientific Instruments/Tables/Table_Data_Dependencies.xlsx`
- `/mnt/c/Users/Chris/Documents/UC Davis/SETI/Thesis/Article 1 - Review of Scientific Instruments/Tables/Component_Table.xlsx`
- `/mnt/c/Users/Chris/Documents/UC Davis/SETI/Thesis/Article 1 - Review of Scientific Instruments/Tables/Timing_Claims_To_Measure.xlsx`

## Day 1 Gates

- PASS: Article root was accessible and Article deliverables were created under the Article 1 RSI path only.
- PASS: RSI draft skeleton exists as `RSI_Draft_v3.docx` with required sections.
- PASS: Figure/table dependency records exist under Article `Tables/`.
- PASS: UI scaffold directories exist.
- PASS: Config loader reads the existing YAML, computes the exact byte hash, and writes inventory/hash files.
- PASS: No forbidden article/thesis/manuscript/figures/tables directories were found inside the UI repo.

## Day 2 Gates

- PASS: `control_app/devices/t660_service.py` implements real serial/TCP T660 command sessions and the required public methods.
- PASS: Article Instrument Design text, Figure 1 draft, and Component Table were created under the Article path only.
- PASS: Real T660 reproducibility/readback completed with native Windows Python from `.venv`.
- PASS: `safe_idle` was applied/read back five times across T660-1 and T660-2.
- Evidence:
  - `runs/20260615_t660_reproducibility/command_log.txt`
  - `runs/20260615_t660_reproducibility/t660_readback_before_after.json`
  - `runs/20260615_t660_reproducibility/error_flags.json`
  - `runs/20260615_t660_reproducibility/run_manifest.json`

## Day 3 Gates

- PASS: `control_app/workflows/timing_recipe_manager.py` parses recipes, resolves configured signal names to T660 unit/channel, applies through `T660Service`, and writes readback JSON when hardware is available.
- PASS: `recipes/safe_idle.yaml`, `recipes/timing_calibration.yaml`, and `recipes/pump_probe_single_point.yaml` exist.
- PASS: Article Timing and Synchronization text, Figure 2 draft, and Timing Claims table were created under the Article path only.
- PASS: `safe_idle`, `timing_calibration`, and `pump_probe_single_point` were applied to real T660 hardware and read back successfully with native Windows Python from `.venv`.
- Evidence:
  - `runs/20260615_timing_recipe_readbacks/command_log.txt`
  - `runs/20260615_timing_recipe_readbacks/safe_idle_recipe_readback.json`
  - `runs/20260615_timing_recipe_readbacks/timing_calibration_recipe_readback.json`
  - `runs/20260615_timing_recipe_readbacks/pump_probe_single_point_recipe_readback.json`
  - `runs/20260615_timing_recipe_readbacks/run_manifest.json`

## Day 4 Gates

- PASS: `control_app/devices/arduino_mux_service.py` implements a real serial wrapper that requires configured route names and command templates.
- PASS: `control_app/devices/picoscope_service.py` implements a real PicoSDK `ps5000a` block-capture path.
- PASS: `control_app/workflows/arduino_mux_diagnostic.py` verifies Arduino MUX serial identity, firmware/protocol readback, MUX Output A/B/EXT route command/readback, and safe idle without opening the PicoScope.
- PASS: `tests/hardware_checks/check_forbidden_ui_imports.py` found no forbidden UI hardware imports.
- PASS: Article Control Software text and independent Arduino MUX and PicoScope calibration rationale were added to the external draft; the UI/state-machine dependency row was added to the Article figure dependency table.
- PASS: `docs/Wiring Table.xlsx` was used to append MUX route topology, Arduino MUX control-pin topology, PicoScope input topology, and a diagnostic route selector to `hardware_configuration.yaml`.
- PASS: Arduino MUX firmware and matching serial command templates were added for identity, version, route selection, route readback, and safe-disable behavior.
- PASS: Route alignment was corrected: T660 TTL timing outputs are direct routes to MIRcat TRIG IN, Nd:YAG FIRE/Q-SWITCH, HF2LI DIO timing inputs, and T660-1 TRIG IN. They are not routed through the Arduino MUX.
- PASS: `hardware_configuration.yaml` now defines PicoScope capability metadata, recipe-driven settings source, direct TTL route alignment, repo-local PicoSDK runtime path, and full PicoSDK serial under `devices.picoscope`.
- PASS: `recipes/picoscope_settings_test.yaml`, `control_app/workflows/picoscope_settings_test.py`, and `tests/hardware_checks/check_picoscope_settings_apply.py` were added for real PicoScope settings-apply testing.
- PASS: Real PicoScope settings application completed through native Windows Python after loading `vendor\picosdk\win64\ps5000a.dll`, using SDK serial `10261/0071`, and closing the PicoScope 7 UI before opening the unit through the SDK.
- BLOCKED: Historical combined Arduino MUX and PicoScope diagnostic artifact is superseded; independent Arduino MUX route evidence must be rerun with current hardware_configuration.yaml. This remains separate from T660 TTL trigger routing, which is direct.
- Evidence:
  - `runs/20260615_arduino_mux_diagnostic/BLOCKED.md`
  - `runs/20260615_arduino_mux_diagnostic/run_manifest.json`
  - `logs/20260615_arduino_mux_command_log.txt`

## Hardware Check Commands and Exit Statuses

Initial WSL `python3` hardware attempts were blocked because Windows COM ports were not available as `COM3`/`COM7` from WSL. The checks were rerun with native Windows Python from `.venv/Scripts/python.exe`.

- `python3 -m compileall control_app tests/hardware_checks` -> exit `0`
- `python3 tests/hardware_checks/check_config_inventory.py` -> exit `0`
- `python3 tests/hardware_checks/check_forbidden_ui_imports.py` -> exit `0`
- `python3 tests/hardware_checks/check_t660_reproducibility.py --operator "Codex" --confirm-real-hardware` -> exit `2` in WSL, superseded by native Windows retry
- `python3 tests/hardware_checks/check_timing_recipes.py --operator "Codex" --confirm-real-hardware` -> exit `2` in WSL, superseded by native Windows retry
- `python3 tests/hardware_checks/check_arduino_mux_diagnostic.py --operator "Codex" --confirm-real-hardware` -> exit `2`
- `.venv/Scripts/python.exe -m compileall control_app tests/hardware_checks` -> exit `0`
- `.venv/Scripts/python.exe tests/hardware_checks/check_config_inventory.py` -> exit `0`
- `.venv/Scripts/python.exe tests/hardware_checks/check_forbidden_ui_imports.py` -> exit `0`
- `.venv/Scripts/python.exe tests/hardware_checks/check_t660_reproducibility.py --operator "Codex" --confirm-real-hardware` -> exit `0`
- `.venv/Scripts/python.exe tests/hardware_checks/check_timing_recipes.py --operator "Codex" --confirm-real-hardware` -> exit `0`
- `.venv/Scripts/python.exe tests/hardware_checks/check_arduino_mux_diagnostic.py --operator "Codex" --confirm-real-hardware` -> exit `2`
- `.venv/Scripts/python.exe tests/hardware_checks/check_picoscope_settings_apply.py --operator "Codex" --confirm-real-hardware` -> exit `0`; PicoSDK driver loaded from `C:\Users\Chris\Documents\GitHub\Control_System\vendor\picosdk\win64\ps5000a.dll`, then `OpenUnit`, `SetDeviceResolution`, `SetChannel A/B`, `SetSimpleTrigger`, `GetTimebase2`, `Stop`, and `CloseUnit` all returned status `0`.

## Hardware IDs and Readbacks

Configured IDs from `hardware_configuration.yaml`:

- T660-1: serial `00369`, port `COM3`
- T660-2: serial `00431`, port `COM7`
- Arduino MUX: expected identity `ARDUINO_MUX_V1`, port `COM6`
- MIRcat: model `MIRcat-QT-Z-2100`, serial `10524`, port `COM9`
- HF2LI: device ID `18500`
- PicoScope: model `5244D`, serial `10261`

Real hardware identity/readback records:

- PASS: T660 reproducibility completed 5 cycles.
- PASS: T660-1 identity `HTI,T660-1,00369,28E660-1-1.7`; firmware `28E660-1-1.7`.
- PASS: T660-2 identity `HTI,T660-2,00431,28E660-1-1.7`; firmware `28E660-1-1.7`.
- PASS: Timing recipe readbacks were recorded for `safe_idle`, `timing_calibration`, and `pump_probe_single_point`.
- PASS: PicoScope settings apply completed for `recipes/picoscope_settings_test.yaml`.

## Blockers and Next Actions

- PicoScope settings apply is complete.
  - Next action: run the independent Arduino MUX diagnostic with the Arduino MUX available; keep PicoScope checks separate.

## Discipline Confirmations

- No Article artifacts were created inside the UI/control repo.
- No fake device models, simulator backends, stub data streams, synthetic traces, artificial device responses, or demo mode were added to the active application path.
- No UI file imports hardware libraries or project device service modules directly.
- `hardware_configuration.yaml` was updated only in response to the explicit spreadsheet request; existing items were not edited.
- MIRcat SDK was inventoried in `logs/mircat_sdk_inventory_20260615.md`; no Day 5 MIRcat service was implemented and no MIRcat connection was opened.
