# P0 execution-baseline record

Campaign: `system_recalibration_001`
P0 classification: **COMPLETE — AWAITING EXPLICIT USER APPROVAL FOR S0**
Captured: `2026-07-24T11:11:14.7654318-07:00`
Connection-instruction amendment validated: `2026-07-24T11:25:32.1567102-07:00`
P0 bookkeeping closed: `2026-07-24T11:31:54.4873062-07:00`
Timezone: `America/Los_Angeles` (`Pacific Standard Time`, UTC-07:00 at capture)
Operator: `Christopher Robertson`
Absolute campaign path:
`C:\Users\Chris\Documents\GitHub\Control_System\calibration\system_recalibration_001`

## Hardware-access statement

**No hardware connection was opened, no device command was sent, no device was
queried, no cable was moved, and no measurement acquisition was performed
during P0.** Physical inventory values were obtained from operator inspection,
operator reports of prior identification, installed-file metadata, and
document review. T660 firmware readback remains deferred to S0.

## Git and repository state

- Branch: `main`
- Working tree at P0 closure: **CLEAN**
- Git whitespace/diff validation: **PASS**
- `calibration/timing_calibration.csv`: absent
- `calibration/timing_offsets.yaml`: absent
- No active executable dependency on `Control_System_Archives` was found.
- No active T660-1 CH D to MIRcat DB9 pin-5 route was found.
- Arduino MUX configuration: disabled and excluded; direct wiring remains
  mandatory.

P0 review completed successfully. No hardware execution was authorized by
this record.


Selected PicoScope recipe:
`recipes/picoscope_settings_test.yaml`

Selected optical recipe:
`recipes/ndyag_alignment_10hz.yaml`


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

### PicoScope

- Physically confirmed model: `5244D`
- Physically confirmed serial: `10261`
- SDK identifier: `10261/0071`
- Bundled `ps5000a.dll`: file/product version `2.2.16.5110`
- PicoScope 7 T&M Stable: `7.2.19.9415`
- PicoScope 7 T&M Early Access: `7.2.24.9442`
- Installed SDK-lib `ps5000a.dll`: `2.2.8.5060`
- Workflow driver search order selects the repository-bundled DLL before the
  installed SDK path.

### MIRcat

- Bundled `MIRcatSDK.dll`: file/product version `2.4.1.1`
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
- Firmware versions: **resolved during S0**. Both T660-1 and T660-2 reported
  `28E660-1-1.7`; full identity responses are preserved in
  `readbacks/S0/t660_identity_firmware.json`.

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

The configuration inventory check regenerated the inventory record. Its path
field was restored to the tracked repository convention.

## Related P0 records

- `manifests/p0_physical_inventory.md`
- `manifests/p0_python_environment.txt`
- `manifests/p0_blocker_table.md`
- `docs/MIRcat/daylight_db9_process_trigger_correspondence.md`

## Historical requirement before S0

This requirement was satisfied before the completed S0 execution. It is
retained only as historical context and is not an MS-01 prerequisite.
