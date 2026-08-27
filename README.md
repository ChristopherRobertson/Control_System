# Pump-probe control system and unified thesis campaigns

This repository contains the control software and evidence architecture for a
thesis-level pump-probe program.

The repository is a monorepo with explicit boundaries:

1. `control_app/`, `recipes/`, and `software/` implement the control system.
2. `campaigns/` is the sole prospective phase/dependency authority across
   calibration, characterization, validation, HRP, and optional MbCO.
3. `instrument/` contains the promoted runtime-bundle interface.
4. `evidence/` is the default location for new immutable campaign records; the
   unified evidence registry preserves all completed legacy locations.
5. `references/` and `theory/` define external-reference and model boundaries.

The control application continues to launch with `python -m control_app.ui.app`.
`control_app.paths` preserves current configuration, recipe, run, and log locations
while supporting the unified hierarchy.

The authoritative repository boundary is documented in
`docs/repository_scope.md`. Generic UI runs under `runs/` are operational
records, not campaign evidence unless an approved phase explicitly imports
them. No hardware action is authorized merely because a recipe, workflow, or
plan exists.

The retained biological pump path contains a permanently mounted,
identity-bound Thorlabs ELL15 electronic iris and uses a Coherent WaveMaster as
the visible/near-IR wavelength working reference. Their hardware identities,
manufacturer sources, connection requirements, services, and qualification
boundaries are documented in `docs/Iris/` and `docs/WaveMaster/`. The iris is a
static optical conditioner and is never credited as a safety shutter or
finite-event control. The shared component and per-acquisition contract is in
`docs/opo_540_optical_configuration.md`.

The Newport 1918-R / 919P-010-16 average-power working reference is registered
in `hardware_configuration.yaml`; its source package and bounded OM-01
measurement authority are documented in `docs/Power_Meter/`.
