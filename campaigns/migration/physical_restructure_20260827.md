# Physical unified-layout migration — 2026-08-27

This migration physically separates software, installed-instrument authority,
campaign planning, evidence, references, theory, and shared documentation while
keeping them in one Git repository. It does not represent a fresh scientific start.

## Preservation anchors

- Original campaign reconstruction: branch `codex/pre-unified-layout-20260827`,
  commit `654f896`.
- Pre-physical unified overlay: branch `codex/unified-campaign-layout`, commit
  `9a8bb99`.
- Physical migration branch: `codex/physical-unified-layout`.
- The operator also retained an external full-repository backup before this work.

These references are provenance and recovery aids, not hash-matching operational
gates.

## Canonical relocation map

| Previous path | Canonical path |
| --- | --- |
| `control_app/` | `software/control_app/` |
| `tests/` | `software/tests/` |
| `tools/` | `software/tools/` |
| `config/` | `instrument/schemas/` |
| `recipes/` | `instrument/recipes/` |
| `hardware_configuration.yaml` | `instrument/hardware_configuration.yaml` |
| `wiring_map.yaml` | `instrument/wiring_map.yaml` |
| `runs/` | `evidence/experiments/runs/` |
| `logs/` | `evidence/experiments/logs/` |
| `calibration/system_recalibration_001/readbacks/<phase>/` | `evidence/calibration/system_recalibration_001/phases/<phase>/` |
| `calibration/system_recalibration_001/manifests/` | `evidence/calibration/system_recalibration_001/phases/P0/` |
| `characterization/system_characterization_001/readbacks/<phase>/` | `evidence/characterization/system_characterization_001/phases/<phase>/` |
| calibration/characterization plans and analyses | `campaigns/instrument_readiness_001/` |
| biological requirement briefs | `campaigns/hrp_001/` and `campaigns/mbco_cryo_001/` |
| `docs/<instrument>/` | `references/manuals/<instrument>/` |
| MIRcat SDK, device drivers, and `vendor/picosdk/` | `references/sdk/` |
| calibration certificates | `references/certificates/` |

Historical `repository_state.txt` files and native acquisition payloads may contain
the old path spellings because those strings describe the state observed when a
phase ran. Canonical registries, phase manifests, artifact indexes, active scripts,
configuration, and procedures use the new paths.

## Phase-package preservation inventory

The directory moves included tracked and Git-ignored native raw data. File counts and
byte totals below were recorded before the move. The migration audit confirms minimum
stable-file counts and phase statuses, and reports byte-size deltas caused by path and
provenance metadata edits for information only; byte totals are not an operational gate.
Content hashes are intentionally not used as an operational requirement.

| Phase | Files | Bytes | Recorded status |
| --- | ---: | ---: | --- |
| S0 | 9 | 180,904 | historical record; no phase manifest |
| MS-01 | 233 | 289,330,489 | historical record; no phase manifest |
| MS-02 | 226 | 286,810,552 | historical record; no phase manifest |
| T2-01 | 1,898 | 940,518,053 | historical record; no phase manifest |
| T1-01 | 3,056 | 1,975,959,772 | historical record; no phase manifest |
| PT-01 | 657 | 1,372,656,279 | PASS |
| MC-01 | 108 | 4,127,881 | COMPLETE |
| TR-01 | 17 | 37,381 | PASS |
| OM-01 | 46 | 174,874 | PASS_COMPLETE_QUALIFIED_BOUNDED |
| HF-01 | 561 | 2,682,968,954 | PASS |
| WM-01 | 40 | 90,139 | IN_PROGRESS |
| CH-00 | 22 | 36,468 | PASS |

P0 material was preserved as a phase package rather than being treated as a generic
manifest directory. Existing statuses remain unchanged, and WM-01 resumes in the
same phase package.
