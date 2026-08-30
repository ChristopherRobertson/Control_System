# QB-01 — MIRcat probe-source characterization

Campaign: `instrument-readiness-001`  
Domain: `characterization`  
Registry status: `planned`  
Required dependencies: `MD-01, MSW-01, HF-02, DET-02, CH-00.1`
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### QB-01 — minimal MIRcat probe-source characterization

Characterize only the module(s) intersecting the retained Mylar/polystyrene
carbonyl window and combined 1885-1980 cm^-1 biological region. In the Mylar
window use the lower edge, selected feature, and upper edge of the accepted
continuous sweep. In the biological region use the merged HRP/MbCO band and
off-band anchors; coincident anchors are one condition. Test the single sweep
operating point plus every CH-00.1-retained slow, repeated rapid,
fixed-wavelength, and scan-burst source mode.
Measure a module transition only if a retained window crosses one. Reuse SP-02
axis calibration and MSW-01 timing; do not redetermine them or survey unused
modules/ranges.

Mandatory deliverables:

- Synchronized MIRcat readbacks, trigger/DIO records, optical-meter data, module
  identities, operating mode, pulse settings, and all calibration links.
- Power/pulse/stability versus wavenumber, module/crossover behavior, warm-up
  and repeatability tables, saturation limits, uncertainty, and recommended
  operating envelope.
- Measured-versus-manufacturer capability table and safe shutdown record.

## `EXPERIMENTS.md` allocation and decision contract

QB-01 implements the source-output portions of `EXP-CAL-06`, `EXP-CAL-07`,
`EXP-CAL-09`, `EXP-CAL-14`, `EXP-CHAR-01`, `EXP-CHAR-02`, `EXP-CHAR-03`,
`EXP-CHAR-04`, `EXP-OPT-02`, and `EXP-OPT-06`.
Requested and read-back wavenumber, mode, rate, pulse/trigger settings, power, stability,
and module identity are configuration data. Acceptance is mode/window/power-specific;
unsupported transitions, unstable output, saturation, or unbounded uncertainty reject
that configuration. Module/source service, firmware, operating mode, scan profile,
wavenumber window, repetition/pulse setting, alignment, or metrology changes trigger
revalidation. This phase does not establish sample absorbance, timing zero, or detector
normalization.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
