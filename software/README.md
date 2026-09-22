# Control-system software

The importable application is `software/control_app/`; tests, utilities,
dependencies, and packaging live beside it. From the repository root, install the
package once with `.venv\Scripts\python.exe -m pip install -e software`, then launch
with `.\run_gui.ps1` or `.venv\Scripts\python.exe -m control_app.ui.app`.

The desktop includes six measurement modules with single/dual pages, including
Phase Scan, plus MIRcat, T660-1, Nd:YAG, OPO Iris and Plotter: seventeen tabs.
Phase Scan's established implementation lives in `measurement_modules/phase_scan/`.
The old workflow/widget import paths remain aliases for existing callers. The
redundant Single Scan Phase Delay pair is no longer registered.
Device command routing, exclusive ownership and shutdown are shared; each
experiment owns its acquisition plan, data and saved settings.
The desktop opens one application device session in a background startup worker.
Tabs use its shared settings snapshot and do not discover hardware on activation.
Device writes and acquisition checks use live readbacks over the retained
connections; experiment ownership still protects blank/sample sequences. Only
application shutdown deinitializes and disconnects the pooled transports, after
the existing safe-state procedure. CLI workflows retain their original lifecycle.
Use **Instruments → Refresh connected settings** to refresh external changes or
retry an unavailable startup device. Missing readbacks remain explicit failures.
**Instruments → Recheck supported device choices** explicitly repeats capability
enumeration when needed, without reconnecting healthy devices.
HF2LI supported choices are enumerated once and retained in
`%LOCALAPPDATA%/ControlSystem/device_capabilities_v1.json`; current operating
settings are always read from hardware at startup. An absent or unusable optional
capability record triggers discovery, and acquisition still verifies the selected
settings. The first enumeration can take longer; it does not block Qt navigation.
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
