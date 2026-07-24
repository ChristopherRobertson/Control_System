# P0 execution-baseline record

Campaign: `20260722_complete_system_recalibration_001`  
P0 classification at capture: **BLOCKED — CLEAN COMMIT REQUIRED BEFORE S0**  
Captured: `2026-07-24T11:11:14.7654318-07:00`  
Connection-instruction amendment validated: `2026-07-24T11:25:32.1567102-07:00`  
Timezone: `America/Los_Angeles` (`Pacific Standard Time`, UTC-07:00 at capture)  
Operator: `Christopher Robertson`  
Absolute campaign path:
`C:\Users\Chris\Documents\GitHub\Control_System\calibration\20260722_complete_system_recalibration_001`

## Hardware-access statement

**No hardware connection was opened, no device command was sent, no device was
queried, no cable was moved, and no measurement acquisition was performed
during P0.** Physical inventory values were obtained from operator inspection,
operator reports of prior identification, installed-file metadata, and
document review. T660 firmware readback remains deferred to S0.

## Git and repository state

- Branch: `main`
- Full local commit: `6d267fcdc10331de0e12aeec5028049be0a97182`
- `origin/main`: `06f1c83cf6cf9e633558c599b339974aacbe2a61`
- Local `main` relationship to `origin/main`: `2 ahead, 0 behind`
- Working tree: **DIRTY**
- Dirty state at capture: 16 modified tracked files and 3 untracked files
  before creation of this baseline/blocker pair.
- Git whitespace/diff validation: **PASS**
- `calibration/timing_calibration.csv`: absent
- `calibration/timing_offsets.yaml`: absent
- Historical provenance and recipe-hash snapshots were not overwritten.
- No active executable dependency on `Control_System_Archives` was found.
- No active T660-1 CH D to MIRcat DB9 pin-5 route was found.
- Arduino MUX configuration: disabled and excluded; direct wiring remains
  mandatory.

The dirty candidate state is identified by the hashes below, but it is not an
acceptable S0 execution revision until reviewed and committed as a clean local
baseline. No push is required or authorized by this record.

## Required file hashes

| SHA-256 | File |
|---|---|
| `32b9a32e33004fcd69f5212a18e74ff34ace4922612786ff3de82b7c341a71a6` | `hardware_configuration.yaml` |
| `e4ce448328bdbf45c1bbbbf5b684934c7f00956ea326cb677e95a3f3b17f4d36` | `wiring_map.yaml` |
| `550ea15d7ef1a3a55689384ab3871070adcf15440011ac441ea9dca97009ae1d` | `recipes/timing_calibration.yaml` |
| `885a1ce00c6bf80b52cbc882d7dc66493798cd2a02c91a9053d8f0cc5734ea94` | `recipes/safe_idle.yaml` |
| `82f90590c0d0fc0259378c8f5592b555cc0e5d36d57e0206be9adac79db7681f` | `recipes/picoscope_settings_test.yaml` |
| `5cec26046fe3dbc05049e61f1b1767140a960e2c347de4a4965f7fc2df51b20b` | `recipes/ndyag_alignment_10hz.yaml` |
| `f83c491051f01d0920f1f6ec4bfe9be4cecbe3c1bb92cff764b1110c7fef0308` | `recipes/pump_probe_single_point.yaml` |
| `1f45e6f97d3cc9fb746a130636eded8a7393f853d9e59595b31e7c32b74db669` | `config/config_hash.txt` |
| `e156772f088744547fd38cf277ead798521d21b80d918e2e35a644397b0b4667` | `config/config_inventory.txt` |
| `4c8aceb7b63342eb2547fb8f3342b1f44ccf940a1b08cb6b6e542cc44ded9acb` | `docs/Wiring Table.xlsx` |

Selected PicoScope recipe:
`recipes/picoscope_settings_test.yaml`

Selected optical recipe:
`recipes/ndyag_alignment_10hz.yaml`

## Relevant source and test hashes

| SHA-256 | File |
|---|---|
| `b9eb8b3b10637dc2a0cb5a97e3c6be4e6d88f1890ccdc0db85ad6d26fecfa5cb` | `control_app/workflows/timing_calibration_procedure.py` |
| `bb13a10231b985913356058a3e214f952ddd7b9dfa131ef0c089a79dc727e954` | `control_app/workflows/timing_trace_analysis.py` |
| `7f67dc07d35b3c776bc4072a95961aa4af7b789608ab3d3b435b130ac7eb5df0` | `control_app/workflows/timing_recipe_manager.py` |
| `44d9a3a7d699da4514d6ab2bb5e31a05a8ef2d7f1414e4ce111e56a71fd7e1c2` | `control_app/devices/t660_service.py` |
| `b27148a2f3b62da576884ebf83a69cef74e18b93bf7d1d588b3554dd10686067` | `control_app/config_loader.py` |
| `d0b955c8a10f1cac62252e90957e1650ed3376bbce935d640d0c2312a270fd90` | `tests/hardware_checks/check_complete_timing_calibration.py` |
| `d229d9de920b0bdf6e23c6e9a48b8b3a6c4bdbacfe6ea5972de272825c04d0f6` | `tests/test_timing_calibration_procedure.py` |
| `03fa3a1c6c57a62bdbe8b99ace2a2e167241b583118d3a97093c5b5ecc192b1a` | `tests/test_t660_persistent_state.py` |
| `4003154bbaebb6bb7a512b3a3e5dc2f1895ff0288f386d5e6927c8b8c4e75828` | `tests/test_experiment_builder.py` |
| `8a4d9dfe1a3772e9b77fe8c9a63e568910709c5aef9bd0ce3be2bf5764362bdb` | `docs/MIRcat/daylight_db9_process_trigger_correspondence.md` |
| `67be029444a19fb539132c812b8d3dfa9aac9ad93112ed233ea8f13435d0e72e` | `docs/timing_calibration_procedure.md` |
| `39bab7d5b00b5fee56375dd45d52ae08d05c45323ad56a8b5f55044271497ed0` | `calibration/20260722_complete_system_recalibration_001/manifests/p0_physical_inventory.md` |
| `4e52e247a11f4e0eff4ebf195edc8562f17aa3af6e688d5f3cd76fb9436b6748` | `calibration/20260722_complete_system_recalibration_001/manifests/p0_blocker_table.md` |
| `788c956e04c7251492ff9a36308ade0c95d1c1c40e9b0613b7c609fc33b0f8fe` | `calibration/20260722_complete_system_recalibration_001/manifests/p0_python_environment.txt` |

The source, procedure, test, correspondence, inventory, and blocker hashes
above were refreshed after the connection-instruction amendment. Any
subsequent correction requires another baseline hash capture.

## Windows and application environment

- Windows: Microsoft Windows 11 Pro, version `10.0.26200`, build `26200`
- Windows PowerShell: `5.1.26100.8894`
- Python executable:
  `C:\Users\Chris\Documents\GitHub\Control_System\.venv\Scripts\python.exe`
- Python: `3.12.4`, MSC v.1940, 64-bit AMD64
- pip: `26.1.2`
- Dependency snapshot:
  `manifests/p0_python_environment.txt`
- Application package version: no packaged version identified; Git revision
  plus source hashes are the application identity.

### PicoScope

- Physically confirmed model: `5244D`
- Physically confirmed serial: `10261`
- SDK identifier: `10261/0071`
- Bundled `ps5000a.dll`: file/product version `2.2.16.5110`
- Bundled DLL SHA-256:
  `771e314f1eed2a45883e7d3a27262cc243e5973c22b86e61c6a2e39e130e84c0`
- PicoScope 7 T&M Stable: `7.2.19.9415`
- PicoScope 7 T&M Early Access: `7.2.24.9442`
- Installed SDK-lib `ps5000a.dll`: `2.2.8.5060`
- Workflow driver search order selects the repository-bundled DLL before the
  installed SDK path.

### MIRcat

- Bundled `MIRcatSDK.dll`: file/product version `2.4.1.1`
- Bundled DLL SHA-256:
  `da2c304706e37a67697f6325d40708e229bed58a3da081d4fab71733cfd79c3c`
- MIRcat Control GUI: `1.9.0.4`

### HF2LI/LabOne

- Installed LabOne release family: `26.04`
- Installed MF firmware package: `LabOneMF-26.04.1.6.tar`
- Python packages: `zhinst 26.4.1`, `zhinst-core 26.4.1.6`,
  `zhinst-timing-models 26.4.0`, `zhinst-toolkit 1.4.0`,
  `zhinst-utils 0.7.2`
- No device was connected to confirm active device firmware.

### T660

- T660-1 and T660-2 identities are recorded in
  `manifests/p0_physical_inventory.md`.
- Firmware versions: unresolved; safe readback deferred to S0.

## Software-only validation

All checks ran using the Windows virtual-environment Python. No hardware was
opened.

| Check | Result |
|---|---|
| Timing-calibration procedure tests | **PASS — 17/17** |
| T660 persistent-state tests | **PASS — 6/6** |
| Experiment-builder tests | **PASS — 6/6** |
| Nd:YAG alignment workflow contract | **PASS** |
| Forbidden UI hardware-import scan | **PASS** |
| Configuration inventory check | **PASS** |
| Git whitespace/diff validation | **PASS** |

The formerly failing Step 7 fake-hardware pacing test passed in the full suite
and in three consecutive focused runs after deadline/recheck pacing was
implemented.

The configuration inventory check regenerated its two inventory records. Their
path field was restored to the tracked repository convention; substantive
inventory/hash updates for the confirmed Nd:YAG/OPO devices were retained.

## Related P0 records

- `manifests/p0_physical_inventory.md`
- `manifests/p0_python_environment.txt`
- `manifests/p0_blocker_table.md`
- `docs/MIRcat/daylight_db9_process_trigger_correspondence.md`

## Exact requirement before S0

Review the complete working diff, resolve any remaining P0 issues, create a
clean local commit identifying this candidate state, rerun the P0 software
checks, and capture a new clean-commit hash manifest. Do not begin S0 until the
user explicitly approves continuing.
