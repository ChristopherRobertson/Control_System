# Recipe-Driven Workflow UI

The **Workflows** tab discovers only the workflows listed in
`instrument/recipes/ui_workflows.yaml`. This explicit catalog prevents test scripts,
incomplete recipes, and timing-only files from appearing as runnable
experiments.

## Operator sequence

1. Select a workflow from the dropdown.
2. Review the preset device/timing settings and adjust the exposed parameters.
3. Press **Configure & Save**. The backend validates every value and writes an
   immutable `configured_workflow.json` snapshot under
   `evidence/experiments/runs/configured_workflows/`.
4. Confirm the laser-safety condition when required. **Run Configured
   Workflow** remains disabled until configuration succeeds.
5. Press **Run Configured Workflow**. The backend runs the validated settings
   saved by **Configure & Save**.
6. For a continuous workflow, use the catalog-defined **Stop / Safe Idle**
   action in the same tab.

Changing any adjustable value invalidates the saved UI state immediately. The
backend independently checks the current values, so a stale or modified client
cannot bypass the configure-before-run gate.

## MIRcat ownership

For every catalog workflow that requires MIRcat control, the manufacturer GUI
must be closed before Run. The Custom UI owns the single MIRcat SDK connection
and applies the saved QCL, wavenumber, current, pulse, trigger-mode, timeout,
and referenced timing/preset settings in the workflow's established safe
order. Applied settings and device readbacks remain part of the workflow run
artifacts.

## Adding a viable workflow

Add one catalog entry containing an existing backend `device_key` and
`command`, its fixed settings, its timing-recipe reference, and typed adjustable
parameters. No new dropdown wiring is required. A workflow should be added only
after its backend command is executable end-to-end and has safe shutdown/error
handling.
