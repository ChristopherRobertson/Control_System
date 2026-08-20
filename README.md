# Pump-probe control and measurement campaigns

This repository contains the control software and evidence architecture for a
thesis-level pump-probe program.

Scientific work is organized in three layers:

1. `calibration/system_recalibration_001/` establishes instrument corrections,
   uncertainties, reference planes, qualified configurations, and promotion.
2. `characterization/system_characterization_001/` measures source, beam,
   spectral, temporal, sensitivity, stability, and reproducibility performance
   using promoted calibration inputs.
3. `experiments/` holds requirements-level horseradish-peroxidase and
   myoglobin-CO designs used to select the minimum instrument work. Numeric
   settings and executable campaigns are finalized from promoted results and
   the canonical theoretical notebook.

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
