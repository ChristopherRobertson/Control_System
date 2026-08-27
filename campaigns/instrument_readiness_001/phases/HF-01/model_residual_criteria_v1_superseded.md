# HF-01 frozen acceptance and expansion criteria

Criterion version: `HF01-MODEL-RESIDUAL-v1`. These rules were frozen before
response acquisition.

## Data integrity and electrical safety

- Every retained condition has three independent windows or transitions.
- PicoScope monitor and HF2LI records have monotonic timestamps, complete
  settings/readbacks, no overflow/overload, and no unexplained missing segment.
- Connected voltage stays inside `source_load_voltage_envelope.md`.
- An integrity or hard-voltage failure rejects that acquisition; it never
  authorizes an extra model point.

## Cascaded-filter model acceptance

For model prediction `H_n(f) = [1 + i 2 pi f tau]^-n`, all of the following
must pass for each anchor after uncertainty propagation:

- normalized magnitude residual at each retained frequency is no greater than
  the larger of `5%` and three combined standard uncertainties;
- phase residual is no greater than the larger of `5 degrees` and three
  combined standard uncertainties;
- measured cutoff differs from prediction by no more than the larger of `10%`
  and three combined standard uncertainties;
- normalized RMS complex residual across the retained frequencies is at most
  `5%`;
- rising/falling final-gain difference is at most the larger of `5%` and three
  combined standard uncertainties;
- observed 99% settling is no more than `120%` of the predicted value after
  delay correction, and absolute overshoot is at most `5%`;
- the intermediate positive/negative cutoff offsets agree in magnitude within
  `5%` and show the expected phase-sign reversal within `5 degrees`, each with
  the same three-uncertainty alternative.

One isolated failed metric invokes a single targeted point only when its
frequency/time region lies outside the bracket established by the other
anchors. A broad, contradictory, or second failure stops HF-01 for amendment.
Results never invoke an unrecorded grid.

## Range and rate selection

- Retained peak plus expanded uncertainty must remain below `80%` of the input
  range, with no overload recovery in the following window.
- Choose the smallest nonclipping range unless the adjacent larger range has
  indistinguishable total error; then keep the larger safety margin.
- Initial reference output rate is at least `8 x` measured filter bandwidth
  where the installed device permits. Timestamp-aware offline decimation
  screens lower supported rates.
- For a selected configuration, the immediately lower supported rate becomes
  selected if it preserves every declared feature and changes reconstructed
  amplitude, timing, and integrated area by no more than the larger of `2%`
  and three combined standard uncertainties. Continue downward until the next
  lower rate fails. A higher rate is measured only under the plan's guard-band
  rule.

## Timing-copy and channel equivalence

Timing-copy criterion version: `HF01-TIMING-COPY-v2`, prospectively amended
under `HF01-AUTH-AMEND-003`. Exact one-to-one event counts are required. HF2
DIO copy timing is reported with the actual streamed sample-interval bound;
the 20 ns repeatability limit applies to the raw Pico B-relative-to-EXT copy
measurement and is not misapplied as an HF2 nanosecond-resolution claim.

- The one 10 Hz timing check must contain a one-to-one set of exactly 10 A/B
  reference-copy edges and 10 C/D marker-copy edges, with monotonic HF2LI DIO
  timestamps and no extra or missing event.
- After applicable MS02 correction, copy-offset residual standard deviation
  must not exceed `20 ns`; mean offsets and uncertainty are retained rather
  than forced to zero.
- Signal Input 2 passes selected-setting equivalence when complex gain differs
  by at most `3%`, phase by at most `5 degrees`, cutoff and settling by at most
  `5%`, and zero-window RMS noise by at most `20%`, or the difference is within
  three combined standard uncertainties; neither channel may clip.
- Reload equality requires exact integer/string nodes and double nodes within
  `1e-9` relative or the device's observed quantization, whichever is larger.

## Challenger rule

Exactly one nearest boundary challenger is invoked for an experiment only when
the two leading total-error intervals overlap or the winner lies within one
expanded uncertainty of a hard applicability boundary. Otherwise no challenger
is measured. If equivalence persists, retain the larger temporal/clipping
margin unless lower rate materially improves a declared record-size limit.
