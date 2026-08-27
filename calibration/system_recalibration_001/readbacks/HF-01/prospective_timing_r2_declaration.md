# Prospective HF01-TIMING10-R2-001 declaration

This method was frozen before any R2 data. The operator authorized it as
`HF01-AUTH-AMEND-003` at `2026-08-26T19:52:11.4007288Z`; authorization covers
exactly one execution and no automatic retry.

- Keep the operator-confirmed temporary timing topology unchanged.
- Keep the PicoScope generator programmed zero before and after.
- Use T660-2 synthetic `10 Hz`, exactly ten captured events, positive polarity,
  50-ohm source setting, and `1 ms` width on copied pairs A/B and C/D.
- Use one HF2 demodulator stream at the maximum supported single-demodulator
  rate requested as `460 kSa/s`; retain the actual quantized readback.
- Export and validate only `/dev18500/demods/2/sample.dio`.
- Require exactly ten DIO0 rising edges, ten DIO1 rising edges, ten Pico rapid
  segments, zero overflow, T660 count 0 to 10, and final T660 safe-idle match.
- Retain the Pico B-relative-to-EXT mean and repeatability at 2 ns sampling.
- Report DIO0-versus-DIO1 timing with the actual HF2 sampling-resolution bound;
  do not claim nanosecond HF2 edge resolution.

Criterion `HF01-TIMING-COPY-v2` accepts one-to-one event
capture plus raw Pico copy repeatability no worse than the already frozen
`20 ns` limit. The HF2 copy relation is bounded by its actual sample interval
rather than incorrectly treated as a nanosecond-resolved value. The criterion
amendment and exactly one R2 run were authorized by `HF01-AUTH-AMEND-003`.
