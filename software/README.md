# Control-system software

The importable application is `software/control_app/`; tests, utilities,
dependencies, and packaging live beside it. From the repository root, install the
package once with `.venv\Scripts\python.exe -m pip install -e software`, then launch
with `.\run_gui.ps1` or `.venv\Scripts\python.exe -m control_app.ui.app`.

Scientific phase ordering, evidence status, and acceptance decisions do not belong
in the application. The application may load an explicitly promoted bundle from
`instrument/promoted_bundles/` and writes ordinary run packages under
`evidence/experiments/runs/`. A campaign imports such a run only through its approved
phase procedure and stable evidence identifiers.
