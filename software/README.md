# Spectroscope application

Install from the repository root with `.venv\Scripts\python.exe -m pip install -e software`.
Launch with `run_gui.ps1`, or `python -m control_app.ui.app` after installation.
Normal startup connects configured devices. For software inspection use
`python -m control_app.ui.app --offline`.

## Components

| Location under `control_app/` | Responsibility |
| --- | --- |
| `ui/` | Application shell and device-control pages |
| `measurement_host/` | Module discovery, scoped settings, output, ownership and shared UI |
| `measurement_modules/` | Experiment planners, acquisition adapters, processing and native storage |
| `devices/` | Instrument protocols and communication services |
| `workflows/` | Operational orchestration and public workflow interfaces |
| `paths.py` | Runtime resources and scientific output containment |

The host supplies independent single/dual settings, baselines, results and
cancellation to six experiment modules. See the
[module API](control_app/measurement_host/README.md) and
[operating procedures](../docs/README.md). Drivers and UI construction must not
connect hardware implicitly during tests. Real operations require exclusive
ownership until cleanup and native-data preservation finish.

## Resources and output

Runtime recipes, device identities and selected parameters live in
[`instrument/`](../instrument/README.md). Disconnected Phase Scan planning uses
[self-contained preview settings](../instrument/phase_scan_preview.md); connected
capabilities and actual readbacks govern acquisition. Electrical command delays
do not establish optical arrival times.

`control_app.paths` owns the external research-root setting. Use
`CONTROL_SYSTEM_RESEARCH_ROOT` or `instrument/storage.local.json`; see the
[root README](../README.md). Scientific writers validate destinations under that
root, create required folders, and report failures. Raw capture, command/readback
logs, analysis and plot exports are scientific output. Input selection is
independent of output routing. Shutdown diagnostics and ownership state use
application storage. Scientific evidence is not a startup dependency.

## Verification

From the repository root, run `python -m pytest software/tests -q`, with
`QT_QPA_PLATFORM=offscreen` for unattended Qt checks. Tests use synthetic records,
injected transports and isolated temporary research storage. They require no
experimental dataset. Native-format tests preserve supported field meanings,
array values and missing-data masks. Passing tests does not establish physical
safe state, optical timing or detector response.
