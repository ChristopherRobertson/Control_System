# SV-02 recipe contract

Status: **DESIGN CONTRACT ONLY — NO EXECUTABLE RECIPE EXISTS**

The former sample-specific polystyrene and Mylar YAML files are retired. New
SV-02 recipes are generated only after the required calibration and earlier
characterization bundles exist and CH-00 has frozen the test grid.

## Required inputs before recipe authoring

- promoted or explicitly accepted SP-02 axis bundle;
- promoted DET-04 balance/normalization bundle;
- accepted AR-01 acquisition configuration and dwell/settling envelope;
- SV-01 FTIR records and authoritative polystyrene feature table;
- selected polystyrene alignment and holdout specimens/scans;
- independent Mylar reference and its accepted claim scope;
- accepted QCL range, direction, power, detector range, and environmental
  conditions;
- approved output directory under `evidence/characterization/system_characterization_001/phases/SV-02/`.

## Required experiment order

1. Freeze all settings, criteria, partitions, repetitions, and exclusions.
2. Acquire the polystyrene alignment partition.
3. Fit the declared correction model and freeze its coefficients, covariance,
   validity range, analysis version, and residual decision.
4. Acquire or reveal the polystyrene holdout partition and calculate holdout
   metrics without refitting.
5. Acquire Mylar in both directions and calculate independent validation
   metrics without refitting.
6. Restore safe state and produce the full SV-02 closeout package.

## Recipe requirements

Every executable recipe must identify `campaign_id`, `phase_id`,
`phase_run_id`, required bundle/configuration IDs, alignment/holdout role,
sample identity, scan direction, spectral window, step, dwell, repetitions,
HF2LI configuration, MIRcat settings, controls, artifact tables, acceptance
criteria, output paths, emission approval, and restoration procedure.

No biological sample, Mylar record, or holdout result may change the frozen
polystyrene alignment.
