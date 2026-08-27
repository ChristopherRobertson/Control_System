# HF-01 model acceptance criteria (superseded v2)

Criterion version: `HF01-MODEL-RESIDUAL-v2`.

These rules govern the dual-demodulator model-validation records. Demodulator 0
is the filter under test. Demodulator 1 is a wideband reference configured on
the same HF2LI signal input, oscillator, harmonic, external reference, device
clock, and output-sample grid. The synchronized complex ratio cancels source
phase, host-clock offset, and command latency without requiring a phase model
for the PicoScope or T660 cable paths.

## Data integrity and electrical safety

- Every anchor contains one connected-zero interval, three independent rising
  carrier steps, three independent falling carrier steps, and all declared
  offset-carrier conditions.
- Demodulators 0 and 1 must have exact matching timestamps for every retained
  complex-ratio sample.
- Both demodulators must retain the declared order, time constant, output rate,
  oscillator, harmonic, input assignment, and trigger readbacks.
- PicoScope monitor and HF2LI records must have monotonic timestamps, complete
  settings, no overflow or overload, and no unexplained missing segment.
- Connected voltage must remain inside `source_load_voltage_envelope.md`.
- The external master clock and DIO0 reference PLL must be locked before and
  after every anchor. All temporary outputs return to safe idle after each run.
- Any integrity or voltage failure rejects the acquisition; it does not create
  an additional model point.

## Dual-demodulator transfer estimator

For each retained nonzero segment, calculate the timestamp-aligned ratio
`R(f) = Z_test(f) / Z_reference(f)`. Normalize it by the mean zero-offset carrier
ratio. The predicted ratio is

`R_model(f) = H_test(f) / H_reference(f)`,

where `H_n(f) = [1 + i 2 pi f tau]^-n` and both predictions use installed node
readbacks. The wideband reference correction remains explicit in every row; it
is never silently treated as unity.

Any resolved residual frequency at the zero-offset carrier is included in the
same readback-based transfer calculation before the three replicate ratios are
combined; the normalization therefore cannot conceal residual detuning.

The reconstructed filter-under-test response is
`H_measured(f) = R_measured(f) H_reference(f)`.

## Acceptance limits

All of the following must pass for each primary anchor after uncertainty
propagation:

- all three zero-offset carrier-ratio replicates agree within the larger of 5%
  and three combined standard uncertainties;
- normalized magnitude residual at every retained frequency is no greater than
  the larger of 5% and three combined standard uncertainties;
- phase residual at every retained frequency is no greater than the larger of
  5 degrees and three combined standard uncertainties;
- fitted cutoff differs from the readback-based prediction by no more than the
  larger of 10% and three combined standard uncertainties;
- normalized RMS complex residual across retained frequencies is at most 5%;
- rising/falling final-gain difference is no greater than the larger of 5% and
  three combined standard uncertainties;
- the reference-demodulator transition identifies the input edge for each step;
  measured 1%-99% settling is no more than 120% of prediction after that delay
  correction, and absolute overshoot is at most 5%;
- measured relative group delay differs from the test/reference model difference
  by no more than the larger of 5%, one synchronized output-sample interval, and
  three combined standard uncertainties; and
- the intermediate positive/negative cutoff offsets agree in magnitude within
  5% and their measured phases reverse sign within 5 degrees, each with the
  same three-uncertainty alternative.

The PicoScope remains the connected-voltage authority. It supplies amplitude,
offset, clipping, and source-load evidence; it is not used to establish the
complex phase relation, which is wholly identified inside the HF2LI clock
domain.

## Range and rate selection

- Retained peak plus expanded uncertainty must remain below 80% of the input
  range, with no overload recovery in the following window.
- Choose the smallest nonclipping range unless the adjacent larger range has
  indistinguishable total error; then retain the larger safety margin.
- Each test/reference demodulator pair uses equal installed output rates. The
  rate is at least 8 times the test bandwidth where the two-active-demodulator
  aggregate limit permits. The installed maximum paired rate is used otherwise.
- Timestamp-aware analysis is mandatory. A known aliased baseband rotation is
  permitted only because the simultaneous complex ratio cancels it before model
  residuals are calculated.

## Model boundary

Exactly the three declared primary anchors are used. Rejected or superseded
records remain preserved but do not create new settings. The previously acquired
high-order diagnostic is not a primary point under this criterion. If any
primary anchor cannot satisfy these rules after one same-setting integrity
repeat, HF-01 stops for another prospective amendment. No physical parameter
grid is authorized.

## Timing-copy and channel equivalence

The accepted timing-copy authority is `HF01-TIMING-COPY-v3` and
`HF01-TIMING10-R5-001`. Exact one-to-one event counts are required. HF2 DIO
copy timing remains bounded by its actual streamed sample interval; the 20 ns
repeatability limit applies to the raw PicoScope B-relative-to-EXT measurement.

Signal Input 2 and reload-equivalence criteria remain unchanged from the phase
plan and are applied only after the manufacturer model passes and computational
selection is complete.
