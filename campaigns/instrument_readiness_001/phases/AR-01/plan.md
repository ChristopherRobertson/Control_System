# AR-01 — joint scan-speed and HF2LI acquisition optimization

Campaign: `instrument-readiness-001`  
Domain: `characterization`  
Registry status: `planned`  
Required dependencies: `HF-01.1, MSW-01, HF-02, DET-02, DET-03, DET-04, QB-01, OG-01, OV-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### AR-01 — joint scan-speed/HF2LI acquisition optimization and optical validation

The 2026-08-26 reconstruction expands this phase. Freeze a deterministic candidate
rule before optical results and use a stable nonbiological target that is not Mylar.
Jointly select scan speed within the accepted installed-source envelope, window,
direction, HF2LI time constant,
order, output rate, range and phase, record length/padding, exclusions, SNR,
throughput, and data volume. For every tuple report native spacing
`scan_speed/output_rate`, retained-model lag/broadening, order-specific settling,
effective noise bandwidth, duration `window_width/scan_speed`, hysteresis,
clipping/range and loss/throughput margins, total uncertainty, and robustness.
Approximate `scan_speed*n*tau` or `scan_speed*sqrt(n)*tau` metrics must be labeled
model-derived and checked against HF-01. Enforce rate/bandwidth constraints. Select
one bounded speed envelope or named slow/high-resolution, normal analytical, and
rapid/stroboscopic modes; do not optimize noise at the expense of required features.

For single-scan and repeated rapid-scan Phase-Scan configurations, jointly evaluate
PicoScope sample interval/record length, local pulse-threshold behavior, reconstruction-
interval width, phase density, and bounded retry cost against the QB-01 omission
envelope and measured reconstruction bias. The configurable candidate policy starts
with a repeat at two consecutive dual-channel omissions, any interval below 90%
coverage, or a whole-scan missing fraction above 5%, with at most three additional
attempts per affected phase delay. Coverage equal to 90% passes. At the illustrative
2 MHz and 5 us candidate settings, ten opportunities occupy one interval, so one
omission passes and two fail. Test the combined criteria rather than treating
consecutive loss as the sole gate, and retain all tested alternatives and rejection
reasons. No candidate becomes final until the measured source, timing, detector,
throughput, and reconstruction envelope supports it.

Using an optically stable nonbiological signal and the qualified HF2LI setup,
validate each of the five reconstruction methods across the normal dual-detector and
temporary timing/IRF topologies: wavelength-by-wavelength, repeated rapid scan,
nanosecond fixed-wavelength, microsecond fixed-wavelength, and single-pump
phase-shifted rapid/log scan burst. Import the HF-01 PicoScope-AWG complex transfer, step, range,
rate, noise, channel-equivalence, and uncertainty results; do not repeat its
electrical parameter grid. For the Mylar continuous sweep, compare the selected
speed/filter setting with one slower quasi-static reference in both directions,
because that optical comparison is required to measure scan peak shift and
broadening. For each room-temperature/77 K HRP-C-CO and MbCO fixed-wavenumber configuration, acquire
the selected setting only using one controlled nonbiological point transition
and that workflow's retained record envelope. Compare observed settling,
filter memory, and Sample/Reference response with the HF-01/DET-03 prediction.
Add one bracketing biological setting only when the prediction residual fails,
the observed result lies inside its acceptance guard band, or an installed
source/detector effect cannot otherwise be separated. A common numeric setting
remains acceptable only with the explicit HF-01 equivalence record and separate
configuration IDs.

Mandatory deliverables:

- Native Sample/Reference/full-DIO streams, complete settings/readbacks,
  controlled step/dwell series, and environmental records.
- Imported-versus-observed response residuals, scan-direction shift/broadening,
  minimum justified dwell, filtering/averaging rules, covariance behavior,
  uncertainty, and any predeclared bracket-escalation decision.
- Phase-Scan pulse-coverage and retry candidate table, reconstruction-bias and
  throughput tradeoff, accepted local-threshold and capture envelope, and explicit
  rules for combined-attempt completion and retry exhaustion.
- Separate frozen configuration IDs for every retained architecture linked to
  their permitted scan/record envelopes, including filter transfer, effective
  noise bandwidth, settling, temporal attenuation/bias, and any explicit
  biological equivalence alias.

## `EXPERIMENTS.md` allocation and decision contract

AR-01 is the joint optimization owner for `EXP-CAL-06`, `EXP-CAL-07`,
`EXP-CAL-13`, `EXP-CHAR-03`, `EXP-CHAR-04`, `EXP-CHAR-07`, `EXP-CHAR-13`,
`EXP-OPT-02`, `EXP-OPT-05`, `EXP-OPT-06`, and `EXP-OPT-08`. It must retain native
coverage and readbacks, full candidate/rejection tables, prediction residuals,
uncertainty, direction/history, filter memory, loss, and data-volume margins. A setting
is accepted only for its measured mode/condition/topology and frozen claim envelope;
source, detector, topology, filter/rate/range, scan schedule, timing, or algorithm changes
trigger revalidation. Probe carrier rate is optimized independently of the 10 Hz pump
maximum. This phase does not establish chemical time zero, sample recovery, dose,
kinetics, or model identifiability in a biological sample.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
