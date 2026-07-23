# Pre-hardware provenance snapshot

Captured: 2026-07-22 (America/Los_Angeles; exact operator timestamp pending)

Historical snapshot: the worktree and branch below record the environment at
capture time. They were superseded after the calibration work was merged into
`C:\Users\Chris\Documents\GitHub\Control_System` on `main`; they must not be
used as active execution paths. See `post_merge_provenance.md` and freeze a new
execution snapshot immediately before hardware access.

## Repository

- Working tree: `C:\Users\Chris\Documents\GitHub\Control_System_timing`
- Campaign root: `calibration/20260722_complete_system_recalibration_001`
- Branch (read-only linked-metadata query): `UI-baseline`
- Commit: `016aa3fe936faa829171d853db49b86afebeb9d5`
- `git status --short`: empty (clean at capture)
- WSL limitation: `.git` points to `C:/Users/Chris/Documents/GitHub/Control_System/.git/worktrees/Control_System_timing`, which WSL Git does not resolve directly. Branch, commit, and status were obtained by explicit read-only `--git-dir` and `--work-tree` arguments. No Git metadata was changed.
- Protected repository modified: **no**

## Configuration hashes (SHA-256)

- `hardware_configuration.yaml`: `88c4d3bdc6280ac9bfe57d294d3c0403cd4cbb9174bb88068e46777195829cf2`
- `wiring_map.yaml`: `b412e8d4384329cdb6d29157c06c57bbe865e36a6b4a81d0891ab9d09b8a2048`
- `recipes/timing_calibration.yaml`: `9911b1df8bb4861b5ab851c5ddd77f88b3e07cbf3c8ff30317417e4b93eab491`
- `recipes/safe_idle.yaml`: `e9fd76d1e1df4ed7657b9685534d8fcea80619421b67bac16e13ce8c7b394837`
- `recipes/picoscope_settings_test.yaml`: `750100d3049b3f3f23c0f1c397fb4d24ab553a683b59241c95877ea04f3003c0`
- Full recipe hash list: `manifests/recipe_sha256.txt`

The recipe hash list was refreshed after the dependency migration from `runs/` to `calibration/` and again after removal of the obsolete T660-1 CHD/MIRcat DB9 pin-5 route. The safe-idle and PicoScope recipe contents were unchanged.

On 2026-07-23 the legacy Day 8 workflow, entry point, historical canonical timing outputs, and offset-derived Nd:YAG recipe snapshot were moved to `Control_System_Archives/archive/20260723_legacy_timing_measurements`. The active Nd:YAG recipe now uses the nominal 179830 ns target and is explicitly marked `UNCALIBRATED_NOMINAL_TARGET`.

## Software snapshot

- WSL Python: `3.12.3`
- WSL pip: `24.0`
- WSL kernel: `5.15.167.4-microsoft-standard-WSL2` on x86_64
- Control-system application version: no packaged version identified; commit above is the software identity.
- PicoScope driver/API runtime version: **unresolved; must be queried from the Windows driver/runtime without opening acquisition hardware before MS-01**.
- MIRcat SDK bundled DLL version: **unresolved; file/product version and active manufacturer GUI version required before MC-01**.
- HF2LI LabOne version: **unresolved; required before HF-01**.
- T660 firmware: **unresolved; safe readback required after S0 ownership/safe-idle gate**.

No simulated or dry-run result is hardware evidence.
