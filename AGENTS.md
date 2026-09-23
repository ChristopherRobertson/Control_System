# Repository instructions

## Scope and storage

Keep this repository focused on spectroscope control software, its custom UI,
drivers, operational recipes, selected runtime parameters, tests and documentation.
Scientific data, acquisition metadata, fits, reports, figures and notebooks belong
under the configurable external research root in `control_app.paths`. Do not write
scientific outputs inside this repository or silently fall back here. Tests use
isolated temporary research storage and synthetic fixtures.

## Operational integrity

Preserve numeric operating values, units, device identities, safety constraints,
validity envelopes and native record compatibility. Research evidence is separate
from explicitly selected runtime bundles. Both registry and manifest must say
`PROMOTED` before a bundle is loaded; creating files does not authorize hardware.
Do not invent observations or qualification, overwrite original measurements, or
silently select new scientific parameters. Unknown optical timing and detector
response must remain explicit limitations.

Never connect devices, move hardware or energize outputs during software
verification. Use mocks, simulations and offline UI checks. Preserve the custom
UI's per-tab settings, output routing, cancellation, ownership and restoration.
Ownership lasts through safe cleanup and required native-data preservation.

## Implementation and documentation

Preserve unrelated working-tree changes and native research records. Keep required
runtime resources in this repository and document their current function and
validity directly. Software startup and automated tests must not depend on a
particular experimental run or external procedural document. Native readers may
accept supported schema versions without rewriting source files.

Update applicable READMEs and operating instructions with code changes. Keep links
resolvable, distinguish preview values from connected readbacks, and describe
current behavior without claiming physical qualification from software tests.
Run focused hardware-free checks appropriate to the changed behavior.

Do not add repository-authored hash-matching operational gates. Hashes may be used
for diagnostics; use stable IDs, paths, sizes, UTC timestamps, versions, device
identities and source records for provenance. Git and external tools retain their
normal integrity behavior.

## Current development scope

All existing, archived and future acquisitions are functionality tests until Christopher Robertson explicitly changes that status. No existing result is a runtime calibration or supports scientific/dissertation claims. Prioritize end-to-end experiment-tab functionality; characterization/calibration follows later. Preserve safety checks and unqualified limitations. The MUX is disabled future work and must not block direct-wired experiments. See docs/result_status.md.
