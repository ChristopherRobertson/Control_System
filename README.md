# IR spectroscope control system

All acquisitions are **functionality tests**, with no runtime calibration or scientific claims until explicit operator release. Current priority is end-to-end app workflows. See [result status](docs/result_status.md). MUX work is deferred; current experiments use direct detector and marker connections.

This repository contains the custom instrument application, device services,
operational recipes, selected operating parameters, tests, and software documentation.
Scientific data and analysis belong in the configured external System_Research directory.

## Start the application

```powershell
.venv\Scripts\python.exe -m pip install -e software
.\run_gui.ps1
```

Install `software/requirements-ui.txt` if Qt is not installed. The normal launcher
connects installed devices; use `--offline` with the module entrypoint for a UI-only
session without hardware startup.

```powershell
.venv\Scripts\python.exe -m control_app.ui.app --offline
```

Single and Dual detector modes provide six measurement pages each: Slow Scan,
Fixed Wavenumber, Nanosecond Stroboscopy, Microsecond Stroboscopy, Rapid Scan
Phase Delay, and Phase Scan. MIRcat, T660-1, Nd:YAG, OPO Iris, and Plotter follow.
All 17 pages stay instantiated; 11 are visible in each detector mode. Switching
modes preserves settings, ownership, active work, and each page's destination.
See [operating documentation](docs/README.md) for individual workflows.

## Repository contents

| Location | Purpose |
| --- | --- |
| `software/control_app/` | Custom UI, measurement modules, drivers and acquisition services |
| `software/tests/` | Software regressions and small synthetic fixtures |
| `software/tools/` | Standalone operational utilities |
| `instrument/` | Hardware configuration, wiring, recipes, schemas and selected runtime bundles |
| `references/` | Manufacturer manuals, certificates and required SDK files |
| `docs/operating_procedures/` | Current operator instructions |

## Research output

This installation uses `C:\Users\Chris\Documents\UC Davis\PhD_Work\System_Research`.
`control_app.paths` resolves storage once at application startup, in this order:

1. `CONTROL_SYSTEM_RESEARCH_ROOT` environment variable.
2. `research_root` in the ignored `instrument/storage.local.json` installation file.
3. `<user home>/Documents/System_Research` on other installations.

The root must be absolute and outside this repository. Restart the application
after changing it. Scientific destinations must remain inside this root; invalid
paths and write failures are reported without falling back into the software tree.
New measurement folders default to `experiments/runs/YYYY-MM-DD/<tab title>/`.
Custom per-page destinations must also be under the research root. Invalid saved
destinations remain visibly flagged until corrected. Each operation freezes its
own destination. Nd:YAG device output uses the dated root without a tab-name folder.

Dated save-folder preferences always use today's local date, including after
restart and midnight rollover. Browsing to a past dated output folder selects
the corresponding folder for today. Undated custom folders retain their layout;
active operations keep their frozen destination and existing data are not moved.

`CONTROL_SYSTEM_RUN_ROOT` and `CONTROL_SYSTEM_LOG_ROOT` remain supported as
subdirectory overrides within the research root. Command logs and device readbacks
live in `experiments/logs/` because they can contain measurement values. Ordinary
UI shutdown diagnostics use `%LOCALAPPDATA%/ControlSystem/logs/`. Ownership and
recovery coordination use the shared `%PROGRAMDATA%/ControlSystem/` location.

Native measurement records, analysis exports, calibration fits, scientific figures,
notebooks and reports belong in System_Research. Input files may be opened anywhere;
export destinations are checked. Scientific records retain their native schemas and
values. Corrections and derived analyses must preserve their source records.

## Operating parameters

The UI reads `instrument/hardware_configuration.yaml`, `instrument/wiring_map.yaml`,
and `instrument/recipes/`. Device identities, timing values, electrical limits,
validity conditions and unqualified states are operational constraints.
Only explicitly selected bundles marked `PROMOTED` in both the runtime registry
and manifest are loaded. The registry currently contains no promoted bundles.
See [runtime configuration](instrument/README.md) for the selection procedure.

Real device commands require exclusive ownership of the coupled instrument.
Restoration and native-data preservation must complete before ownership is released.
A lost process does not establish safe idle. Use **Review instrument recovery…**
after physical restoration and preservation have been verified. External vendor
software does not participate in this lock.

## Verification

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.venv\Scripts\python.exe -m pytest software/tests -q
```

Tests use an isolated temporary research root with simulated or mocked devices.
Native-format checks use self-contained synthetic records. Software tests do not
establish physical safe state, optical validity or real-device performance.
