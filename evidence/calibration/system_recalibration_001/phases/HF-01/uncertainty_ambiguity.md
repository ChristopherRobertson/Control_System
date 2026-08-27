# HF-01 uncertainty and ambiguity record

## Quantified electrical terms

The aggregation authority is `tables/hf01_uncertainty_acceptance.csv`; native
per-segment and per-offset uncertainties remain in the linked analysis JSON.
The principal retained terms are:

- PicoScope connected-amplitude measurement and range uncertainty rather than
  programmed AWG amplitude alone;
- within-condition carrier, step, offset, and zero-window repeatability;
- complex response residuals against the installed-order/time-constant model;
- the fitted paired-demodulator pipeline delay and its standard uncertainty;
- HF2LI node quantization and exact readback values;
- Signal Input 1 versus Signal Input 2 gain, phase, cutoff, settling, and noise;
- readout-rate-to-bandwidth margin and the measured immediately lower rate;
- PicoScope sample timing, imported MS-01/MS-02 path terms, loading, and
  retained common-path asymmetry; and
- configuration reload/revisit difference and observed electronic drift.

The v3 corrected complex RMS residuals were 0.00536%, 0.02415%, and 1.76739%
for the fast, intermediate, and slow anchors, each below the 5% limit. The
paired-pipeline corrections also remained below one installed sample interval.

## Selection ambiguity

The complete supported-space analysis produced unique retained decisions under
the prospective ranking and guard rules, so no boundary challenger was
invoked. This is distinct from the mandatory immediately-lower-rate checks,
which were acquired as planned and rejected because their rate-to-cutoff ratios
fell below 8.

Sweep and HRP share identical numeric settings but retain separate configuration
IDs and validity envelopes. This is an explicit alias, not an assumption that
their scientific requirements are interchangeable.

## Explicit unquantified/downstream terms

The exact installed detector-output interval, detector noise, final optical
scan-distortion tolerance, HRP precision and fastest accepted early feature,
and maximum biological record durations were not established by HF-01. These
terms are not replaced by zero uncertainty or literature estimates. DET-01,
DET-02, AR-01, and the applicable experiment plans remain the authorities.

The missing tee manufacturer markings/cable lengths and declined photographs
are retained as provenance limitations. Connected voltage measurements,
common-path endpoint behavior, and measured inter-input equivalence are the
electrical authorities within this phase.

The MbCO result is not an ambiguity: the fastest valid two-channel HF2LI
configuration is outside the mandatory 1 us envelope. A changed scientific
claim or different acquisition path is required.
