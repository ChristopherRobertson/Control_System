# Pre-hardware provenance snapshot

Captured: 2026-07-22 (America/Los_Angeles; exact operator timestamp pending)

Historical snapshot: the worktree and branch below record the environment at
capture time. They were superseded after the calibration work was merged into
`C:\Users\Chris\Documents\GitHub\Control_System` on `main`; they must not be
used as active execution paths. See `post_merge_provenance.md` for the active
repository location.

## Repository

- Working tree: `C:\Users\Chris\Documents\GitHub\Control_System_timing`
- Campaign root at capture: `calibration/20260722_complete_system_recalibration_001`
- Branch (read-only linked-metadata query): `UI-baseline`
- `git status --short`: empty (clean at capture)
- WSL limitation: `.git` points to linked Windows worktree metadata that WSL
  Git does not resolve directly. Branch and status were obtained by explicit
  read-only repository/worktree arguments. No Git metadata was changed.
- Protected repository modified: **no**




On 2026-07-23 the legacy Day 8 workflow, entry point, historical canonical timing outputs, and offset-derived Nd:YAG recipe snapshot were moved to `Control_System_Archives/archive/20260723_legacy_timing_measurements`. The active Nd:YAG recipe now uses the nominal 179830 ns target and is explicitly marked `UNCALIBRATED_NOMINAL_TARGET`.

## Software snapshot

- WSL Python: `3.12.3`
- WSL pip: `24.0`
- WSL kernel: `5.15.167.4-microsoft-standard-WSL2` on x86_64
- Control-system application version: no packaged version identified.
- PicoScope software and driver-library versions were inventoried during P0.
  The active unit/runtime identity is recorded when MS-01 opens the PicoScope;
  it is not a separate pre-execution requirement.
- MIRcat SDK bundled DLL version: **unresolved; file/product version and active manufacturer GUI version required before MC-01**.
- HF2LI LabOne version: **unresolved; required before HF-01**.
- T660 firmware: **unresolved; safe readback required after S0 ownership/safe-idle gate**.

No simulated or dry-run result is hardware evidence.
