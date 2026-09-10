# Control-system software

The importable application is `software/control_app/`; tests, utilities,
dependencies, and packaging live beside it. From the repository root, install the
package once with `.venv\Scripts\python.exe -m pip install -e software`, then launch
with `.\run_gui.ps1` or `.venv\Scripts\python.exe -m control_app.ui.app`.

The desktop includes Phase Scan, Dual-Detector Phase Scan, twelve independent
experiment pages, and MIRcat, T660-1, Nd:YAG, OPO Iris and Plotter: nineteen tabs.
Device command routing, exclusive ownership and shutdown are shared; each
experiment owns its acquisition plan, data and saved settings.
The default Save Location is `evidence/experiments/runs/YYYY-MM-DD`, using the
local date. An explicitly chosen custom destination remains available on restart.

Independent measurement packages add their own single/dual tab pairs through
`measurement_modules/<experiment_id>/registration.py`; no central import edit is
needed. See the [repository architecture and parallel-development instructions](../README.md#control-application)
and the [frozen host API](control_app/measurement_host/README.md). The horizontal
tab bar's native scroll arrows keep every installed tab accessible for offline work while
hardware is owned. Hardware ownership is enforced at backend device entry points
and retained through safe restoration and data preservation.

Scientific phase ordering, evidence status, and acceptance decisions do not belong
in the application. The application may load an explicitly promoted bundle from
`instrument/promoted_bundles/` and writes ordinary run packages under
`evidence/experiments/runs/`. A campaign imports such a run only through its approved
phase procedure and stable evidence identifiers.
