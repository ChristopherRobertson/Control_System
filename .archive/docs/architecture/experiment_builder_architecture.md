# Constrained experiment builder

The new `control_app.experiments` package is the migration target for UI and
backend orchestration. It accepts a versioned data definition, validates it
against a device capability registry and cross-device constraints, compiles a
validated immutable plan, and executes that plan through adapters.

The builder lifecycle is create/load, validate, save, configure, run/stop,
process, and export. The Qt panel renders `fields` generically; adding a valid
definition does not require a new widget, tab, state-machine branch, or
device-key dispatch branch.

The Qt panel is implemented in `software/control_app/ui/widgets/experiment_builder_widget.py`
and appears as the first tab in the desktop application. It renders typed fields,
supports advanced YAML editing, saves definitions and immutable plans, and
provides processing/export controls. Run remains visibly gated until an
`ExperimentEngine` containing explicitly registered device adapters is injected;
opening the panel, loading files, validating, and configuring never access hardware.

## Inventory and migration map

- Executable workflows currently live in `software/control_app/workflows`: MIRcat status,
  detector alignment, sweep/fast sweep, HF2LI recording, Nd:YAG alignment,
  PicoScope settings, Arduino diagnostics, and timing calibration.
- `instrument/recipes/ui_workflows.yaml`, `selectable_workflows.py`, and
  `state_machine.py` are the existing recipe-command/device-key coupling points.
- `*_widget_commands.py` and `ui_command_router.py` are the device command
  handlers. Device SDK and serial behavior is correctly isolated mostly in
  `software/control_app/devices/*_service.py` and should be wrapped by capability
  adapters rather than moved into definitions.
- Timing recipes flow through `timing_recipe_manager.py` into `T660Service`.
  Existing timing recipes remain authoritative during incremental migration.
- HF2LI/MIRcat services expose configuration and readbacks. PicoScope applies
  recipe capture settings. Processing/export currently includes
  `labone_plotter_processor.py` and `sweep_export.py`; these can be registered
  as named processors without changing the compiler.
- Arduino MUX code is inactive/bypassed per configuration and is not registered
  as an experiment capability.
- Existing workflow implementations and tests remain referenced. Nothing is
  safe to archive yet; no files were moved to the external archive.

## Safety boundaries

MIRcat SDK ownership is explicit. External Process Trigger is registered but
unavailable until experimentally confirmed. T660-1 CHD and reserved MIRcat DB9 pin 5 (Laser Output On/Off),
6, and 8 cannot be selected. MIRcat DB9 1-3 DIO mapping is unavailable until
confirmed. Every valid definition supplies stop, abort-to-safe, and failure
recovery behavior. The standing physical meaning of `default wiring restored`
is defined in `instrument/default_wiring_state.md` and is not a recurring operator
confirmation unless the operator reports a change.
cleanup actions. Tests use recording adapters only and never open hardware.

## Incremental adoption

Existing workflows remain operational while their service calls are mapped to
`ServiceCapabilityAdapter` operations. Processing functions should be added to
`ProcessingRegistry` under stable names. Once feature parity is verified on
approved hardware, the old selector/router/state-machine path can be archived
under the separately designated archive directory in a dedicated change.
