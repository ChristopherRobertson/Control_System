# HF-01 model acceptance criteria

Criterion version: `HF01-MODEL-RESIDUAL-v3`.

These rules govern the paired-demodulator validation records. Demodulator 0 is
the filter under test. Demodulator 1 is an order-one, minimum-time-constant
reference on the same signal input, oscillator, harmonic, external reference,
device clock, and installed output rate.

## Integrity and retained samples

- The reference-demodulator magnitude identifies every connected-stimulus run
  in acquisition order. An isolated threshold gap of at most eight native
  samples may be bridged; a longer gap is a separate run.
- The number and order of reference-gated runs must exactly match the three
  zero-offset carriers and every declared offset carrier.
- Test and reference timestamps are trimmed only to their common endpoint
  overlap. Every retained sample must then have an exact timestamp match, with
  no interior omission or nonmonotonic timestamp. Extra poll-boundary samples
  are reported for each stream.
- Node readbacks must retain the declared filter settings and common input,
  oscillator, harmonic, trigger, and rate. External master-clock and DIO0 PLL
  lock, no clipping or sample loss, PicoScope voltage/range margin, and final
  safe idle are mandatory.

## Transfer estimator and paired-pipeline delay

For each retained nonzero run, calculate
`R(f) = Z_test(f) / Z_reference(f)`. Each of the three zero-offset carrier
ratios is corrected for its resolved residual frequency with the readback model
before their complex gain is combined.

The filter model is `H_n(f) = [1 + i 2 pi f tau]^-n`, using installed order and
time-constant readbacks. The reference correction remains explicit:
`H_measured(f) = [R(f) / G] H_reference(f)`.

A paired HF2LI demodulator implementation may attach the same timestamp to
samples with a fixed sub-sample pipeline displacement. Exactly one constant
delay nuisance, `delta_pair`, is therefore estimated independently for each
anchor by weighted zero-intercept regression of raw phase residual on
`2 pi f`. It must satisfy `|delta_pair| <= 1 / installed_rate`. The corrected
response is `H_corrected(f) = H_measured(f) exp[-i 2 pi f delta_pair]`.

Raw and corrected phase, fitted delay, delay uncertainty, and one-sample bound
are all retained. The nuisance cannot change magnitude, cutoff, settling, or
overshoot and cannot include an arbitrary phase intercept. It is subtracted
from the measured test/reference 50% step-delay difference before group-delay
comparison.

## Acceptance limits

All of the following must pass for every primary anchor:

- all three model-corrected zero-offset complex gains agree within the larger
  of 5% and three combined standard uncertainties;
- magnitude residual at every retained offset is no greater than the larger of
  5% and three combined standard uncertainties;
- corrected phase residual at every retained offset is no greater than the
  larger of 5 degrees and three combined standard uncertainties;
- fitted cutoff differs from the readback prediction by no more than the
  larger of 10% and three combined standard uncertainties;
- normalized RMS corrected complex residual is at most 5%;
- the single paired-pipeline delay satisfies its one-native-sample bound;
- all six reference-identified step edges are evaluated without temporal
  smoothing; observed 1%-99% settling is at most 120% of prediction and
  absolute overshoot is at most 5%;
- rising/falling final-gain span is no greater than the larger of 5% and three
  combined standard uncertainties;
- corrected relative group delay differs from the test/reference model by no
  more than the larger of 5%, one native sample, and three combined standard
  uncertainties; and
- the intermediate positive/negative cutoff pair agrees in magnitude within
  5% and reverses measured filter phase within 5 degrees, with the same
  three-uncertainty alternatives.

## Boundary

Exactly the three declared primary anchors are used. No fourth model point or
physical parameter grid is authorized. A rejected acquisition remains
preserved and may be replaced once at the identical declared setting under a
new stable ID. A primary v3 anchor that still fails stops HF-01 for prospective
disposition. The PicoScope is the connected-voltage authority and is not used
as a cross-clock phase reference.

Timing-copy authority remains `HF01-TIMING-COPY-v3` and
`HF01-TIMING10-R5-001`. Signal Input 2 and reload-equivalence criteria are
applied only after model acceptance and computational selection.
