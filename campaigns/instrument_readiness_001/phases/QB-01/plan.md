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

For every retained externally triggered Phase-Scan condition, capture the sample
detector on PicoScope CHA and the reference detector on CHB under the accepted
CHD-to-EXT and CHD-to-Sweep-Active configuration. Treat CHB as the primary optical
witness and CHA as corroboration. Generate expected opportunities from the
configured and read-back T660-2 repetition rate, determine phase locally from
consecutive optical edges, retain missing positions, and exclude partial boundary
opportunities. Derive channel thresholds locally from baseline and pulse populations
with noise and saturation checks; no absolute voltage threshold is transferable
between wavenumbers, alignments, or electrical-trigger tests.

Classify a MIRcat optical omission only when an expected opportunity is absent from
both channels. Classify CHA-only and CHB-only observations separately as detector/
path discrepancies. Across wavenumber, module, current, pulse width, repetition
rate, duty, scan direction, scan position, and thermal history, report omission
fraction, local density/clustering, run lengths, reconstruction-interval coverage,
and correlations with pulse amplitude/width, saturation, Sweep Active state, and
source readbacks. Do not infer adequacy from a whole-scan average or maximum
strictly consecutive loss alone.

Mandatory deliverables:

- Synchronized MIRcat readbacks, trigger/DIO records, optical-meter data, module
  identities, operating mode, pulse settings, and all calibration links.
- Power/pulse/stability versus wavenumber, module/crossover behavior, warm-up
  and repeatability tables, saturation limits, uncertainty, and recommended
  operating envelope.
- Opportunity-level dual-channel classifications, local threshold/noise/saturation
  records, cluster and reconstruction-interval coverage statistics, detector/path
  discrepancy table, and a configuration-specific optical-omission envelope.
- Measured-versus-manufacturer capability table and safe shutdown record.

## `EXPERIMENTS.md` allocation and decision contract

QB-01 implements the source-output portions of `EXP-CAL-06`, `EXP-CAL-07`,
`EXP-CAL-09`, `EXP-CAL-14`, `EXP-CHAR-01`, `EXP-CHAR-02`, `EXP-CHAR-03`,
`EXP-CHAR-04`, `EXP-OPT-02`, and `EXP-OPT-06`.
Requested and read-back wavenumber, mode, rate, pulse/trigger settings, power, stability,
and module identity are configuration data. Acceptance is mode/window/power-specific;
unsupported transitions, unstable output, saturation, or unbounded uncertainty reject
that configuration. Unclassified opportunities or an optical-omission regime outside
the predeclared bound reject the affected configuration even when the aggregate loss
fraction appears small. Module/source service, firmware, operating mode, scan profile,
wavenumber window, repetition/pulse setting, alignment, detector path, trigger routing,
or metrology changes trigger
revalidation. This phase does not establish sample absorbance, timing zero, or detector
normalization, and it does not by itself freeze the reconstruction retry policy.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
