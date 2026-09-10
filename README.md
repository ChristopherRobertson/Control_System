# IR spectroscope control system and thesis campaigns

This repository is a single, structured workspace for instrument-control software,
campaign procedure development, acquisition evidence, runtime configuration, and
the scientific references needed to connect them. The boundaries are physical, but
Git versions them together so the control system can consume promoted results
without copying data between repositories.

## Repository map

| Directory | Responsibility |
| --- | --- |
| `software/` | GUI application, device services, tests, tools, dependencies, and packaging |
| `instrument/` | Installed hardware/wiring authority, runtime recipes, schemas, and explicitly promoted bundles |
| `campaigns/` | Unified phase registry plus self-contained phase packages containing plans, readbacks, raw data, analysis, reports, and promotion work |
| `evidence/` | Generic GUI/operational experiment runs and cross-campaign catalogs that do not belong to a registered campaign phase |
| `references/` | Manufacturer manuals, SDKs/drivers, certificates, and their registry |
| `theory/` | Versioned model/notebook derivatives and validation fixtures |
| `docs/` | Repository architecture, operating procedures, and the phase-record contract |
| `.archive/` | Inactive source documents retained intact under their original relative paths |

`campaigns/master_sequence.md` is the authoritative human instruction set.
`campaigns/phase_registry.yaml` is its machine-readable ordering, status, and
hard-dependency companion. Calibration and characterization remain useful
scientific domains, but they are phases in one instrument-readiness graph.

Completed evidence is stored directly in the matching canonical phase package under
`campaigns/<campaign>/phases/<phase-id>/`, beside the plan and phase metadata. The
relocation did not create new acquisitions, change measurement values, or change
phase status.
`campaigns/registries/evidence_locations.yaml` is the stable lookup authority. The
archived historical record at
`.archive/campaigns/migration/self_contained_phase_packages_20260827.md` documents
the phase-package relocation and preservation audit. Archived migration and
experiment-overview documents are historical only; current campaign authority
remains in the master sequence, phase registry, campaign requirements, methods,
and phase packages.

## Control application

For the existing local environment:

```powershell
.venv\Scripts\python.exe -m pip install -e software
.\run_gui.ps1
```

After the editable install, the original module command also works from the
repository root:

```powershell
.venv\Scripts\python.exe -m control_app.ui.app
```

The GUI reads `instrument/hardware_configuration.yaml`,
`instrument/wiring_map.yaml`, and `instrument/recipes/`; it writes ordinary runs and
logs below `evidence/experiments/`. Runtime scientific values may come only from a
bundle explicitly marked `PROMOTED` in both the promoted-bundle registry and its
manifest. A plan, recipe, directory, or registry row never authorizes hardware or
changes scientific status.

The desktop is composed by the small `software/control_app/measurement_host/`
host. **Phase Scan** and **Dual-Detector Phase Scan** retain their scientific
workflows, native files, timing and review controls. Additional measurements
register their own pair through
`software/control_app/measurement_modules/<experiment_id>/registration.py`.
Discovery sorts descriptors by display order and stable ID, isolates optional
import/construction failures, and adds the pairs before the unchanged MIRcat,
T660-1, Nd:YAG, OPO Iris and Plotter device-tab order. A workspace selector and
scrolling tab bar keep every tab reachable. Offline analysis, simulation and
plan editing can continue while another tab owns the instrument.

The [version 1 module API](software/control_app/measurement_host/README.md)
specifies the descriptor, two lifecycle handles, scoped context, frozen operation
inputs, independent preference/output namespaces, reusable scientific-adapter
presentation and standalone sample-selection interchange. This task owns the
host, discovery package, shared shell, state machine, service boundaries and
existing regressions. Each of the six feature tasks owns only its named package,
its tests and its operating procedure. Features must not import sibling features
or edit a central import list. This is a measurement host, not a user-authored
workflow language or scheduler.

All real backend connections and commands require exclusive ownership of the
coupled spectrometer. On Windows the default OS lock and durable ownership
records live under `%PROGRAMDATA%/ControlSystem/`; all app/task processes and
checkouts use that same location. Access failures block hardware rather than
falling back to a different lock. In-memory tokens prevent late callbacks from
releasing another operation. Manual alignment/emission sessions retain ownership
until explicit cleanup; an acquisition retains it through restoration and native
preservation. Loss of a process or lock never proves physical safe idle. Faults
retain their owner/history records and require explicit evidenced recovery using
**Review instrument recovery…** after physical restoration and data preservation
have been verified. The procedure does not restart an experiment. External vendor
software does not participate in this lock; release its device sessions before
using the application.

The Phase Scan adapter migrates only the old regular/dual settings and HF2 choice
keys into `measurements/phase_scan/<mode>/v1/`, preserving the old values. New
feature runs use the frozen destination
`<save_root>/measurements/<experiment_id>/<mode>/<run_uuid>/`; existing Phase Scan
native directory names and schemas remain unchanged. Selected instrument
calibration is loaded only through promoted-bundle access. Accepted sample
spectral selections are independent versioned data with producer, condition,
source and uncertainty; they do not require the Slow Scan package to be installed.

For parallel feature development, use the checkpoint branch
`measurement-host-v1` (also `codex/shared-measurement-host` and the integrated
commit on `main`) as
the baseline for all six worktrees. The starting checkout was clean at `5b89bcb`,
the merge containing the current working Phase Scan code and fixes; the shared
foundation is a descendant of that merge. Do not branch features from the older
pre-Phase-Scan history. For example:

```powershell
git worktree add -b codex/steady-state-slow-scan ../Control_System_slow_scan measurement-host-v1
$env:QT_QPA_PLATFORM = 'offscreen'
.venv\Scripts\python.exe -m pytest software/tests -q
```

Each worktree needs its own editable installation/environment, or must launch
from its `software/` directory with an explicitly selected Python runtime.
`run_gui.ps1` already launches from that directory. Once feature packages pass
their tests, integrate their package/test/procedure commits onto this foundation
and rerun the suite; discovery requires no shell integration changes. Two
retained local fixture directories used by existing replay tests are ignored by
Git (`single_detector_ftir_20260906T203723_580408Z` and
`exploratory_air_checkout_20260902T224505_935642Z`, under
`evidence/experiments/runs/`). Preserve their originals; a separate checkout may
use local read-only fixture copies or links for those optional replay tests.

Foundation validation uses simulated instruments, synthetic registrations, Qt
offscreen interaction, Windows subprocess contention/crash tests and retained
native replay only. Live SDK shutdown/recovery behavior, sustained simultaneous
detector throughput and physical safe-state readbacks require commissioning on
the installed instrument. Code tests do not qualify scientific measurements,
change campaign status or promote calibration.
The completed foundation passed **755 tests**, **24 subtests**, and both read-only
UI boundary/close checks. The three skipped tests are the pre-existing obsolete
administrative-gate cases; the two warnings come from existing diagnostic plots
with no labeled artists. The retained 322-scan replay still checks absolute and
delta absorbance within `1e-14`, including the same 174 unsupported cells.

The [default wiring diagram](instrument/default_wiring_state.md) shows the
detector split connections: each signal passes through a female-to-female BNC
adapter and a male-to-two-female BNC tee. Sample feeds HF2LI Signal 1 In (+)
and PicoScope CHA; reference feeds HF2LI Signal 2 In (+) and PicoScope CHB.
T660-1 supplies the probe/reference train and clocks T660-2's event input.
T660-2 executes FIRE, Q-switch, and MIRcat Process Trigger trains/frames and
supplies the separate 10 MHz clock distribution. Sweep Active on MIRcat DB9
pin 2 feeds HF2LI DIO21 and PicoScope EXT. Both T660 D outputs and HF2LI DIO1
are unwired.

The repository boundary and authority rules are in `docs/README.md`, and the
shared acquisition/evidence rules are in `docs/phase_record_contract.md`.

Every phase also requires a separate thesis-quality `procedural_writeup.md` before
documentation closeout. The governing standard and reusable template are
`docs/phase_record_contract.md` and
`campaigns/templates/phase_record/procedural_writeup.template.md`. The writeup
explains WHY, HOW, WHAT, and the defensible implications/caveats/claims; it does not
replace machine-readable evidence or the formal `final_report.md` decision record.
