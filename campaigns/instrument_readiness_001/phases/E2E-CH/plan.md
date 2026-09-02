# E2E-CH — bounded nonbiological full-system demonstration

Campaign: `instrument-readiness-001`  
Domain: `characterization`  
Registry status: `planned`  
Required dependencies: `E2E-01, SV-02B, IR-01, PF-01, RP-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### E2E-CH — bounded nonbiological full-system demonstration

Run a composite nonbiological demonstration with bounded, configuration-tagged blocks
for slow scan and all five reconstruction methods: nanosecond and microsecond
wavelength-by-wavelength, repeated rapid-scan phase-delay, single-scan phase-delay, and
single-pump rapid/log scan-burst. Cover room-temperature and 77 K surrogate envelopes
where configuration terms differ, using one unchanged qualified iris configuration. Reuse
calibration FE-01/E2E-01 fault-recovery
evidence; do not repeat simulated failures unless the orchestration or
configuration has materially changed.

The OPO-540 block includes electronic-iris startup/ownership, accepted command/
readback, configuration foreign key, post-iris power, mismatch stop, unchanged-
setpoint audit, WM-01 replacement working-reference identity/settings/native status,
and restoration. The iris remains outside finite-event control.

Mandatory deliverables:

- Complete manifest, native Sample/Reference/DIO/source/readback data,
  calibration and characterization configuration IDs, axes, processing,
  startup/safe-stop/restoration records, and artifact audit.
- Predeclared expected result, observed agreement, uncertainty, and a readiness
  decision for biological method development.
- Native `(wavenumber,time)` coverage, reconstruction truth/residuals, missing-
  scan/sample, drift, heteroscedastic-noise, phase, direction, edge, filter-memory,
  interpolation, and identifiable-region tests for each method.

For each Phase-Scan method, exercise the accepted AR-01 coverage criteria using
both observed omissions and predeclared fault-injection cases. Record CHA sample and
CHB reference traces simultaneously, derive local thresholds, preserve the expected
opportunity grid, and verify that a dual-channel omission is distinct from a
one-channel detector/path discrepancy. Demonstrate all three repeat triggers:
consecutive dual-channel omissions, deficient reconstruction-interval coverage, and
excess whole-scan missing fraction.

Verify that each affected phase delay receives no more than three additional
attempts and stops early when the aligned valid regions collectively cover all
required reconstruction bins. Preserve every attempt. Align attempts with observed
Sweep Active timing, wavelength markers, and timestamps; retain valid original
regions, fill invalid regions from valid repeats at the same phase delay, and use
pulse-coverage weighting where multiple attempts are valid. The reconstruction must
retain the contributing acquisition and normalized contribution weight for every
region. A valid complete repeat may be selected, but an omission-free physical scan
must not be required.

Force at least one retry-exhaustion case and verify the exact
`INCOMPLETE_MISSING_PULSE_COVERAGE` disposition. The best-effort diagnostic output
must leave deficient regions as `NaN` or visibly flagged, label every table and plot
not for publication, and keep the run from being reported complete. Any silent use
of a deficient region or loss of attempt/bin provenance rejects the method.

## `EXPERIMENTS.md` allocation and decision contract

E2E-CH is the nonbiological validation owner for `EXP-CHAR-12`, `EXP-CHAR-13`,
`EXP-OPT-07`, `EXP-OPT-08`, `EXP-OPT-09`, `EXP-OPT-11`, `EXP-VAL-01`,
`EXP-VAL-02`, `EXP-VAL-03`, `EXP-VAL-04`, `EXP-VAL-05`, `EXP-VAL-06`, and
`EXP-VAL-07`. Each method/configuration is accepted or rejected separately against a
frozen truth, native coverage, loss/noise/fault set, uncertainty, and algorithm version;
no interpolation may manufacture unsupported regions. Hardware/path/topology/settings,
thermal envelope, schedule/coverage, optical-omission or stream-loss regime, retry/
merge policy, or algorithm changes trigger
revalidation. The phase does not establish biological equivalent-state reset, dose,
sample identifiability, peaks, fractions, lifetimes, or kinetics.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
