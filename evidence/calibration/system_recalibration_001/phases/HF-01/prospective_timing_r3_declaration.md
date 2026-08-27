# Prospective HF01-TIMING10-R3-001 declaration

This sequencing correction was frozen after R2 disposition and before any R3
data. The operator authorized it and subsequent necessary bounded acquisition
repeats as `HF01-AUTH-AMEND-004` at `2026-08-26T19:59:34.8396345Z`.

- Preserve the operator-confirmed temporary timing topology.
- Keep the PicoScope generator programmed zero before and after.
- Preserve the authorized R2 electrical settings: T660-2 synthetic 10 Hz,
  exactly ten events, positive polarity, 50-ohm source setting, 1 ms width on
  A/B and C/D, and HF2 demodulator 2 requested at 460 kSa/s.
- Open and arm the PicoScope rapid-block capture before the HF2 polling window
  begins.
- From the PicoScope after-arm callback, start a 1.3 s HF2 DIO poll, allow a
  100 ms pre-event margin, and only then start T660-2.
- Retain the actual HF2 rate and require that the final DIO edge precede the
  stream end by at least one 100 ms event period.
- Export only `/dev18500/demods/2/sample.dio`; require exactly ten DIO0 rises,
  ten DIO1 rises, ten Pico segments, zero overflow, T660 count 0 to 10, AWG
  zero before and after, and final T660 safe-idle match.
- Evaluate under the already amended `HF01-TIMING-COPY-v2` criterion.

R3 corrects only the acquisition-window order. It does not change the
electrical method, acceptance criterion, or HF-01 scope. Any necessary later
repeat receives a new stable acquisition ID and preserves the failed evidence
under the standing bounded-repeat authorization.
