# HF-01 authorization

- Authorization ID: `HF01-AUTH-001`
- Campaign: `system_recalibration_001`
- Phase: `HF-01`
- Operator: `Christopher Robertson`
- Authorization date: `2026-08-26` local (`America/Los_Angeles`)
- Source: direct operator instruction supplied in the Codex task attachment
  `C:/Users/Chris/.codex/attachments/6e3bed39-da4e-4c04-a98c-0daf494a1ba4/pasted-text.txt`
- Requested repository provenance: commit/reference `93d81be` (informational,
  never a hash-matching gate)

The standing authorization covers only HF-01: repository evidence and focused
utilities; non-emitting hardware communication; operator-led temporary cable
moves; a bounded monitored PicoScope generator stimulus; one bounded 10 Hz
T660/PicoScope/HF2LI-DIO timing check; HF2LI acquisition and analysis; selected
configuration confirmation; and restoration to the documented default wiring.

It excludes laser arming, firing, emission, shutter opening, optical alignment,
sample or biological work, continuation of WM-01, ATT-01, every later campaign
phase, and canonical promotion. All lasers must remain electronically inhibited
and shuttered. No T660 timing output may reach MIRcat, T660-1, or a laser
controller while the temporary HF-01 copy topology is active.

Physical execution is operator-led. Codex presents exactly one physical action,
waits for the observation, records it, and only then issues the next action.
Generator output is programmed to zero before every connection, exchange,
restoration, ownership transfer, or abnormal stop. Before the first nonzero
enable, the exact waveform, programmed amplitude, offset, frequency,
terminations, source/load calculation, and expected connected voltage are
presented for operator confirmation.

Response acquisition is restricted to exactly three predeclared model anchors,
then computational enumeration, selected-setting confirmation, one optional
decision challenger per experiment only when the frozen ambiguity rule invokes
it, and at most one targeted extra model point after a predeclared residual
failure. A second model failure stops the phase for prospective amendment.

## Safety-intake clarification

On `2026-08-26`, the operator clarified that the Nd:YAG has no separate
electronic-inhibit control, confirmed the lasers are off and its firing
interlock is disconnected, established that shutters are closed unless
explicitly reported open, and authorized advancement past the remaining
repetitive safety checks. This resolves the intake terminology only. It does
not authorize arming, firing, emission, shutter opening, optical work, or any
later phase.

## Operator-workflow amendment

On `2026-08-26T19:30:47.7308617Z`, the operator authorized multiple routine
inspection and wiring steps to be provided together in order to accelerate
HF-01. This supersedes the earlier one-physical-action-at-a-time pacing rule
for routine HF-01 work. Codex still pauses for explicit operator confirmation
before the first nonzero PicoScope generator enable and before final restoration
is accepted. The amendment does not expand the non-emitting phase scope.

## Ten-hertz replacement amendment

On `2026-08-26T19:46:48.9951910Z`, after `HF01-TIMING10-001` was rejected
because its HF2 poll exporter saved X/Y rather than DIO, the operator explicitly
authorized one replacement 10 Hz check with the corrected DIO export. The
replacement ID is `HF01-TIMING10-R1-001`. The rejected first run remains
preserved. This amendment authorizes no further timing-check repeat.

## Final timing-method amendment

On `2026-08-26T19:52:11.4007288Z`, the operator explicitly authorized
`HF01-AUTH-AMEND-003`: exactly one final check, `HF01-TIMING10-R2-001`, using
the prospectively declared 1 ms pulses, maximum single-demodulator HF2 DIO
rate, and criterion `HF01-TIMING-COPY-v2`. The declaration remains the method
authority. This amendment authorizes no automatic retry, no nonzero PicoScope
generator output, and no expansion beyond HF-01.

## Bounded acquisition-repeat authorization

On `2026-08-26T19:59:34.8396345Z`, the operator authorized
`HF01-AUTH-AMEND-004`: execute `HF01-TIMING10-R3-001` and any subsequent
bounded HF-01 acquisitions necessary to collect the required data. Codex may
diagnose an acquisition issue, correct it prospectively, assign a new stable
acquisition ID, preserve the rejected evidence, and repeat without requesting
per-run permission. This supersedes the no-automatic-retry clauses of the R2
and R3 timing declarations, but it does not authorize silent overwrites,
unrecorded method changes, laser arming/firing/emission, shutter opening,
optical or biological work, later phases, or canonical promotion. The separate
operator confirmation before the first nonzero PicoScope AWG enable remains
in force.

The operator supplied that first-enable confirmation at
`2026-08-26T20:05:01.7544193Z` as `HF01-OPCONF-005`, after the exact waveform,
amplitude, offset, frequency, termination, source/load calculation, expected
connected voltage, and stop envelope were presented.

## Dual-demodulator model-validation amendment

On `2026-08-26T22:02:51.1736955Z`, the operator authorized
`HF01-AUTH-AMEND-005`: amend HF-01 as needed to obtain complete model-validation
evidence and keep all governing documentation aligned with the amended method.

The governing plan is `HF01-PLAN-v2`. It uses exactly the original three sparse
anchor regions with a synchronized wideband reference demodulator on the same
HF2LI input, oscillator, and device clock as the test demodulator. This method
identifies complex magnitude, phase, group delay, settling, and positive/negative
phase reversal without requiring cross-device host-clock synchronization. It
authorizes same-setting response repeats under new stable acquisition IDs and
criterion `HF01-MODEL-RESIDUAL-v2`.

This amendment does not authorize a fourth model point, physical parameter grid,
laser action, optical or biological work, later phase, or canonical promotion.
Earlier records and the v1 method remain preserved as superseded evidence and
are never rewritten as if acquired under the amended method.

## Paired-pipeline validation method

Under the same `HF01-AUTH-AMEND-005` authority, the governing plan is
`HF01-PLAN-v3` and the criterion is `HF01-MODEL-RESIDUAL-v3`. Exactly the same
three sparse anchor regions are retained. The paired-demodulator analysis uses
reference-magnitude run identification, exact overlapping timestamp samples,
the explicit reference-filter transfer, and one zero-intercept constant delay
nuisance per anchor bounded to one installed output-sample interval. Raw and
corrected phase are both retained, and step acceptance uses unsmoothed native
samples.

The v2 fast record remains preserved as superseded exploratory evidence and is
not accepted under the v3 criterion. New v3 stable IDs govern all three primary
anchors. This method adds no model point, physical grid, laser action, optical
or biological work, later phase, or promotion authority.
