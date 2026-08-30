# MS-02.1 — installed PicoScope and dual-recorder branch transfer calibration

Campaign: `instrument-readiness-001`
Domain: `calibration`
Registry status: `planned`
Required dependencies: `MS-02`
Optional dependencies: `none`

This is the canonical phase plan. It does not authorize hardware, acquisition,
status changes, acceptance, or promotion. Universal execution, retention,
restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Why this supplemental phase is required

The immutable completed `MS-01` and `MS-02` phases established their recorded
channel/path and splitter-skew dispositions. They did not establish the complete
installed transfer function required by `EXPERIMENTS.md` when each sample and
reference detector is observed simultaneously by the HF2LI and PicoScope through
the actual tee/adapter/cable/termination network. This phase fills only that new
configuration-specific gap and never changes, extends, or reacquires the completed
phase results.

This phase owns the installed-configuration, PicoScope, and dual-recorder branch terms
of `EXP-CAL-01`, `EXP-CAL-02`, and `EXP-CAL-03` and supplies the branch/topology
evidence required by `EXP-VAL-07`.

## Measurement and reference planes

For each retained normal dual-detector and sample-detector/pump-detector timing
configuration, freeze a human-readable `configuration_id` containing detector,
amplifier, tee, adapter, connector, cable, termination, HF2LI input, PicoScope
channel, firmware/software, and routing identities. Measure from the detector or
qualified electrical source plane to the HF2LI and PicoScope receiver planes:

- branch loading, attenuation, reflection/ringing, bandwidth, and relative skew;
- PicoScope returned sampling interval/timebase behavior, amplitude scale,
  resolution/bandwidth mode, channel contribution, and uncertainty;
- external-trigger source, polarity, threshold/hysteresis, impedance, latency,
  pretrigger baseline, record length, segment loss, and overflow behavior; and
- change in detector output when the HF2LI and PicoScope are connected
  simultaneously versus the qualified single-destination controls.

Import the accepted `MS-01` channel/path and `MS-02` splitter correction terms by
stable evidence ID. Do not repeat their acquisition grids. Physical cable-length
equality is configuration provenance and never a timing calibration.

## Required native evidence and analysis

Retain configuration photographs/diagrams, identity/readback records, native
PicoScope captures, HF2LI records where applicable, source/reference captures,
returned timebase and overflow metadata, rejected/diagnostic attempts, and safe
restoration. Analysis must separate branch, receiver, and previously imported
channel/path terms; report frequency- and amplitude-dependent transfer, reflection
metrics, delay/skew, covariance, Type A/Type B contributions, combined uncertainty,
and closure residuals at every retained configuration.

## Acceptance, rejection, and scope boundary

Accept a configuration only when both destinations remain inside their qualified
input envelopes, the measured transfer and latency model closes within the
predeclared uncertainty criterion, trigger/pretrigger behavior is repeatable,
overflow/loss is reconciled, and reconnect/revisit results remain inside the
declared tolerance. Retain and cause-code every clipped, unstable, reflected,
mis-triggered, lossy, or out-of-envelope attempt. Failure rejects that
configuration or opens separately authorized bounded work; it does not alter
`MS-01` or `MS-02`.

The output is a machine-readable branch-transfer and PicoScope calibration bundle
with stable quantity IDs, reference planes, covariance, validity envelope, and
revalidation triggers. Revalidate after a detector/amplifier, tee, adapter, cable,
termination, HF2LI input mode, PicoScope channel/mode, external trigger, material
rewiring, service, or firmware/software change outside the recorded envelope.

Downstream consumers are `HF-01.1`, `MD-01`, `HF-02`, `DET-01` through `DET-04`,
`OP-01`, `CL-01`, `IR-01`, `E2E-01`, `RPT-01`, and every architecture using
PicoScope timing support. This phase does not establish detector optical
responsivity, biological time zero, pump/probe arrival, HF2LI filter response,
sample reset, or a final acquisition setting.

## Closeout

Closure requires retained/indexed evidence, criterion-by-criterion disposition,
restoration, `final_report.md`, and an indexed, manifest-linked,
reviewer-accepted `procedural_writeup.md` under
`docs/phase_record_contract.md` that documents WHY, the actual chronological HOW,
WHAT was observed, uncertainty, implications, limitations, and the source map.
