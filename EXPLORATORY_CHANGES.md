# Exploratory Phase-Scan Changes

## Purpose and disposition

This file records deliberate changes and operating decisions for the originally disposable
Phase-Scan proof-of-concept branch. The objective is to demonstrate that
room-temperature MbCO recombination can be observed after photolysis with the
single-scan phase-delay method. These measurements and outputs are exploratory,
are not campaign qualification evidence, and are not eligible for publication.

On 2026-09-05, the operator approved retaining the desirable application, recipe,
test, and workflow implementation by committing the reviewed work on
`exploratory` and integrating it into local `main`. This supersedes the original
disposition to retain only this file and discard the exploratory implementation.
The approved integration does not include a push or any hardware operation.

This file remains a historical development and observation record. The source
and tests define current software behavior; entries below may describe
superseded implementation, wiring, acquisition, or analysis decisions. Retaining
the implementation does not qualify measurements, change campaign status, or
promote an instrument bundle.

### Implementation retained for integration

- Finite phase-delay acquisition uses preloaded T660 frame blocks and bounded
  Sweep-Active-triggered LabOne histories, with a separate small synchronized
  pump-event record and one consolidated raw acquisition artifact.
- A run has one unpumped baseline, calibrated hardware delay bounds, a nominal
  2.6 ms detector window validated against qualified Sweep Active and readbacks,
  and reconstruction from -1 through +5 ms relative to observed pump sync.
- Missing-pulse retries, coverage merging, their dedicated PicoScope acquisition,
  and programmatic etalon removal have been removed. Ordinary single-pass
  reconstruction and detector/reference/background normalization remain.
- Standalone MIRcat sweep controls, cancellation, device ownership, diagnostic
  plotting, and generic PicoScope block-wait callbacks are retained with their
  hardware-free tests. Diagnostic CSV exports and reloads preserve provisional
  coordinates, channel identities, clipping warnings, and nonpublication status;
  ordinary CSV behavior remains unchanged.
- Live phase acquisition requires an explicitly promoted timing qualification
  and a verified LabOne resident-capacity provider. It fails preflight when
  either is unavailable. The implementation retains its exploratory output
  classification; software integration does not establish hardware readiness.
- Existing acquired data, historical evidence, campaign records, promoted
  bundles, and local scratch files are outside the implementation commit.

The Nd:YAG iris-control work is not an exploratory change. It is part of the
current main-branch base and remains available in this branch through that base.

## Implemented exploratory changes

### Direct Sweep Active observation

- PicoScope CHA remains connected to the sample detector.
- PicoScope CHB remains connected to the reference detector and is the primary
  optical-pulse witness.
- The detector outputs remain split by the normal tees to the HF2LI and
  PicoScope.
- PicoScope EXT observes MIRcat DB9 pin 2, `Tuned / Sweep Active`, through a
  direct high-impedance branch. The existing pin-2 route to HF2LI DIO21 remains
  connected.
- The PicoScope EXT branch uses MIRcat DB9 pin 7 as its ground reference.
- T660-1 CHD is disconnected and disabled for this exploratory configuration.
- The direct BNC-to-mini-hook lead is treated as a 1x cable, not as a 10x
  attenuating probe. Its 50-ohm description is the cable impedance and does not
  authorize a 50-ohm termination at the observed DB9 signal.
- PicoScope EXT is configured for the rising Sweep Active edge with zero
  process-trigger offset. The configured trigger threshold is an initial
  candidate that must be checked against the observed pin-2 low and high levels.
- This direct trigger configuration is explicitly marked exploratory and cannot
  satisfy or replace the campaign CHD-to-Sweep-Active qualification.

### Exploratory output classification

- Background, test-scan, reconstruction, CSV, native-data, and plot products are
  marked `EXPLORATORY_PROOF_OF_CONCEPT` and not eligible for publication.
- Completed exploratory plots carry a visible `NOT FOR PUBLICATION` watermark.
- Missing-pulse-incomplete outputs retain their stricter
  `INCOMPLETE_MISSING_PULSE_COVERAGE` status and leave deficient regions empty.
- The complete original and repeated acquisitions remain preserved even when an
  attempt or region is rejected.

### Direct-trigger tests

- Hardware-free tests exercise the direct Sweep Active trigger contract, rising
  EXT edge, disabled T660-1 CHD, zero trigger offset, and nonpublication status.
- Missing-pulse retry tests continue to verify that the nominal pass completes
  before retries and that no more than three additional attempts are made for an
  affected phase delay.

### MIRcat internal trigger-acceptance headroom

The operator reports that the missing optical pulses were incoming triggers
being blocked by the MIRcat, and that the following tested settings eliminated
the blocking in a separate investigation:

| Destination / purpose | Repetition-rate setting | Pulse-width setting |
|---|---:|---:|
| T660-2 CHA to HF2LI EXT REF | 2,000,000 Hz | 150 ns |
| T660-2 CHB to MIRcat TRIG IN | 2,000,000 Hz | 150 ns |
| MIRcat internal QCL settings | 2,100,000 Hz | 142 ns |

Only the internal MIRcat settings change. MIRcat optical triggering remains
external; this does not switch the laser to internally triggered emission.
The initial description mentioned a 1 kHz rate offset, while the explicit tested
2.1 MHz versus 2 MHz example has a **100 kHz** offset. The implementation adopts
the explicit tested pair, not an inferred 2.001 MHz default. Internal rate and
width are separately editable rather than automatically applying an offset at
other trigger rates. No untested rate/width pair is claimed to eliminate losses.

- The Phase-Scan GUI now distinguishes `T660-2 Trigger Rate`, `T660-2 Trigger
  Width`, `MIRcat Internal Rate`, and `MIRcat Internal Width`. The derived plan
  and acquisition confirmation show both pairs and the internal rate margin.
- T660-2 CHA/CHB timing and the HF2LI reference remain at the external rate.
  Expected optical opportunities still come from the configured and read-back
  T660-2 rate: 500 ns spacing and ten opportunities per 5-microsecond interval
  at 2 MHz. The 2.1 MHz internal setting is never a fallback timing authority.
- The internal rate must be strictly higher than the external trigger rate.
  Internal duty is checked independently: 2.1 MHz times 142 ns is 29.82%, below
  the 30% ceiling. The existing conservative 30% external TTL duty bound remains
  separate; laser-specific SDK limits are applied to the internal settings.
- Every participating QCL receives the internal pair for background, test, and
  pumped scans. SDK rate, width, current, internal duty, and positive rate margin
  are verified after configuration/tuning and before emission and the sweep's
  process-trigger event. A mismatch stops the operation through the existing
  safe-shutdown path; settings are not silently reset to the external pair.
- Saved plans and acquisition/native records distinguish the two timing roles.
  Plan schema `3.1` and native-record schema `phase-scan/3.1` retain both requested
  settings and QCL readbacks, including the pre-emission and pre-process-trigger
  checks. Existing native records remain readable without rewriting them.
- Changing either internal parameter invalidates background compatibility,
  requiring a fresh background at the same acquisition settings.
- PicoScope analysis, acceptance thresholds, three-additional-attempt limit,
  aligned-bin gap filling, raw-attempt preservation, and deficient-output labels
  remain enabled as a safety net. An expectation of zero blocked triggers never
  bypasses measured coverage checks.

This change records an operator-reported finding and implements its explicit
settings. It does not independently validate zero losses, reinterpret completed
campaign evidence, or promote a calibration/characterization result. No laser or
timing output was enabled while implementing or testing the change, and no
campaign, calibration, characterization, or completed-history document was
modified.

## Retained missing-pulse behavior

The exploratory workflow retains the established missing-pulse acceptance and
gap-filling behavior as a safety net alongside the internal rate-headroom setting:

- A MIRcat optical pulse is classified as missing only when its expected
  opportunity is absent from both CHA and CHB.
- A one-channel-only event is recorded as a detector/path discrepancy rather
  than a MIRcat omission.
- A phase delay is selected for reacquisition when two consecutive opportunities
  are absent from both channels, when a reconstruction interval has less than
  90% coverage, or when the whole-scan missing fraction exceeds 5%.
- All nominal phase delays are acquired before missing-pulse analysis begins.
- Only affected phase delays are retried, with no more than three additional
  attempts.
- Retrying stops as soon as the marker-aligned union of the original and repeats
  provides acceptable coverage for every required reconstruction region. A
  single omission-free replacement scan is not required.
- Valid original regions are retained. Valid repeat regions fill deficient
  regions, and multiple acceptable contributors are combined with pulse-coverage
  weighting while preserving per-region acquisition provenance.
- Isolated single missing opportunities are already accepted by the default
  90%-of-ten-opportunities rule for a 5-microsecond interval at 2 MHz.
- Missing optical opportunities are not replaced with synthetic pulses.
  Interpolation may be considered only for a visibly marked diagnostic preview;
  it must not replace measured values or convert an incomplete result into a
  complete result.

## Sample/reference processing decision

- The sample beam contains MbCO.
- The reference beam contains a matched water-and-buffer blank.
- Each acquisition is normalized as sample detector divided by reference
  detector before pump-induced absorbance is calculated.
- The optical background is an unpumped MbCO acquisition made with the blank
  simultaneously present in the reference path.
- The desired difference spectrum is
  `-log10[(S/R)/(S0/R0)]`.
- Pulse detection, local expected-grid fitting, Sweep Active alignment,
  wavelength-marker alignment, and reconstruction-bin assignment occur before
  attempts are combined.
- For repeated attempts, valid sample/reference transmission-ratio bins are
  coverage-weighted and merged before applying the logarithm. The merged ratio,
  background ratio, resulting absorbance, normalized contribution weights, and
  contributing attempt sources are retained with the reconstruction.
  Independently
  merging sample and reference channels, or averaging already-log-transformed
  absorbance from unlike attempts, is not the intended final processing order.

## Implemented proof-of-concept acquisition settings

The following settings are the exploratory workflow defaults. The spectral
endpoints remain operator-adjustable and must be recentered after the sample's
actual A1 maximum is located:

| Setting | Exploratory value | Rationale |
|---|---:|---|
| MIRcat current | 750 mA | Reduce the risk of detector saturation in the strongly absorbing aqueous configuration; increase only after a pump-blocked signal check if necessary. |
| T660-2 CHA/CHB repetition rate | 2 MHz | Retain the HF2LI EXT REF and MIRcat TRIG IN train; 500 ns expected-opportunity period. |
| T660-2 CHA/CHB TTL width | 150 ns | External reference/trigger pulse width, distinct from the MIRcat internal QCL width. |
| MIRcat internal repetition rate | 2.1 MHz | Operator-reported tested trigger-acceptance setting, 100 kHz above the external train; optical triggering stays external. |
| MIRcat internal pulse width | 142 ns | Internal duty is 29.82% at 2.1 MHz, below the 30% ceiling. |
| Spectral span | 10 cm^-1 | Minimum proof-of-concept window, centered on the experimentally observed main A1 maximum after it is located. |
| Sweep rate | 10,000 cm^-1/s | Produces an approximately 1 ms sweep across a 10 cm^-1 window. |
| Phase increment | 5 microseconds | Retain the requested reconstruction grid and missing-pulse interval width. |
| Pre-pump window | 2 ms | Provide an unpumped baseline region at every reconstructed wavenumber. |
| Post-pump window | 5 ms | Capture approximately 99.5% recovery under the literature biexponential guide while avoiding an unnecessarily long phase series. |
| Minimum pump-shot interval | 250 ms | Provide conservative time for sample reset, acquisition transfer, preservation, and device readiness. Actual intervals may be longer and are reconstructed from observed timing. |
| Repetitions | 1 | Minimize proof-of-concept duration and sample exposure. |

For a 10 cm^-1, 1 ms sweep with 2 ms before-pump coverage, 5 ms after-pump
coverage, and a 5-microsecond phase increment, the plan contains approximately
1,601 pumped phase positions. A 250 ms minimum pump-shot interval gives a nominal
duration of approximately 6.7 minutes before setup and missing-pulse retries.

## Implemented exploratory HF2LI change

The existing `campaign_sweep_qualification_candidate` preset is not to be
modified for this proof of concept. The separate
`exploratory_phase_scan_poc` preset is used so the campaign candidate retains
its original settings and meaning.

The exploratory detector demodulators are configured for:

- 20 kSa/s detector-stream rate for both sample and reference;
- a 50-microsecond time constant;
- the existing external 2 MHz reference topology and detector assignments;
- the independently configured timing/DIO stream needed to observe Sweep Active,
  wavelength markers, and the electrical pump reference.

The faster detector settings are necessary because the previous 2 kSa/s,
1-millisecond detector configuration would supply only about two detector sample
intervals across a 1 ms sweep and would smear most of a 10 cm^-1 window. The
pump-blocked background and test scan must confirm usable signal-to-noise,
absence of clipping, marker recovery, and successful PicoScope transfer before
photolysis begins.

## Optical preparation and continuation checks

- The operator reported all lasers aligned and a pump-rejection filter installed
  between the sample and its detector. Record the final iris diameter and OPO
  wavelength readback if not already captured, and confirm the cleaned pump beam
  overlaps the MIRcat-probed sample volume without the unwanted wavelength halos.
- Confirm that pump scatter does not reach either infrared detector.
- Locate the sample's main A1 maximum and center the final 10 cm^-1 scan window
  on the observed peak rather than treating a literature value as the measured
  center.
- Confirm positive, unsaturated sample and reference signals on both the HF2LI
  and PicoScope before recording the optical background.

## Validation record

Before the subsequently approved current, cadence, spectral-window, and HF2LI
changes, the exploratory direct-trigger and missing-pulse implementation passed
the offline suite with 151 tests passed, 11 skipped, and 24 subtests passed. The
suite and diff checks must be rerun after each implementation update, and the
result recorded here without treating a software test as hardware validation.

After implementing the 750 mA current, 10 cm^-1 default window, 250 ms cadence,
5 ms post-pump window, fast exploratory HF2LI preset, and ratio-before-log attempt
merge, the focused Phase-Scan suite passed 58 tests with 6 skipped. The complete
offline software suite then passed 154 tests with 11 skipped and 24 subtests
passed.

After separating MIRcat internal timing from the T660-2 reference/trigger train,
the focused Phase-Scan suite passed 81 tests with 7 skipped using system Python.
The complete offline suite, including the GUI tests in the repository virtual
environment, passed **182 tests, 3 skipped, and 24 subtests** using
`.venv\Scripts\python.exe -m pytest software/tests -q`. The checks cover separate
SDK/T660/HF2LI settings, internal duty and hardware limits, readback failure and
safe shutdown, setting resets during SDK sweep start, background invalidation,
and retention of the 2 MHz optical-opportunity grid and existing retry behavior.

## Historical continuation checkpoint

- The original instruction was to continue on `exploratory`, preserve local
  uncommitted work, and retain only this record on `main`. That branch-retention
  policy was superseded by the operator-approved integration on 2026-09-05
  described above. Updating this record does not itself authorize a push.
- Before the internal-headroom change, a fixed 1850 cm^-1 external-triggered
  illumination check confirmed sample/reference detector pulses and HF2LI PLL
  lock to T660-2 CHA. The 1850 cm^-1 setting was for filter verification, not a
  measured MbCO band center. That check did not validate the new internal pair,
  a full optical sweep, or the reconstructed photolysis series.
- The last shutdown in this task confirmed MIRcat emission OFF, disarmed and SDK
  deinitialized, with both T660 units at trigger source OFF and every A-D output
  disabled. This software update did not reconnect or enable hardware. Confirm
  the current physical state before subsequent operation; previous authorization
  is not authorization to restart a laser or fire the pump in a new task.
- The next milestone is an authorized pump-blocked background/test-sweep pair,
  after confirming the optical window and releasing the PicoScope from its
  standalone application so the SDK can acquire it. Validate actual pin-2 EXT
  triggering, full dual-detector capture, wavelength/Sweep Active markers,
  internal/external rate readbacks, transfer, measured pulse coverage and
  reconstruction before enabling the pumped phase series.
- Keep all outputs exploratory and not for publication. The completed
  calibration/characterization campaigns and their documentation remain outside
  this demo's editing scope.

### 2026-09-02 continuation: air-only checkout first

The operator confirmed that the pump is physically blocked and MIRcat is
off/disarmed, and reported no observed MbCO band maximum. The next optical
operation was then changed to one simple **air-only, unpumped scan**, specifically
to check HF2LI detection and triggering before introducing the sample.

- A non-emitting readiness check confirmed both T660 identities, trigger sources
  OFF and all A-D outputs disabled. MIRcat read back emission OFF, disarmed,
  scan inactive, interlock/key closed, and system error zero. Its SDK session was
  deinitialized afterward.
- Installed QCL 1 coverage read back approximately 1638.807-2077.275 cm^-1.
  Its idle settings were 2.1 MHz, 142 ns and **1000 mA**. The proposed acquisition
  must explicitly set and verify **750 mA** before enabling emission.
- HF2LI dev18500 was reachable and its settings snapshot had no read errors.
  No HF2LI preset was applied during this check. PicoScope 7 was not running;
  the PicoScope SDK opened successfully, configured both detector channels and
  rising EXT with autotrigger disabled, verified 16 ns sampling and sufficient
  memory, and closed. No acquisition, emission enable, arm, sweep or timing
  event occurred.
- Readbacks and the proposed operation are preserved under
  `evidence/experiments/runs/exploratory_mbco_readiness_20260902T224148_508839Z/`.
  The earlier proposed broad survey remains a planning-only artifact; the
  air-only checkout is the next proposed operation.
- Proposed air checkout: one 1950 -> 1940 cm^-1 sweep at 10,000 cm^-1/s,
  750 mA, external T660-2 2 MHz / 150 ns and internal MIRcat 2.1 MHz / 142 ns.
  This range is a system-test window, not a measured MbCO peak selection.
  Fire/Q-switch outputs and T660-1 CHD remain disabled. Fresh authorization to
  enable MIRcat emission is still required; no automatic retry is authorized.
- HF2LI acquisition uses continuous native polling and selects the sweep using
  observed DIO21 Sweep Active and DIO22 wavelength markers. It is not an HF2LI
  triggered-capture mode. The air scan must verify those observations, reference
  tracking and both detector streams. A provisional nominal wavelength axis or
  a successful SDK transfer alone does not demonstrate complete optical
  reconstruction. Background/test operations do not automatically execute the
  runner's pumped-series pulse-coverage stage, so inspect the saved air record
  with the existing coverage analyzer explicitly.
- The air checkout is not the unpumped MbCO optical background. Band selection,
  a fresh sample/reference background, a pump-blocked comparison scan and any
  separately authorized pumped series remain outstanding.
- The unchanged implementation again passed the full offline suite:
  **182 passed, 3 skipped, 24 subtests passed**. No optical acquisition has yet
  been demonstrated in this continuation.

The operator subsequently requested **2050 -> 1650 cm^-1** for this first air
scan, superseding the narrower system-test proposal above. QCL 1's installed
readback range covers the entire requested span. At 10,000 cm^-1/s this is one
nominal 40 ms sweep, with approximately 800 HF2LI detector samples per channel,
80,000 external optical opportunities, and 81 requested wavelength markers at
5 cm^-1 spacing. The prepared operation remains one unpumped sweep, with no
automatic repeats, at 750 mA and the same separate external/internal timing
pairs. The revised planning artifact is
`proposed_air_scan_2050_to_1650.json` in the readiness directory above. No
emission was enabled while preparing this revised operation.

### Authorized air attempt and startup/rate corrections

The operator confirmed both probe paths were through air and authorized one
2050 -> 1650 cm^-1, 10,000 cm^-1/s, 750 mA air sweep with the pump blocked.
Records are preserved under
`evidence/experiments/runs/exploratory_air_checkout_20260902T224505_935642Z/`.

- The first preparation (`20260902T224505_939642Z_background`) stopped because
  the temporary command-line progress logger could not encode a Unicode arrow
  using Windows CP1252. No emission-enable or process-trigger call occurred;
  safe shutdown was verified. The logger was corrected to UTF-8 and preparation
  resumed for the same authorized optical operation.
- The optical attempt (`20260902T224603_439271Z_background`) successfully read
  back 750 mA, internal 2.1 MHz / 142 ns, external optical triggering and
  external process triggering. Emission was briefly enabled, but
  `MIRcatSDK_StartSweepScan` returned **71, START_SWEEPSCAN_FAILURE**. T660-1's
  event counter remained 42511; no process-trigger or pump event occurred.
  PicoScope block capture was not reached. No valid air spectrum, EXT-trigger
  validation, optical pulse-coverage result or reconstruction was obtained.
- Both preparations retain their native/partial records and cleanup records.
  The final readbacks confirmed MIRcat OFF, disarmed, scan inactive and error
  word zero, with SDK deinitialization and both T660 units OFF/all outputs
  disabled. PicoScope was closed. Later rate checks connected only to HF2LI.
- The retained HF2LI streams contained sample/reference data and tracked near
  2 MHz, but DIO21 was already high throughout and no DIO22 rising edges were
  observed. These pre-sweep records do not demonstrate sweep detection.
- A concrete SDK sequence error was found: Phase Scan calls `TuneToWW`, then
  `StartSweepScan` without the required intervening `CancelManualTuneMode`.
  The vendor header explicitly requires this cancellation before scanning
  (`references/sdk/MIRcat/include/MIRcatSDK.h`, line 1372). The exploratory
  adapter now cancels manual tune while T660-2 CHB is still disabled and checks
  internal QCL settings again before starting the sweep. Regression transports
  now model the blocking manual-tune state; cancellation failure or a settings
  reset stops before sweep/process triggering and preserves the partial record.
  This correction has passed offline tests but has not yet been optically
  retried.

The operator requested correction of the HF2LI detector sample rate and later
confirmed the corrected values were visible in LabOne. A direct, non-emitting
SDK set/readback check reproduced **20,000 requested -> 14,391.447368421053 Sa/s
actual** on both detector demodulators. This is consistent with the instrument's
documented approximation to supported rates; leaving LabOne open was not, by
itself, evidence of a conflicting write. Both streams were then set to
**28,782.894736842107 Sa/s** and held that setting over the bounded two-second
check. The time constants remained approximately 49.9954 microseconds. The DIO
timing stream remained 230,263.15789473685 Sa/s, the readback of its 200,000 Sa/s
request. See `hf2li_rate_rounding_check.json` and
`hf2li_detector_rate_adjustment.json` in the operation directory above.

Only the exploratory HF2LI preset's detector-rate entries were changed to the
verified 28.783 kSa/s setting, replacing the earlier 20 kSa/s request. The
campaign candidate preset retains its original values. Phase Scan now verifies
both detector rate readbacks against the selected preset before emission and
records the verified rates and sample intervals. Neither rate change affects
the 2 MHz external optical-opportunity/reference clock or the separate 2.1 MHz
MIRcat internal setting. A fresh compatible optical background will still be
needed for the eventual MbCO measurement.

The complete offline suite after these corrections passed **186 tests, 3
skipped, and 24 subtests**; `git diff --check` passed. The next proposed operation
is one further air-only 2050 -> 1650 cm^-1 sweep at the same laser/sweep settings
and the corrected detector rates. It is prepared in
`prepared_air_scan_after_corrections.json` and requires fresh per-operation
emission authorization. No additional optical attempt was made during diagnosis
or correction, and no campaign, calibration, characterization or completed
history document was edited.

### One-time standalone 10-second air scan preparation

The operator changed the requested air scan to **2050 -> 1650 cm^-1 at
40 cm^-1/s**, nominally **10 seconds**, and explicitly specified that it is
independent of Phase Scan. No phase interval, phase-delay plan, pumped-series
default or saved fast HF2LI preset was changed for this request.

One-time preparation records are in the preceding air-checkout directory's
`slow_scan_once/` child directory. `standalone_air_scan_operation.json` describes
one unpumped sweep; `restore_fast_hf2li_snapshot.json` records the fast detector
and marker-stream settings to restore and verify after completion, abort or
cancellation. The temporary settings are now applied to the live HF2LI pending
fresh optical-operation authorization:

- Sample demodulator API index 0 and reference index 3: **1798.9309210526317
  Sa/s**, **1 ms requested / 1.0018887078828383 ms read back**, fourth-order
  filters, harmonic 1, oscillator 0 and continuous streaming.
- Timing/DIO demodulator API index 2: enabled, **28782.894736842107 Sa/s**,
  independently retaining Sweep Active and wavelength markers. Its rate is not
  derived from a phase increment for this standalone scan.
- A requested second verification found that the live controls had changed to
  224.866 Sa/s, first-order detector filters and a disabled timing stream. Those
  settings were corrected to the one-time configuration above and read back
  successfully; the source of the intervening writes was not established.
- A reference-only test enabled **T660-2 CHA at 2 MHz / 150 ns**, with CHB and
  all other outputs disabled and MIRcat OFF/disarmed. HF2LI oscillator readbacks
  were 2000001.56, 1999996.06 and 2000000.34 Hz. T660-2 was then returned to OFF
  with all outputs disabled, and MIRcat's SDK was deinitialized. No emission or
  pump event occurred. See `hf2li_slow_live_verified.json`.
- The complete 10-second dual-detector PicoScope capture would exceed the
  configured memory at 16 ns/sample. A local, one-scan recipe was verified at
  **48 ns/sample**, within the existing pulse-capture interval limit. The
  10.50026-second allocation is approximately 218.76 million samples per
  channel, below the SDK's 268.44 million-sample limit. Full raw detector
  records are retained; this standalone spectrum is not a phase-delay
  reconstruction or a full phase-bin missing-pulse qualification.
- The PicoScope block API now accepts an optional wait callback so a long
  standalone capture can continue draining HF2LI data and checking interlocks.
  Existing callers retain their behavior when the callback is omitted. The full
  offline suite passed **188 tests, 3 skipped and 24 subtests**.

The standalone optical scan has not yet run. Emission authorization for the
earlier failed attempt does not authorize this new 10-second operation. The
next operation still uses 750 mA, external optical triggering at 2 MHz / 150 ns,
and internal MIRcat settings of 2.1 MHz / 142 ns. The pump remains blocked and
Fire/Q-switch outputs remain disabled.

### Standalone air scans completed, including the operator-requested repeat

The operator subsequently authorized continuation without further permission
pauses, then explicitly requested a repeat of the same scan. Two independent
unpumped **2050 -> 1650 cm^-1, 40 cm^-1/s** air scans were executed at 750 mA.
Their immutable acquisition directories under `slow_scan_once/` are
`acquisition_20260902T230429_400991Z/` and
`acquisition_20260902T230659_436853Z/`. Both operations retained external
2 MHz / 150 ns reference/optical triggering and internal 2.1 MHz / 142 ns
MIRcat settings, with readbacks and duty limits verified. Neither operation
used a phase-delay plan or changed the phase interval. The standalone script
starts the sweep directly without entering manual TuneToWW mode.

- Both scans completed one observed Sweep Active interval of **9.994755657 s**.
  Each detector stream retained **17,980 samples** during the sweep at
  1798.930921 Sa/s, and the timing stream retained 287,679 samples at
  28782.894737 Sa/s. There were **no in-sweep stream gaps**. A later HF2LI gap
  during PicoScope transfer was outside the completed sweep and is retained
  and reported in the native-data analysis.
- Actual PicoScope **EXT rising-edge capture succeeded with autotrigger
  disabled**. Both full detector records transferred: 218,755,418 samples per
  channel at 48 ns, covering 10.500260064 s. Overflow was zero. No PicoScope
  ADC clipping was found in the repeat's full arrays; this is not a detector
  linearity qualification. The EXT waveform itself was not digitized.
- Both sweeps contained **80 rising wavelength markers, versus 81 requested**,
  evenly spaced approximately 124.935 ms apart. The final marker was about
  9.870133 s after Sweep Active rose. Endpoint identity remains unresolved;
  no missing marker was silently renumbered. The repeat's sample/reference
  spectrum therefore uses an explicitly **provisional linear axis between
  observed Sweep Active edges**, not an accepted marker-identified axis.
- Representative PicoScope pulses show approximately 2 MHz optical timing.
  Across 101 one-millisecond spot windows, sample pulses were resolved in 63
  windows and reference pulses in 80 under the stated signal/noise criterion.
  Weak windows remain unresolved, not classified as missing pulses. Full
  phase-bin pulse coverage and phase-delay reconstruction were not performed.
- Each run incremented the T660-1 counter by exactly one process event;
  Fire/Q-switch channels A/B and disconnected CHD remained disabled. No pump
  event occurred. Both cleanup records verify MIRcat OFF/disarmed/stopped and
  deinitialized, both T660 units OFF/all channels disabled, PicoScope closed,
  and restoration of the saved fast HF2LI settings with matching readbacks.
- The repeat's plot, CSV, native spectrum, pulse spot checks and assessment are
  in `acquisition_20260902T230659_436853Z/analysis_20260902T230753_389587Z/`.
  An initial first-run export attempt stopped on a Spectrum field-name error;
  its partial CSV and valid native spectrum remain preserved. The corrected
  analysis writes fresh child directories and completed on the repeat.

This demonstrates standalone optical sweep acquisition, hardware EXT capture,
dual-detector transfer and provisional ratio-spectrum construction. It is
not an MbCO background, absorbance measurement, accepted wavelength calibration,
or a complete optical Phase Scan reconstruction. All results remain exploratory
and nonpublication; campaign and completed-history documents were not edited.

### Air detector mismatch: stopped and rejected for ratio/background use

After the repeat, the operator requested STOP and reported that the sample and
reference shapes should match. No further optical operation or hardware setting
write was made. Offline inspection found a missed input-headroom check: both
HF2LI signal inputs had read-back ranges of approximately **1.014 V**, whereas
the repeat's split-detector PicoScope waveforms reached **0.713 V sample** and
**1.940 V reference**. About 12.91% of the complete reference record's samples
exceeded its configured HF2LI input range; no sample-channel point did.

Independent 2 MHz fundamental estimates from one-millisecond raw PicoScope
windows support reference-channel overload. At approximately five seconds,
sample magnitude was 0.10120 V RMS from PicoScope versus 0.10116 V from HF2LI;
reference magnitude was 0.54899 V RMS from PicoScope versus 0.32957 V from
HF2LI. The HF2LI comparison allows the nominal four-millisecond filter delay.
Illustrative hard clipping of the raw reference waveform at its configured
range substantially lowers its computed fundamental. This is diagnostic
evidence, not a correction or a model of the full analog input response.

The saved sample rates, filter orders, time constants and channel mappings
matched the request. That did not establish adequate input headroom, and the
earlier claim that the HF2LI settings were correct was incomplete. PicoScope
overflow zero does not establish HF2LI ADC headroom. Contemporaneous HF2LI
overload flags were not retained, and upstream detector nonlinearity/optical
path differences remain possible additional contributors.

Both acquisitions now have additive `detector_comparison_disposition.json`
records rejecting their use for detector matching or ratio/background
acceptance, while preserving successful trigger/transfer observations and all
native data. The repeat's detailed offline evidence is in
`input_range_diagnostic/diagnostic.json`. No derived spectrum was promoted or
used as an MbCO background. Before another optical measurement, reduce/balance
the incoming detector signals and verify their peak headroom and linearity.
The manufacturer's HF2LI documentation specifies input-range settings only up
to 1.5 V, so increasing the range alone does not accommodate the observed
1.940 V reference peak. Hardware remains in the previously verified safe idle
state; the user's STOP supersedes the earlier authorization to continue.

### 750 mA repeat, retained settings, and reference waveform diagnosis

The operator then requested another 750 mA scan and explicitly superseded the
previous restoration policy: retain acquisition settings after the scan for
possible repeats. `run_standalone_air_keep_settings.py` implements that bounded
standalone operation without calling the fast-HF2LI restoration routine. The
run is `slow_scan_once/acquisition_20260902T231231_332187Z/`.

- MIRcat already read 750 mA on entry; 750 mA was explicitly reapplied. Fifteen
  readbacks during active scanning, the post-transfer check, the final retained
  configuration, and a fresh SDK reconnection all confirmed **750 mA**. Internal
  2.1 MHz / 142 ns and external optical/process triggering were retained.
- The 2050 -> 1650 cm^-1, 40 cm^-1/s sweep again lasted 9.994755657 s, with
  17,980 detector samples per channel and no in-sweep detector gaps. Both full
  PicoScope records transferred; 80 of 81 requested wavelength markers were
  observed. Endpoint identification remains provisional.
- Contemporaneous HF2LI `/status/flags/adcclip/0` and `/adcclip/1` observations
  now directly confirm the overload: sample clipping was 0/15 checks and
  reference clipping **12/15 checks**. Repeat raw peaks were approximately
  0.713 V sample and 1.940 V reference. This scan remains diagnostic only and
  is not accepted as a ratio/background or detector-matching measurement.
- After shutdown and reconnection, the HF2LI input/demodulator settings matched
  the scan configuration: detector rates 1798.930921 Sa/s, time constants
  1.001888708 ms, fourth-order filters, and timing stream 28782.894737 Sa/s.
  No fast-preset restoration occurred. Numerical T660 pulse settings remained;
  its outputs were stopped/disabled and MIRcat IR was OFF/disarmed. See
  `retained_settings_after_reconnect.json` and `repeat_summary.json`.

The operator reported matched optical arms, an angled reference detector, and
that removing the filter for the second scan had no effect. No assertion is
made that the filter caused an etalon. Offline comparison in
`waveform_comparison_20260902T231547_284349Z/` extracted the 2 MHz Fourier
component from one-millisecond raw PicoScope windows every two milliseconds.
The sample closely matches HF2LI (median raw/HF2LI ratio 1.0032 in the central
region). The reference's excess upward peaks are **already present in its raw
PicoScope waveform**, with additional HF2LI attenuation/distortion from ADC
clipping (median raw/HF2LI ratio 1.6041). Thus HF2LI overload alone does not
explain the originating peak structure. This localizes an additional issue to
the detector/analog/optical path before demodulation, without distinguishing
detector nonlinearity, electrical loading/reflections, or optical effects.
The normal detector BNC tees remain connected, so the PicoScope branch does
not independently isolate the HF2LI analog input's loading.

### Red alignment pointer currently enabled at the operator's request

The operator requested the MIRcat red pointer for an alignment check while
diagnosis continued. The pointer was enabled and read back ON at
2026-09-02T23:17:16Z, with **IR emission OFF, MIRcat disarmed, and 750 mA retained**.
No IR scan or pump event accompanied this action. Evidence is in
`slow_scan_once/red_alignment_20260902T231658_231906Z/`.

A live `hold_red_pointer.py` helper owns the MIRcat SDK session (execution
session 65501). Do not start a second MIRcat SDK controller while it is active.
To end the pointer operation, create the helper directory's `STOP` file and
wait for its `closed.json`/OFF readback; it then disables the red pointer and
deinitializes the SDK. This explicit red-pointer operation changes the prior
all-lasers-off state; IR remains off. The HF2LI scan settings remain retained.

### Repeat after reference detector adjustment; red pointer now OFF

The operator adjusted the reference detector and requested another scan. Before
starting, the red-pointer helper was stopped through its `STOP` file; it read
back the pointer OFF, deinitialized the SDK and exited with no cleanup errors.
Its completed record is `red_alignment_20260902T231658_231906Z/closed.json`.
Execution session 65501 no longer owns the MIRcat SDK.

The authorized repeat is `slow_scan_once/acquisition_20260902T231923_573556Z/`:
one 2050 -> 1650 cm^-1 air sweep at 40 cm^-1/s and 750 mA, with unchanged
external 2 MHz / 150 ns and internal 2.1 MHz / 142 ns. Current readbacks stayed
750 mA. The sweep lasted 9.994755657 s; each detector retained 17,980 samples
with no in-sweep gaps, and both complete PicoScope records transferred without
overflow. Eighty wavelength markers were observed; the axis remains provisional.

The reference adjustment did not remove its upward spikes or ADC overload.
Reference clipping again appeared in **12/15 active-scan checks**, versus
**0/15 sample checks**. Raw reference/sample peaks remained approximately
**1.940 V / 0.713 V**. This result remains diagnostic only and is not accepted
as a background or valid detector-matching spectrum. See `repeat_summary.json`,
`detector_comparison_disposition.json` and
`analysis_20260902T232028_511007Z/air_checkout.png` in that acquisition directory.

Final readbacks verify MIRcat IR OFF/disarmed, red pointer OFF, both T660 units
idle with outputs disabled, and retained 750 mA/internal pulse parameters and
HF2LI scan settings. No fast-HF2LI restoration or corrective current write was
needed. The user preference to retain scan settings remains in force.

The operator subsequently requested the red alignment pointer ON again. Its
ON readback at 2026-09-02T23:26:14Z is recorded in
`slow_scan_once/red_alignment_20260902T232600_454188Z/enabled.json`; IR remains
OFF/disarmed and current is 750 mA. This new helper owns the MIRcat SDK in
execution session **86850**. Create this new directory's `STOP` file and wait
for `closed.json`/OFF verification before another MIRcat SDK operation. The
pointer is intentionally left ON for the operator; scan settings are retained.

### Detector-location swap test: both inputs at negative DC levels

The operator reported swapping detector locations and requested the same scan.
The red-pointer session 86850 was stopped first; its new `closed.json` confirmed
pointer OFF and clean SDK release. The authorized scan is
`slow_scan_once/acquisition_20260902T232846_841583Z/`.

MIRcat remained at 750 mA with the same 2050 -> 1650 cm^-1, 40 cm^-1/s scan
and separate external/internal timing settings. The 9.994755657-second sweep
completed with 17,980 HF2LI samples per input, no in-sweep gaps, full dual-channel
PicoScope transfer and 80 wavelength markers. These transport results do not
make the detector record usable.

Both HF2LI ADCs reported clipping **before sweep setup**, throughout all 15
active-scan checks, and afterward. ADC minimum/maximum status values were -128
for both inputs. PicoScope A stayed near **-1.471 V** and B near **-1.499 V**
throughout the capture, without the previous positive optical pulse trains.
This new offset/clipping condition prevents using the swap to determine whether
the original reference spikes followed a detector or optical arm. No ratio
spectrum/background was accepted. `negative_offset_diagnostic.json`,
`channel_summary.json` and `detector_comparison_disposition.json` retain the
evidence and rejection; native arrays remain intact.

The operator was asked whether cables stayed with the detectors or were
reconnected to preserve sample/reference channel assignments; the answer is
pending. Use electrical Input 1/Pico A and Input 2/Pico B labels until clarified.
Detector/controller power and head/signal connections after the physical swap
need checking, followed by a usable baseline before another optical run.
No specific power or cable fault has yet been established.

Final cleanup verified MIRcat IR OFF/disarmed, red pointer OFF, both T660 units
idle, and retained 750 mA/internal pulse settings plus the slow HF2LI scan
configuration. Session 86850 no longer owns the MIRcat SDK.

### Standalone Air Scan in the custom application

At the operator's request, the tested standalone scan is now available in a
dedicated **Air Scan** tab in the normal custom application. The fixed operation
is one **2050 -> 1650 cm^-1, 40 cm^-1/s, 750 mA** air sweep. It has no phase-delay
plan, background requirement, automatic repeat, or pump event. The existing
Phase Scan parameters and saved presets are unchanged by this addition.

- Check the pump-blocked/beam-path box, then click **Start Air Scan (IR ON)**.
  Each click authorizes one operation at the displayed settings; there is no
  additional modal confirmation. **Stop** requests cancellation and retains
  ownership until device calls return, outputs stop, and available data is saved.
  Start becomes available again after a verified shutdown. A failed shutdown or
  retention check prevents another Start in that app session.
- The standalone profile applies and checks HF2LI detector rates of
  1798.9309210526317 Sa/s, 1.0018887078828383 ms read-back time constants,
  fourth-order filters, continuous streams, input assignments, input ranges,
  oscillator/harmonic assignments and the external-reference PLL configuration.
  Timing/DIO retains 28782.894736842107 Sa/s. The external reference/optical
  trigger train remains 2 MHz / 150 ns; MIRcat internal settings remain
  2.1 MHz / 142 ns. SDK limits and readbacks are checked separately.
- With IR off, three input-status observations must report neither ADC clipped
  before arming. Missing clipping status also stops preparation. Checks repeat
  before sweep setup and the process event. Clipping observed during an
  otherwise completed sweep remains visible in the diagnostic result; it does
  not become a valid ratio or optical background. The previous negative-offset
  fault will block a new scan if still present.
- PicoScope uses the tested dual-detector 218,755,418-sample allocation per
  channel at 48 ns, EXT rising-edge Sweep Active triggering, and no autotrigger.
  PicoScope 7 must release the device before Start. Exactly one T660-1 CHC
  process event is issued after Pico EXT is armed; Fire/Q-switch A/B and CHD
  remain disabled and are read back before the event. A new optional service
  callback stops IR and timing outputs after capture readiness and before the
  blocking USB transfer. The UI stays responsive during device calls, although
  Stop must wait for a blocking SDK call to return.
- Numeric MIRcat/HF2LI settings remain after completion or Stop; there is no
  fast-HF2LI restoration. IR is switched off, MIRcat disarmed/deinitialized,
  T660 outputs stopped/disabled, and PicoScope closed. The normal MIRcat tab's
  idle SDK session is released before acquisition, and other app controls are
  blocked during Air Scan. Starting Air Scan invalidates an existing Phase Scan
  background because the detector configuration changes.
- Every click creates a fresh `air_scan_<UTC>/` directory under the app's Save
  Location. Native HF2LI chunks, both Pico ADC arrays, settings, status checks,
  cleanup and failures are retained. Completed captures automatically produce
  `detectors.csv`, `analysis.json`, and `air_scan.png`, displayed in the tab.
  Plots use electrical Input 1/Pico A and Input 2/Pico B labels pending the
  detector-swap cable mapping. The wavelength axis stays explicitly provisional
  between observed Sweep Active edges; marker counts are reported without
  renumbering missing endpoints. No ratio/background acceptance or Phase Scan
  reconstruction is claimed. Plots are marked **NOT FOR PUBLICATION**.

The entry point accepts `--air-scan` to open this tab directly; the existing
`run_gui.ps1` launcher also exposes the new tab. Hardware-free transport and GUI
tests verify single-event pump inhibition, EXT arm ordering, pre-emission
clipping/readback failures, cancellation during setup/capture, retained settings,
native preservation, diagnostic plotting, repeat isolation and instrument
ownership. The full offline suite passed **202 tests, 3 skipped and 24 subtests**.
Layout inspection used a hardware-disabled handler. No optical measurement or
pump firing was performed to implement or validate the UI. The new UI path
still requires its first operator-run hardware validation.

### Correction: use the existing MIRcat Sweep Scan controls

The operator clarified that the requested interface was the existing
**MIRcat -> Sweep Scan -> Start Scan** control. The separate Air Scan tab was
an assistant misinterpretation and has been removed; its native records and
validation artifacts remain preserved. The existing MIRcat tab now drives the
exploratory unpumped T660 sweep directly, with the existing **Stop Scan** and
**Emission Off** buttons requesting cancellation while acquisition is running.
The existing **Plotter** receives the detector traces and visibly marks their
provisional axis and nonpublication status.

The failed operator attempt at
`air_scan_20260902T234406_925881Z/` stopped before arming because the new check
rejected an HF2LI PLL center-frequency readback of **2000012.3977661133 Hz**
against the 2 MHz request. This was an overly strict software tolerance, not
evidence of a failed MIRcat arm or emission command. That attempt's cleanup
reported safe idle and retained settings, with no native optical acquisition.
PLL center verification now permits a bounded 20 Hz difference at 2 MHz;
detector rate/filter checks remain strict and the separate measured oscillator
reference check remains in place. The exact saved snapshot that caused the
failure passes the corrected check. A 2.1 MHz PLL reference still fails.

The MIRcat tab's previous scan route selected a campaign candidate, disabled
automated external Process Trigger, and did not provide the new separate
internal pulse settings/current handling. Its exploratory Start Scan action
now uses the tested external-trigger sequence with these changes:

- Start/stop wavenumbers, scan rate, QCL and current come from the existing
  controls. Defaults are 2050 -> 1650 cm^-1, 40 cm^-1/s, QCL 1 and 750 mA.
  Separate scan fields show T660-2 reference/trigger rate and width (2 MHz,
  150 ns) and MIRcat internal rate and width (2.1 MHz, 142 ns). This bounded
  exploratory operation supports one scan per Start; Start can be repeated.
  Invalid duty, rate margin or full-record memory requirements fail before
  devices are opened. The legacy campaign workflow and its gate are retained
  for their existing purpose; no campaign recipe or documentation was changed.
- The normal MIRcat tab's previous SDK session is stopped and released before
  scan ownership. Initialization, arming, TEC readiness, manual-tune clearing,
  external pulse/process configuration and readbacks happen automatically.
  Once the SDK reports waiting for the external process trigger, the emission
  gate is checked. If needed, it is explicitly enabled under the same Start
  authorization and read back before the T660 process event. No pump channel
  is enabled. Successful SDK gate status alone is not optical validation.
- Arm/emission readbacks and progress now update the existing status panel
  during the worker operation. Stop Scan remains available; other instrument
  controls and settings remain blocked until shutdown and saving complete.
  The existing Safety Approval checkbox applies to the displayed unpumped
  operation and physically blocked pump. Numeric settings remain after scans.
- Full dual-detector Pico EXT acquisition, streaming HF2LI data, immutable run
  directories, input clipping checks, provisional marker handling, native
  preservation and nonpublication labels remain. New records are saved under
  `mircat_sweep_<UTC>/`. The launcher option `--mircat-scan` opens the existing
  MIRcat tab's Sweep Scan page directly; `--air-scan` is no longer used.

Validation exercised the existing MIRcat command handler and Start/Stop UI,
SDK-session release, actual control-value forwarding, live status updates,
Plotter delivery, emission-gate enable/readback failure before process firing,
and the recorded PLL readback regression. The full offline suite passed
**207 tests, 3 skipped and 24 subtests**. No new emission or pump operation was
initiated during this correction. Optical operation through the corrected
MIRcat tab remains to be verified by the operator.


### MIRcat Start Scan failure feedback and dark-input diagnosis

The next operator Start attempt, `mircat_sweep_20260902T235457_288595Z/`,
did dispatch and prepare the instruments. It stopped before MIRcat arming
because both HF2LI inputs reported clipping while IR was off. The original
message named only Input 1 because the check raised on the first channel.
Both channels' 100 ms minimum and maximum status values were -128 and both
clipping flags were 1. Cleanup verified IR off, MIRcat disarmed, T660 outputs
idle and numeric settings retained; no sweep or pump event was issued.

A separate read-only check in
`mircat_scan_readonly_diagnostic_20260902T235828_832340Z/` reproduced both
clipping flags and the pinned negative status readings in three samples
spaced over one second. Both inputs remained DC coupled, 50 ohm, single ended,
with approximately 1.0144 V ranges. No detector cause has been established;
power, temperature, connections and dark output level require an operator
check. No HF2LI setting was changed by this diagnostic.

The existing MIRcat tab now keeps command progress and failures visible above
the controls, places Sweep Scan actions and the linked existing Safety Approval
checkbox at the top of the scan page, and allows the long parameter form to
scroll. Native error representations and full saved paths remain in the run
records/log; the visible message uses plain error text, names all clipped
inputs, and reports verified shutdown when available. The clipping preflight
and all hardware interlocks remain enforced.

Targeted backend, existing Start/Stop, recorded clipping-condition and GUI
regressions passed **22 tests**. Offline visual inspection is retained in
`mircat_scan_feedback_validation_20260903T000001_356505Z/`; its displayed error
is a replay of the saved status, not a new acquisition. No optical scan or
pump operation was initiated during this correction. The detector baseline
and first successful scan through the corrected app remain unverified.

### MIRcat progress callback crash correction

After the next operator Start, `mircat_sweep_20260903T000141_198237Z/`,
Windows recorded a native access violation in Qt6Gui.dll at 00:02:01 UTC.
That run had already stopped at the two-input clipping check and completed
verified shutdown and saving. Its SDK readbacks show emission off, disarmed,
no active scan, internal 2.1 MHz / 142 ns settings retained; cleanup reports
both timing units idle, no errors and zero pump events. No optical scan was
captured. The Windows crash report is preserved alongside the correction's
validation in `mircat_gui_crash_fix_20260903T000404_244227Z/`.

A new hardware-free regression reproduced an unsafe GUI update: the scan
worker's context-free progress lambda executed the text/label update on the
worker thread. The test failed before the fix for all four progress messages.
The MIRcat widget now receives progress, state, final result and worker-finish
notifications through explicit queued connections to QObject slots owned by
the GUI thread. Hardware calls remain in the scan worker. This corrects the
identified threading defect consistent with the recorded Qt display crash;
the native crash stack itself was not available in Python stderr.

The targeted suite passed **23 tests**, including the regression that failed
before the fix. A separate Windows Qt display replay completed ten sequential
simulated failed scans and 140 status deliveries, all on the GUI thread, while
painting the interface. The replay used no hardware; its source, report and
screenshot are retained in the validation directory above. The app is relaunched
with Python fault reporting enabled in its redirected stderr for future native
failures. No new emission or pump event was initiated during this fix. The
separate detector dark-input clipping fault remains unresolved.

### Operator-requested 2 V HF2LI range and nonfatal clipping

For the independent MIRcat-tab diagnostic sweep, the operator requested the
maximum input range and removal of the clipping failure. An initial assistant
interpretation incorrectly treated the published 1.5 V input specification as
the software setting limit. The operator corrected this: LabOne accepts 2 V.
The pre-change live Input 1 readback had already been 2.014782648377699 V,
confirming the correction. The initial 1.5 V setting operation is preserved in
`hf2li_max_range_20260903T000839_573415Z/`; it is superseded by the following
operator-corrected setting operation, not an established software maximum.

Both inputs are now requested at **2.0 V**. Live SDK readbacks were
**2.014782648377699 V** for Input 1 and **2.0164402001630966 V** for Input 2,
saved in `hf2li_2v_range_20260903T000908_565521Z/`. The before/after snapshots
show only the two input ranges changed. Coupling, impedance, demodulator rates,
filters and reference settings were retained. Both sampled clipping flags were
zero immediately after the 2 V write; this does not establish that optical
spikes have disappeared. No emission or pump command was sent.

The standalone sweep profile now requests and verifies the operator-confirmed
2 V ranges, allowing the device's small calibrated readback offset. Every
clipping check before arming/setup/process triggering is now informational:
clipping or unavailable clipping status produces a saved warning and acquisition
continues. Status observations before, during and after the sweep, native data,
plots and final UI warnings retain the quality information. Clipping warnings
do not change a completed capture into a failed run. The exploratory plots stay
nonpublication diagnostics and are not accepted as backgrounds. Laser limits,
interlocks, timing/readback verification and safe shutdown remain unchanged.
The fast Phase Scan preset was not changed.

The targeted suite passed **24 tests**, including capture and plotting with
persistently clipped or unreadable clipping flags, preserved native status,
warning-only UI completion, and regression checks against the actual 2 V range
readbacks. The complete recorded post-write HF2LI snapshot also passes the new
scan verification. Two intervening operator attempts at
`mircat_sweep_20260903T000501_193871Z/` and
`mircat_sweep_20260903T000615_006057Z/` remain preserved with the earlier
clipping-stop behavior. This change does not retroactively alter those results.

### Explicit MIRcat emission enable before sweep start

The operator reported no optical emission despite the UI gate status during
`mircat_sweep_20260903T003520_142287Z/`. Its command log confirms one successful
`MIRcatSDK_StartSweepScan` call but **no `MIRcatSDK_TurnEmissionOn` call**. The
post-start SDK status reported emission on, so the previous conditional
emission-enable path skipped the command. The transport capture completed
(about 9.9947 s Sweep Active, 80/81 markers, both detector streams and Pico
records); this is not evidence of optical emission. Cleanup verified safe idle
and retained settings. Native records and their original classification remain
preserved.

The existing MIRcat-tab sweep now always issues `MIRcatSDK_TurnEmissionOn`
**before** `MIRcatSDK_StartSweepScan`, even if a getter already reports on.
The local SDK header requires tuning before emission enable and cancellation
of single/manual tune before a sweep. The sequence therefore arms/waits for
TECs, tunes to the requested start wavenumber, waits for tuned status,
reapplies/verifies external trigger settings, explicitly enables emission and
checks the SDK readback, then cancels manual tune and checks pulse settings
before scan start. T660-2 CHB remains disabled through tuning, emission enable
and the manual-tune transition. The existing post-start gate recheck/re-enable
and Pico-arm-before-process-trigger ordering remain.

`mircat_tuned_before_emission.json`, `mircat_trigger_after_tune.json` and
`mircat_emission_before_scan.json` record preparation and the explicit command
readback. Native metadata records separate emission-gate checks; the SDK getter
no longer marks `optical_valid` true. Failed tune/cancellation or failed emission
readback prevents sweep/process triggering and runs normal cleanup. HF2LI 2 V
ranges, nonfatal clipping, the 40 cm^-1/s scan and separate 2 MHz external /
2.1 MHz internal pulse settings remain unchanged.

The two command-order regressions failed against the earlier implementation
and pass after the correction. The targeted suite passed **29 tests**, covering
explicit enable with an already-on getter, pre-start enable failure, post-start
gate closure/re-enable, cancellation during tune and manual-tune exit failure.
Validation is hardware-free; no new emission or pump operation was initiated
for this correction. Optical emission through the revised UI sequence remains
to be verified on the next operator-run sweep.

### Retrospective script-versus-UI comparison after persistent no-light report

The operator's next app scan, `mircat_sweep_20260903T020532_909748Z/`, still
showed no optical response by the operator's observation. The native command
log now confirms `MIRcatSDK_TurnEmissionOn -> 0 (SUCCESS)` at 02:05:58 UTC,
followed by successful manual-tune cancellation and `StartSweepScan` at
02:05:59 UTC. Thus the explicit SDK command was executed; that fact does not
establish actual optical output. The capture and verified cleanup completed.

Comparison with the older scripted scans identifies that the large detector
change predates the UI conversion. The script run at 23:19:23 UTC (before the
reported detector-location swap) had full-record Pico A/B means of about
+0.098/+0.332 V and in-sweep HF2LI R medians of 68.933/250.568 mV. The script
run at 23:28:46 UTC, after the reported swap, already had Pico means of
-1.477/-1.484 V and both HF inputs clipped. The latest app scan has Pico means
of -1.474/-1.478 V with the 2 V HF ranges and R medians near 0.001 mV. These
are electrical channel labels; the physical arm/cable mapping remains unconfirmed.

T660-2 optical-train and T660-1 process settings match across those runs apart
from timestamps/counters. MIRcat configured timing, current and trigger values
also match. The actual differences include the UI's explicit tune/enable/cancel
sequence, 2 V rather than 1 V HF input ranges, and shutdown before USB transfer
after capture readiness. The same dark-offset behavior in the earlier script
means there is not yet evidence for a UI-specific optical failure. It also does
not identify the cause: actual trigger delivery at MIRcat TRIG IN, direct laser
output, beam path and detector/electrical state are not distinguished by these
records. No new hardware command or implementation change was made for this
comparison. Its machine-readable metrics and source-run references are saved
in a new `mircat_ui_script_comparison_<UTC>/comparison.json` record.

### External optical trigger diagnosis after repeated no-light reports

The operator clarified that the MIRcat can flash its emission LED and sound its
beeper without optical output in both manufacturer and custom software, and that
actual output has required T660 timing with MIRcat in External Trigger mode.
The LED, beeper, successful SDK emission enable and emission/light-valid getters
therefore remain controller indications, not optical evidence. This report does
not identify a detector fault or establish a repaired laser.

Inspection confirms that the current scan requests SDK pulse mode 2 (External
Trigger), separate from external process-trigger mode 2. The tested pair remains
T660-2 CHA/CHB at 2 MHz / 150 ns and MIRcat internal settings at 2.1 MHz / 142 ns /
750 mA. The 2.1 MHz setting is not the reference or expected optical pulse rate.
The fixed-wavenumber alignment workflow enables CHB before T660 START, whereas
the scan enables CHB after starting the reference train. The local Highland
T660 Programming Guide, pages 69 and 71, specifies that CHANnel:ON modifies the
active configuration immediately and forces an end-of-delay. A missing second
START is therefore not an established fault, and the sequence was not changed
on that hypothesis.

One diagnostic gap was corrected in the existing scan workflow: external pulse
and process modes, marker endpoints/interval/units and dwell settings are now
read back after manual-tune cancellation, after StartSweepScan returns, and
immediately before the external process event. Each check is preserved in a
separate JSON file and native metadata, including a mismatched readback on
failure. A mode mismatch stops the operation and performs cleanup before firing
the process event. No new setting writes, automatic retry, internal triggering
fallback, or optical acceptance claim was added. A successful check still does
not prove that pulses arrive at the MIRcat input or produce optical output.

The targeted offline suite passed **33 tests**, including simulated mode changes
at each of the three transitions with a successful emission-enable readback,
absence of a process event after those failures, retained diagnostic records,
and verified cleanup. No emission or pump operation was initiated for this
change. Actual CHB timing at the connected MIRcat TRIG IN and the laser's optical
response still need a physical measurement; previous scan captures contain the
two detector channels and Sweep Active, not a direct measurement of TRIG IN.

### Authorized direct repeat of the pre-GUI air-scan sequence

At the operator's explicit request to control MIRcat directly and repeat the
earlier scan, one scan was executed from a new standalone copy of the original
`run_standalone_air_keep_settings.py`. The custom app had exited and PicoScope 7
was not running before SDK acquisition. The original StartSweepScan preparation
sequence was used, without the later GUI workflow's fixed-wavelength
tune/enable/cancel preparation. The copy retains the operator's later 2 V HF2LI
range request, nonfatal clipping, cooperative cancellation, fresh authorization,
and external-mode readback before the process event. Original scripts and runs
were preserved. The SDK gate read back on after scan setup; no conditional
additional emission-enable command was needed.

The direct run is
`evidence/experiments/runs/direct_air_repeat_20260903T023625_729904Z/acquisition_20260903T023638_592526Z/`.
It scanned 2050 to 1650 cm^-1 at 40 cm^-1/s, 750 mA, with T660-2 CHA/CHB at
2 MHz / 150 ns and MIRcat external optical triggering with internal settings
2.1 MHz / 142 ns. The HF detector streams read back 1798.930921 Sa/s, 1.001889 ms
time constant, order 4 and requested 2 V input ranges. The HF reference read
approximately 1,999,938 Hz before and 2,000,043 Hz after acquisition.

Capture and transfer completed without acquisition or cleanup errors: one
external non-pump process event, 9.994755657 s Sweep Active, 80 of 81 expected
markers, 17,980 in-sweep samples per HF detector with no internal gaps, and
218,755,418 Pico samples per channel with no overflow. Sixteen sampled in-sweep
HF status checks showed no clipping. The wavelength axis remains provisional
because the endpoint marker identity is unresolved.

Direct control did not recover the earlier optical-looking detector spectra.
HF R medians were approximately 0.000936 and 0.001062 mV (0.936 and 1.062 uV),
and full-record Pico A/B means were -1.47610 and -1.48046 V. This reproduces the
near-baseline detector response under the original direct sequence; it does not
isolate trigger delivery, laser response or detector state. SDK gate status was
recorded separately and optical validity was not asserted. Native data, the
plot, CSV and `direct_scan_verification.json` are retained; this is not a usable
MbCO background or a publication result.

Shutdown verified MIRcat emission off, disarmed and no active scan, followed by
SDK deinitialization and both T660 units idle. There were zero pump events.
Requested MIRcat and HF2LI numeric settings were retained without corrective
writes or restoration to the fast Phase Scan preset.

### Direct repeat after operator-reported MIRcat power cycle

The operator reported power-cycling MIRcat and explicitly requested another
attempt. One direct scan used the same hardware sequence and settings as the
preceding direct run, with a fresh SDK session and readback verification. Its
records are in
`evidence/experiments/runs/direct_air_after_powercycle_20260903T023954_119062Z/acquisition_20260903T023959_459976Z/`.
The custom app and PicoScope 7 were not running before acquisition. No software
timing changes were introduced for this repeat.

The operator watched HF2LI during the sweep and reported that there was still no
optical signal. Saved data agree with the lack of recovered detector response:
in-sweep HF R medians were 0.967 and 1.075 uV, with Pico full-record means of
-1.47411 and -1.48383 V. External pulse and process mode 2 read back correctly,
and the SDK emission flag was true; none establishes actual optical output.
The power cycle did not resolve the observed fault.

Acquisition recorded 9.994755657 s Sweep Active, 80/81 expected markers,
17,980 samples per HF detector without internal gaps, and 218,755,418 samples
per Pico channel without overflow. Sixteen in-sweep status checks showed no
HF clipping. There was exactly one process event and zero pump events. Native
data, plot, CSV and the operator observation in `direct_scan_verification.json`
are preserved as diagnostic evidence, with optical validity false and a
provisional wavenumber axis. Cleanup verified emission off, disarmed, no active
scan and both T660 units idle; MIRcat and HF settings were retained without
corrective writes or fast-preset restoration.

### Operator-requested External Pulse / SDK External Passthrough trial

The operator explicitly requested External Pulse instead of External Trigger.
The direct script therefore selected `MIRcatSDK_PULSE_MODE_EXTERNAL_PASSTHRU`
(SDK mode 3), documented in the local SDK header as following the external TTL
signal subject to limits. External process mode remained 2. T660-2 CHA/CHB stayed
at 2 MHz / 150 ns; MIRcat internal settings remained 2.1 MHz / 142 ns / 750 mA.
The same 2050-to-1650 cm^-1, 40 cm^-1/s single scan and HF2LI 2 V input settings
were retained. Both the internal settings and external TTL train were checked
against SDK pulse-rate, width and duty limits before arming.

The first setup,
`direct_air_external_pulse_20260903T024207_749523Z/acquisition_20260903T024213_710724Z/`,
returned SDK error 95 (`TECS_NOT_AT_SET_TEMPERATURE`) from StartSweepScan after
an earlier ready readback. No process event or capture occurred. Cleanup
verified emission off, disarmed and timing units idle; the failed attempt and
its native records remain preserved.

The same requested scan was then prepared with armed status and TEC readiness
required continuously for five seconds, bounded by a 120-second timeout and
rechecked before scan start. No timing or current values were changed. This
continuation completed in
`direct_air_external_pulse_tec_settle_20260903T024327_956949Z/acquisition_20260903T024334_438469Z/`.
External Pulse mode 3 was read back before the single process event. Capture
recorded 9.994755657 s Sweep Active, 80/81 expected markers, 17,980 HF samples
per detector without internal gaps, and 218,755,418 Pico samples per channel
without overflow. Fifteen sampled in-sweep HF checks showed no clipping.

External Pulse did not recover the previous optical-looking spectra at these
settings: HF R medians were 1.010 and 1.336 uV, and full-record Pico means were
-1.47377 and -1.48991 V. This remains a failed optical demonstration with timing
and acquisition evidence; the trigger-delivery/laser/detector cause is unresolved.
The native data, plot, CSV and `direct_scan_verification.json` are preserved.
The provisional wavelength axis is not an accepted background or publication
result. Cleanup verified emission off, disarmed, no active scan and both T660
units idle, with zero pump events. Mode 3 and all numeric settings remained
selected after shutdown. The custom UI implementation was not changed to use
mode 3 by this bounded direct trial.

### Authorized 1000 mA comparison of all three pulse modes

The operator explicitly authorized increasing current to 1000 mA and testing
Internal Trigger, External Trigger and External Pulse. Three direct single
scans were completed sequentially in
`evidence/experiments/runs/direct_air_1000ma_three_modes_20260903T024905_977175Z/`,
under case directories `01_internal_trigger`, `02_external_trigger` and
`03_external_pulse`. Each run read back its requested SDK pulse mode (1, 2 or 3)
and 1000 mA. Live SDK current limits were 0 to 1000 mA. Rate, width and duty
limits were checked before arming. Each case completed on its first setup
attempt, with five seconds of stable armed/TEC-ready status before starting.

All three retained the 2050-to-1650 cm^-1, 40 cm^-1/s sweep, internal settings
2.1 MHz / 142 ns, HF2LI 2 V ranges, and 2 MHz T660 reference. In Internal Trigger
mode, T660-2 CHB remained disabled and the direct PicoScope detector waveforms
were the optical-output diagnostic. HF2LI remained referenced to 2 MHz and was
therefore not a valid optical-absence test for the independently timed internal
2.1 MHz mode. In modes 2 and 3, CHB supplied the 2 MHz / 150 ns external train.
External process triggering and the pump-disabled T660-1 CHC route were retained
for every scan. The external rate was never relabeled as 2.1 MHz.

None recovered the previous optical-looking response. Pico A/B full-record
means were respectively -1.47460/-1.49014 V in Internal Trigger,
-1.47672/-1.49614 V in External Trigger, and -1.47814/-1.49722 V in External
Pulse, with no resolved optical pulse train in the inspected direct waveforms.
The external-mode HF R medians were 0.955/1.061 uV for mode 2 and 1.045/1.431 uV
for mode 3. Internal-mode HF values are preserved but excluded from the displayed
HF comparison because the reference frequencies differ. No optical validity,
background acceptance or publication claim was established. These records do
not distinguish absent MIRcat output from a nonresponding detector/optical path.

Every case recorded approximately 9.9947 s Sweep Active and 80/81 expected
markers, with 17,980 detector samples per HF channel in the first two cases and
17,979 in the third, without internal stream gaps. Each transferred
218,755,418 samples per Pico channel with no overflow. Sampled clipping flags
were clear (16, 16 and 17 checks per channel, respectively). There was one
process event per case and zero pump events. The individual native records,
plots, CSV files, current-limit snapshots, `comparison.json`, analysis source
and `three_modes_comparison.png` are retained in the comparison directory.
The wavenumber axes remain provisional.

Shutdown and numeric-setting retention were verified after every case before
the next case began. Final MIRcat state was emission off, disarmed and no active
scan, with SDK deinitialized and both T660 units idle. Current remains 1000 mA,
SDK pulse mode remains 3 (External Pulse), and the internal settings and HF2LI
settings remain as requested. No custom-app implementation or campaign,
calibration, characterization or completed-history documentation was changed
for this comparison.

### Final evening reset trial with explicit SDK emission enable

The operator reported unplugging MIRcat and holding its power button for
30 seconds, then authorized another three-mode comparison at the retained
1000 mA setting, explicitly requiring SDK Emission ON calls in the two external
modes. This is an operator-reported power-reset attempt, not confirmation of a
factory reset. Records start in
`evidence/experiments/runs/direct_air_reset_explicit_on_three_modes_20260903T025720_147056Z/`.

Internal Trigger completed in
`01_internal_trigger/acquisition_20260903T025730_420432Z/` with CHB disabled.
The first External Trigger preparation called `MIRcatSDK_TurnEmissionOn` while
the sweep was waiting for its external process event. Despite an ON gate
getter, the explicit call returned **94, LASER_NOT_TUNED**. No process event was
sent and no optical scan was acquired in this failed preparation. Its error,
gate readback and verified shutdown remain preserved in
`02_external_trigger/acquisition_20260903T025829_924698Z/`.

The remaining two modes continued in the derived child directory
`external_modes_tuned_enable_20260903T030043_994330Z/`, satisfying the SDK header's
requirement to tune before `TurnEmissionOn` and cancel manual tune before a
sweep. With CHB disabled, each mode tuned to 2050 cm^-1, read back tuned status,
reapplied and verified the requested external mode, explicitly called
`MIRcatSDK_TurnEmissionOn`, then cancelled manual tuning and checked its settings
before enabling CHB and starting the sweep. Both SDK enable calls returned
**0, SUCCESS**, with emission-gate readback changing from false to true:
03:01:35 UTC for External Trigger and 03:02:34 UTC for External Pulse. Both
completed captures and verified shutdown. No second completed Internal Trigger
scan was performed. The child comparison includes the already-completed
Internal Trigger record through its source path.

The operator explicitly confirmed that **none of the three modes produced
light**, and ended the evening. Direct Pico waveforms remained near the dark
baseline. Full-record Pico A/B means were -1.47566/-1.49258 V for Internal
Trigger, -1.47609/-1.49557 V for External Trigger and -1.48067/-1.49811 V for
External Pulse. External-mode HF R medians were approximately 0.966/1.077 uV
and 1.038/1.461 uV respectively. Internal-mode HF amplitude is not interpreted
as an optical-absence test because its internal 2.1 MHz setting is independent
of the retained 2 MHz HF reference. Every completed case retained a full dual
Pico record and about ten seconds of Sweep Active with 80/81 expected markers;
the provisional axes and controller flags do not establish optical validity.

The final child directory preserves `comparison.json`,
`three_modes_comparison.png`, the comparison source, per-mode explicit-enable
JSON records, and `operator_end_of_evening.json`. Initial failures and all native
records remain intact. The fault is unresolved; no usable background, optical
phase-scan reconstruction or publication result was demonstrated.

End-of-evening shutdown is verified: MIRcat emission off, disarmed, no active
scan, SDK deinitialized, both T660 units idle and zero pump events. No scan
helper or custom-app process remains running. Retained settings are 1000 mA
(the SDK-reported maximum), External Pulse / SDK mode 3, internal 2.1 MHz /
142 ns, T660 timing values 2 MHz / 150 ns, and the slow HF detector settings
1798.930921 Sa/s, 1.001889 ms, order 4, requested 2 V ranges. The fast Phase Scan
preset was not restored. Fresh operation authorization is required before the
next emission/pump action. The next investigation should distinguish actual
MIRcat output and TRIG IN pulse delivery from detector/beam-path response;
repeating full scans has not located the cause. No overnight operation or
automatic follow-up was scheduled.

### Fixed 1850 cm^-1 three-mode optical-output test

After MIRcat remained powered off overnight, the operator explicitly authorized
repeating the three pulse-mode comparison at a single 1850 cm^-1 setpoint instead
of starting another scan. The direct fixed-illumination records are in
`evidence/experiments/runs/fixed_1850_three_modes_20260903T175753_281072Z/`.
PicoScope 7 was confirmed closed before SDK access. No sweep or process trigger
was started, T660-1 was forced idle, the pump remained physically blocked, and
there were zero pump events.

Internal Trigger (SDK mode 1), External Trigger (mode 2) and External Pulse /
Passthrough (mode 3) each completed a one-second emission-off baseline, a
ten-second commanded-emission interval and an emission-off post-check. Every
case used QCL1 at 1850 cm^-1 and 1000 mA. MIRcat's internal settings read back
2.1 MHz / 142 ns. T660-2 CHA supplied only the 2 MHz / 150 ns HF2LI external
reference in all cases; CHB remained disabled for Internal Trigger and supplied
the 2 MHz / 150 ns MIRcat input only during the two external-mode emission
intervals. Both internal and external duty fractions were checked against the
SDK limit. The 2.1 MHz internal setting was never used as the HF2LI reference or
as the expected external optical-opportunity rate.

All three explicit `MIRcatSDK_TurnEmissionOn` calls returned **0, SUCCESS**, with
the emission-state getter changing from false to true after the controller
reported armed, TEC ready and tuned. Each mode read back the requested pulse
mode, 1850 cm^-1 setpoint, approximately 5.4054 microns actual wavelength and
the SDK `light_valid` flag. These are controller states and do not prove optical
output. HF2LI readback verified requested 2 V input ranges, 1798.930921 Sa/s
detector streams, 1.001889 ms time constants, order 4 and the 2 MHz reference;
all sampled clipping flags were clear. The settings remained unchanged in the
post-run comparisons.

No mode produced a usable, matching dual-detector optical turn-on. In External
Trigger, the emission-on minus baseline HF median changes were -0.017 uV and
-0.105 uV for inputs 1 and 2. In External Pulse they were +0.076 uV and
+0.389 uV. The latter input-2 shift follows the commanded interval but remains
at the microvolt noise/drift scale, lacks a corresponding input-1 response and
has no resolved PicoScope counterpart, so it is not accepted as detected MIR
transmission. Internal-mode HF amplitudes are retained as diagnostic data only
because the internally generated 2.1 MHz optical timing is deliberately not the
2 MHz HF2LI reference. Auto-triggered, free-running Pico captures were used
because fixed tuning supplies no new Sweep Active edge; their dark and
commanded-on distributions overlap for both detectors in every mode.

The clearer offline view is `fixed_1850_three_modes_v2.png`, with numeric
comparisons in `comparison_v2.json`; original native HF2LI chunks, Pico arrays,
SDK command logs, raw readbacks and the first diagnostic plot remain preserved.
This is a failed optical-output diagnostic and a nonpublication exploratory
record, not a background or MbCO result.

One immediate Internal Trigger cleanup readback briefly retained the SDK's
100%-complete scan-status bit after fixed manual tuning, although emission and
armed were already false. The next case began with that bit clear. A fresh final
SDK session recorded emission off, disarmed, untuned and no scan in progress,
with External Pulse mode 3 and 2.1 MHz / 142 ns / 1000 mA retained. Raw live
T660 readbacks recorded trigger sources OFF and channels A-D OFF on both units.
The companion interpretation record corrects an initial derived Boolean that
mistakenly treated the structured channel-state objects as truth values; it does
not alter the raw readbacks. Final hardware state is safe and the SDK is
deinitialized. Fresh operation authorization remains required before another
emission or pump action.

### Fixed 1850 cm^-1 three-mode retest after wiring correction

The operator reported correcting a possible wiring error and explicitly
authorized repeating the three fixed-setpoint pulse-mode tests. The append-only
retest record is in
`evidence/experiments/runs/fixed_1850_three_modes_retest_20260903T185413_4414657Z/`.
The red alignment pointer was turned off and its SDK session was closed before
IR operation. T660-1 was forced idle, the pump remained physically blocked and
there were zero pump events.

Internal Trigger (SDK mode 1), External Trigger (mode 2) and External Pulse /
Passthrough (mode 3) each completed a one-second emission-off baseline, a
ten-second commanded-emission interval and an emission-off post-check at
1850 cm^-1 and 1000 mA. The same separated timing roles were retained: MIRcat
internal 2.1 MHz / 142 ns, T660-2 2 MHz / 150 ns for external optical triggering,
and HF2LI external reference 2 MHz. All explicit emission-enable SDK calls
returned success. HF2LI readbacks retained the requested slow acquisition
settings and 2 V ranges; all sampled clipping flags were clear.

Unlike the preceding no-light record, External Trigger produced a
commanded-ON increase on both HF2LI inputs and both returned toward the
pre/post emission-off level. Relative to the median of the pre- and post-off
medians, the retest steps were **+0.182 uV** and **+0.780 uV** for inputs 1 and
2, compared with **-0.030 uV** and **-0.076 uV** in the preceding fixed test.
The timing and dual-input polarity are evidence consistent with restored
optical output after the wiring correction. This remains an uncalibrated,
nonpublication diagnostic rather than a completed optical validation or MbCO
result.

Internal Trigger HF amplitudes remain diagnostic only because MIRcat's 2.1 MHz
internal pulse train is deliberately not used as the 2 MHz HF2LI reference.
External Pulse produced a positive input-2 step but did not produce matching
response polarity on both HF inputs. The free-running PicoScope DC
distributions did not independently resolve emission-on changes. Detector
imbalance and the lack of a direct calibrated power measurement therefore
remain explicit limits. The original automatically generated
`comparison_v2.json` is preserved; its fixed no-light interpretation was not
used for this changed data. The derived comparison and limits are in
`wiring_retest_interpretation.json`, with the visual comparison in
`wiring_retest_comparison.png` and reproducible analysis source beside them.

The final External Pulse cleanup initially found the controller's fixed-tune
scan-active flag still set at 100% even though emission and armed readbacks were
already false. A separate final SDK session cleared and verified the scan state.
MIRcat is now emission off, disarmed, untuned, with no scan active and the SDK
deinitialized. Both T660 trigger sources and all channels A-D read back OFF.
The append-only interpretation record corrects the same structured-readback
Boolean bug in the shutdown helper while retaining its raw record. MIRcat
numeric settings remain 2.1 MHz / 142 ns / 1000 mA and External Pulse mode 3;
the HF2LI slow-test settings remain in place. Fresh operation authorization is
required before another IR-emission or pump action.

### Updated MIRcat GUI and detector power-cycle recovery

The operator reported that Daylight supplied updated MIRcat Control Panel
version v1.11.1. In Internal Pulsed operation at 1850 cm^-1, the operator
observed emission on photochromic paper. This is the first direct qualitative
optical-output confirmation after the no-light fault. The operator then
power-cycled both detectors and reported that their HF2LI signals returned.
Operator-provided screenshots and a structured observation are preserved in
`evidence/experiments/runs/detector_power_cycle_confirmation_20260903T212437_0377633Z/`.

The MIRcat screenshot shows QCL1 tuned to 1850.0 cm^-1 (5.405 microns), Pulsed
mode, 2.0 MHz, 150 ns and 750 mA, with armed and emission indicators active.
The HF2LI screenshot shows stable demodulator-R levels of approximately 455 mV
and 500 mV on inputs 1 and 2, both at 2 V range, after the detector power
cycle. This supports a detector/electronics-state explanation for the preceding
microvolt-level HF records and means those pre-power-cycle records must not be
used to characterize optical throughput.

The screenshot is a fixed-illumination diagnostic rather than a phase-scan
configuration. HF2LI oscillator 1 and demodulators 1/4 are visibly in Manual
2 MHz reference mode, with approximately 224.9 Sa/s transfer and 1.002 ms time
constants. Before phase-scan acquisition, the HF2LI must use the actual T660
external reference and the phase-scan detector settings of 20 kSa/s and 50 us.
The planned external-trigger timing roles remain T660-2 CHA to HF2LI EXT REF at
2 MHz / 150 ns and T660-2 CHB to MIRcat TRIG IN at 2 MHz / 150 ns. MIRcat's
separate internal settings remain 2.1 MHz / 142 ns / 750 mA for the planned
external-trigger workflow; the 2.0 MHz / 150 ns values visible during this
Internal Pulsed diagnostic must not silently replace them. No pump operation or
MbCO result is claimed from this observation.

### Successful external-trigger air scan after detector recovery

The operator explicitly authorized one direct 2050 to 1650 cm^-1 air scan at
40 cm^-1/s using MIRcat External Trigger mode, separate MIRcat internal
2.1 MHz / 142 ns / 750 mA settings, and T660-2 2 MHz / 150 ns outputs for both
the HF2LI external reference and MIRcat TRIG IN. PicoScope 7 was closed before
SDK access. The pump remained physically blocked, T660-1 pump outputs remained
disabled and there were zero pump events. The append-only operation root is
`evidence/experiments/runs/authorized_air_scan_after_detector_recovery_20260903T213002_3743882Z/`.

The first preparation in `mircat_sweep_20260903T213017_174260Z/` did not fire a
process trigger or acquire a sweep. After the required manual tune and emission
enable, `MIRcatSDK_StartSweepScan` returned 95,
`TECS_NOT_AT_SET_TEMPERATURE`. The workflow stopped emission and both T660
units, verified safe state, retained all configuration and diagnostic records,
and did not reuse this failed preparation as scan evidence.

The control workflow was updated to require MIRcat armed and TEC-ready status
continuously for five seconds after arming and again after leaving manual tune,
before T660-2 CHB is enabled or `StartSweepScan` is called. The focused air-scan
suite passed **26 tests** after the change. The targeted retry completed in
`mircat_sweep_20260903T213236_758472Z/`.

The successful run read back MIRcat pulse mode 2 (External Trigger), external
process triggering, 2050/1650 cm^-1 endpoints and 5 cm^-1 markers without
mismatch immediately before the process event. QCL1 read back 2.1 MHz, 142 ns
and 750 mA; its internal duty fraction was 0.2982 against the SDK 0.30 maximum.
T660-2 channels A and B read back enabled at 2 MHz / 150 ns for the scan. The
HF2LI reference read 1,999,991.73 Hz before the process event. Exactly one
T660-1 process event was sent only after PicoScope EXT was armed; pump channels
remained disabled.

Observed Sweep Active duration was 9.994755657 s. Each HF detector stream
contained 17,980 in-sweep samples with zero internal gaps and no clipping in 23
sampled status checks. PicoScope A and B each transferred 218,755,418 samples
at 48 ns/sample with no overflow, covering the rising Sweep Active edge through
the complete sweep and approximately 5 percent post-sweep tail. Both detector
systems show the same scan envelope and aligned troughs: sample/reference
Pearson correlation was 0.9722 for HF2LI and 0.9728 for 4.8 ms Pico block means.
This is a successful optical and acquisition checkout and resolves the prior
missing-detector-signal fault after detector power cycling.

The HF2LI observed 80 of 81 requested wavelength-marker rising edges. Because
the endpoint-marker identity remains unresolved, the displayed wavenumber axis
is explicitly provisional between the observed Sweep Active edges. The record
is not accepted as an unpumped sample background and is not publication
eligible. Native data, the plotted scan, readbacks and the derived all-checks
verification are retained; `scan_test_verification.json` is the first derived
record and the corrected `scan_test_verification_v2.json` clarifies that the
post-transfer HF reference value was read only after T660 shutdown.

Final readbacks verified MIRcat emission off, disarmed, untuned and with no
active scan; the SDK was deinitialized. Both T660 trigger sources and channels
A-D read back OFF. Numeric MIRcat settings remain 2.1 MHz / 142 ns / 750 mA in
External Trigger configuration, and the standalone-scan HF2LI settings remain
in place. No automatic follow-up emission or pump action was started.

### Detector-orientation etalon retest

The operator changed a detector's orientation and explicitly authorized an
otherwise identical repeat air scan to test whether the regular fringes were
removed. The red alignment pointer was turned off and verified off before the
scan. Records are in
`evidence/experiments/runs/air_scan_detector_orientation_retest_20260903T214018_1110992Z/`,
with the completed scan in `mircat_sweep_20260903T214023_642369Z/`.

The repeat completed without an acquisition or cleanup error using the same
2050 to 1650 cm^-1, 40 cm^-1/s, External Trigger configuration. Sweep Active
was again 9.994755657 s; both HF2LI channels contained 17,980 samples with no
in-sweep gaps or clipping, both Pico channels contained 218,755,418 samples at
48 ns with no overflow, and 80 of 81 marker rising edges were observed. There
was one process event, zero pump events, and final readbacks verified MIRcat
emission off/disarmed/no scan with both T660 units idle.

A reproducible before/after comparison removes a 10 cm^-1 Hann-smoothed
envelope over 1900 to 2000 cm^-1 and measures the residual fringe RMS and the
dominant component from 0.15 to 0.60 cycle/cm^-1. Input 1 relative residual RMS
increased **18.48 percent** and its dominant fringe amplitude increased
**13.86 percent** after the orientation change. Input 2 residual RMS changed
**-1.56 percent** and its dominant amplitude changed **+0.28 percent**. The
regular fringe period and structure persist. The orientation change therefore
did not remove the etalons; input 1 became modestly worse while input 2 was
effectively unchanged. Because the operator did not identify which input's
physical detector was reoriented in the record, the conclusion is reported for
both channels without assigning the mechanical change to one of them.

The normalized overlays and residuals are preserved in
`detector_orientation_comparison.png`, with method and numeric metrics in
`detector_orientation_comparison.json` and analysis source beside them. Both
scans retain provisional wavenumber axes because the endpoint marker identity
remains unresolved. This is an exploratory optical-path diagnostic and not a
background or MbCO result.

### Post-alignment repeat air scan

The operator used the red alignment pointer, then explicitly requested that it
be turned off and authorized another otherwise identical External Trigger air
scan. The pointer was verified off and its SDK session closed before
acquisition. The append-only run is in
`evidence/experiments/runs/air_scan_post_alignment_repeat_20260903T214445_6204197Z/`,
with native acquisition in `mircat_sweep_20260903T214450_404110Z/`.

The scan completed without acquisition, save or cleanup errors. Observed Sweep
Active duration was 9.994720914 s; both HF2LI channels contained 17,979 samples
with zero in-sweep gaps and no clipping in 22 sampled checks. Both PicoScope
channels contained 218,755,418 samples at 48 ns with no overflow. The HF2LI
again observed 80 of 81 requested wavelength-marker rising edges, so the
wavenumber axis remains provisional. There was one process event and zero pump
events. Final readbacks verified MIRcat emission off, disarmed and no active
scan, with both T660 units idle and the red pointer off.

The same 1900 to 2000 cm^-1 relative-fringe metric was applied to the initial,
orientation-test and post-alignment scans. Relative to the immediately
preceding orientation test, input 1 mean signal decreased 26.97 percent and its
fringe RMS decreased only 3.41 percent, while its dominant relative fringe
amplitude increased 7.69 percent. Relative to the initial recovered-detector
scan, input 1 fringe RMS remains 14.44 percent higher and dominant relative
fringe amplitude remains 22.62 percent higher. Input 2 stayed effectively
unchanged: versus the preceding scan its RMS changed +0.20 percent and dominant
amplitude changed -0.03 percent. The lower input-1 absolute level therefore
does not represent removal of the etalon; the relative periodic structure
persists.

The three normalized scans and fringe residuals are preserved in
`post_alignment_three_scan_comparison.png`, with method and values in
`post_alignment_three_scan_comparison.json` and analysis source beside them.
This remains an exploratory optical-path diagnostic, not a background or MbCO
result.

### Offline phase-sensitive etalon comparison preparation

No fresh MIRcat-emission authorization was provided for this continuation, so
no instrument SDK session was opened and no laser, T660 output, scan or pump
operation was started. The previously verified safe final hardware state was
not changed.

A read-only adjacent-scan analyzer was added in
`software/control_app/workflows/air_scan_etalon.py`. It reads only the completed
`detectors.csv` products. In the provisional 1900 to 2000 cm^-1 region it works
in natural-log detector-amplitude space, removes a 10 cm^-1 Hann-smoothed broad
envelope, robustly downweights outliers, and fits a sinusoid with slowly varying
amplitude. It reports independent frequencies and a shared-frequency phase and
amplitude comparison at the common region center. It also calculates the
diagnostic adjacent ratio difference `-log10[(S2/R2)/(S1/R1)]`. These quantities
are explicitly diagnostic and are not a background-acceptance or hardware gate.

Four synthetic tests verify recovery of continuous frequency, amplitude and
phase, cancellation for a stable adjacent pair, exposure of imposed phase
drift, and rejection of incomplete detector CSV input. The focused air-scan and
etalon suite passed **30 tests**. `git diff --check` reported no whitespace
errors; the existing Windows line-ending warnings remain informational.

The tool was exercised without hardware against the three existing scans in
`evidence/experiments/runs/offline_etalon_phase_reanalysis_20260903T230414_3082045Z/`:

- Initial versus detector-orientation retest, input 1: shared frequency
  0.2719769 cycle/cm^-1 (3.67678 cm^-1 period), -7.890 degree phase shift and
  +20.330 percent fitted log-amplitude change. The adjacent ratio-difference
  RMS was 0.0374891 absorbance unit and its fitted component at the input-1
  frequency was 0.0222094 absorbance unit.
- Orientation retest versus post-alignment repeat, input 1: shared frequency
  0.2733200 cycle/cm^-1 (3.65872 cm^-1 period), -146.455 degree phase shift and
  +0.232 percent fitted log-amplitude change. The adjacent ratio-difference RMS
  was 0.2018620 absorbance unit and its fitted component was 0.2023885
  absorbance unit. The nearly unchanged fitted amplitude therefore does not
  imply cancellation when the phase changes by almost half a cycle.
- Input 2 remained comparatively stable in phase in both comparisons
  (+0.298 and -0.226 degree), while its fitted amplitude changed +6.526 and
  +0.077 percent respectively. Its much smaller residual and different
  approximately 0.239 cycle/cm^-1 component remain separate from the dominant
  input-1 fringe.

The continuous robust-fit frequencies are method-dependent estimates on the
provisional axes. Their approximately 3.66 to 3.68 cm^-1 periods are consistent
with the earlier FFT-bin description of an approximately 3.6 cm^-1 input-1
fringe; the reanalysis does not revise the unresolved endpoint-marker identity.
Both comparisons include an operator-reported physical adjustment, so neither
can answer whether an immediately adjacent, untouched background will cancel
the fringe. The next discriminating hardware diagnostic remains two separately
preserved, otherwise identical external-trigger air scans without touching the
optics between them. Fresh authorization is required before each new MIRcat
IR-emission operation; pump firing remains separately unauthorized and disabled.

The complete offline software suite subsequently passed **223 tests, 3 skipped,
and 24 subtests**. No hardware operation occurred during that validation.

An additive sign-convention check then found that the first diagnostic record
fit `log10[(S2/R2)/(S1/R1)]` while labeling the plotted fit with the requested
negative-log ratio-difference convention. The reported RMS, amplitude magnitude,
detector phase shifts, frequencies and periods are unchanged, but the fitted
ratio-difference phase would differ by 180 degrees. The original record remains
preserved. Corrected reports and plots using the stated
`-log10[(S2/R2)/(S1/R1)]` sign are in
`evidence/experiments/runs/offline_etalon_phase_reanalysis_v2_20260903T230619_5930905Z/`.
A regression now verifies the ratio-fit sign against the calculated absorbance
array. This correction used no hardware.

After the sign correction, the complete offline suite again passed **223 tests,
3 skipped, and 24 subtests**; `git diff --check` again reported no whitespace
errors apart from the existing informational Windows line-ending warnings.

### Consecutive no-touch air-scan etalon stability test

The operator explicitly authorized both proposed air scans together and
instructed that acquisition continue directly to the second scan without a new
authorization pause. This authorization covered exactly two MIRcat-emission
operations and did not authorize a third scan or any pump firing. PicoScope 7,
Daylight/MIRcat GUI processes and competing Python instrument controllers were
absent before direct SDK access; the LabOne service remained available. The
branch was `exploratory`, approximately 71.3 GiB of disk space was free, the
pump remained physically blocked, and no optical-adjustment step occurred
between scans.

The pair root is
`evidence/experiments/runs/authorized_consecutive_air_pair_20260903T230900_5823500Z/`.
The scans are independently preserved in:

- `mircat_sweep_20260903T230952_972499Z/`;
- `mircat_sweep_20260903T231102_474056Z/`.

Both scans used 2050 to 1650 cm^-1 at 40 cm^-1/s and 750 mA, MIRcat External
Trigger with internal 2.1 MHz / 142 ns settings, and T660-2 CHA/CHB at 2 MHz /
150 ns for the HF2LI reference and MIRcat TRIG IN respectively. Each operation
passed both required five-second armed/TEC-ready holds. PicoScope EXT was armed
before the single external process event. T660-1 A/B pump outputs and the
disconnected CHD route remained disabled; total pump events across the pair
were zero.

Scan 1 and scan 2 observed Sweep Active durations of 9.994755657 and
9.994720914 s respectively. Each retained 17,980 in-sweep HF2LI samples per
input with zero internal gaps, zero clipping or clipping-read errors, and
218,755,418 PicoScope samples per channel at 48 ns with zero overflow. Each
observed 80 of 81 requested wavelength-marker rising edges, so both axes remain
provisional. The sample/reference detector correlations were 0.9520 in HF2LI
and approximately 0.9525 to 0.9530 in Pico block means. Scan-to-scan HF2LI
correlation was 0.999707 for input 1 and 0.999872 for input 2; mean levels
increased only 0.468 and 0.602 percent respectively.

The phase-sensitive analysis is in
`adjacent_etalon_comparison/authorized_no_touch_pair.json` and its companion
plot. In the 1900 to 2000 cm^-1 region, the dominant input-1 component had a
shared frequency of 0.2735675 cycle/cm^-1, or a 3.655405 cm^-1 period. From
scan 1 to scan 2 its phase changed -5.982 degrees, fitted log amplitude changed
+0.032 percent, and independently fitted frequency changed -0.0137 percent.
The individual component amplitudes were approximately 0.10540 and 0.10544
absorbance unit. The adjacent `-log10[(S2/R2)/(S1/R1)]` residual retained a
0.008498 absorbance-unit component at that frequency, corresponding to an
estimated **91.94 percent cancellation** of the fitted dominant fringe. The
ratio-difference RMS was 0.007165 absorbance unit and its 95th-minus-5th
percentile span was 0.023018 absorbance unit in the evaluated region.

This demonstrates that the dominant input-1 etalon is substantially stable in
frequency and amplitude over an immediately consecutive untouched pair, with
small but measurable phase drift. An immediately adjacent background is
therefore preferable to a fixed template and cancels most of the fitted fringe,
but cancellation is not complete; the remaining approximately 0.0085
absorbance-unit periodic component can still matter for small spectral changes.
The air pair is not an unpumped MbCO background, does not select an MbCO band
maximum, and does not demonstrate optical Phase-Scan reconstruction or support
publication claims.

`pair_verification.json` checks both completed captures, exact MIRcat/T660
timing roles and current, disabled pump outputs, HF2LI completeness and
clipping status, full PicoScope transfer, one process event per scan, and final
shutdown. Every check passes. Final readbacks after scan 2 verify red pointer
off; MIRcat emission off, disarmed, untuned, no active scan and system error
zero; SDK deinitialized; and both T660 units idle with channels A-D disabled.
Numeric MIRcat and HF2LI settings remain retained. The two-scan authorization
is complete and does not authorize another emission or pump operation.

### Preliminary unpumped 100 cm^-1 MbCO sample/reference scan

The operator reported placing the MbCO sample and matched reference blank in
their beam paths and authorized one preliminary 100 cm^-1 MIRcat scan, with the
scan speed selected for band-location quality. The chosen operation was 2000 to
1900 cm^-1 at 40 cm^-1/s and 750 mA. Its 2.5 s nominal duration provides
approximately 4,500 HF2LI samples per detector across the window, resolving the
known few-cm^-1 etalon while limiting sample exposure. No retry or pump firing
was authorized. PicoScope 7, Daylight/MIRcat GUI processes and competing Python
instrument controllers were absent before direct SDK access.

The operation root is
`evidence/experiments/runs/authorized_preliminary_mbco_100cm_scan_20260903T232625_9651341Z/`,
with the completed acquisition in `mircat_sweep_20260903T232730_074625Z/`.
MIRcat used External Trigger mode with internal 2.1 MHz / 142 ns settings and
750 mA. T660-2 CHA/CHB supplied the 2 MHz / 150 ns HF2LI reference and MIRcat
TRIG IN signals. Both required five-second armed/TEC-ready holds passed.
PicoScope EXT was armed before the single process event; T660-1 A/B pump outputs
and the disconnected CHD route remained disabled, with zero pump events.

Observed Sweep Active duration was 2.500234971 s. Both HF2LI inputs retained
4,498 in-sweep samples with zero internal gaps, zero clipping and zero
clipping-read errors. All 21 requested wavelength-marker rising edges were
observed. Each PicoScope detector record contains 54,692,918 samples at 48 ns
with zero overflow. The HF2LI and Pico sample/reference correlations were
0.9231 and 0.9208 respectively. Full native data, the uncorrected detector CSV,
the original scan plot, SDK/T660/HF2LI/Pico readbacks and cleanup records are
preserved.

The local-maximum analysis is in `local_maximum_analysis/`. It calculates the
simultaneous sample/reference ratio and the provisional relative absorbance
`-log10[(S/R)/q95(S/R)]`. Raw results remain unchanged. A separately labeled
diagnostic view robustly fits the current scan's approximately 0.2736625
cycle/cm^-1 etalon in log-ratio space, subtracts only the slowly varying
sinusoidal component, and displays 1, 3 and 12 cm^-1 Hann-smoothed views.

Two significant broad diagnostic relative-absorbance maxima were resolved:

- **1941.1539 cm^-1**, the strongest broad candidate at approximately 0.10298
  relative absorbance unit;
- **1973.0588 cm^-1**, a retained secondary broad candidate at approximately
  0.09258 relative absorbance unit.

Within six cm^-1 of the strongest broad maximum, the 3 cm^-1-smoothed
diagnostic curve contains local maxima at approximately 1944.0887, 1941.6430
and 1938.2636 cm^-1. These resolved peaks can include residual etalon/sample
structure and are not independently assigned MbCO substates. The provisional
recommendation for the next 10 cm^-1 window is therefore a center of
**1941.1539 cm^-1**, with endpoints approximately 1946.1539 and 1936.1539
cm^-1, pending the required same-configuration adjacent background/test scan.

`preliminary_mbco_scan_verification.json` checks the completed acquisition,
exact current and timing roles, all 21 markers, disabled pump outputs, complete
HF/Pico transfers and final shutdown; every check passes. Marker count alone
does not resolve endpoint-marker identity, so the wavenumber axis and maxima
remain provisional. This single scan is not a separately normalized optical
background, an accepted band assignment, a completed optical Phase Scan or a
publication result.

Final readbacks verify red pointer off; MIRcat emission off, disarmed, untuned,
no active scan and system error zero; SDK deinitialized; and both T660 units
idle with channels A-D disabled. Numeric settings remain retained. This
one-scan authorization is complete and does not authorize another emission or
pump operation.

### Preliminary MbCO 100 cm^-1 repeat at 2 cm^-1/s

The operator next authorized repeating the same unpumped 2000 to 1900 cm^-1
MbCO sample/reference scan at 2 cm^-1/s. This authorization covered exactly one
MIRcat-emission operation, no automatic retry and no pump firing. The 50 s
duration cannot fit in PicoScope memory at the normal 48 ns interval. A
non-emitting device preflight therefore validated timebase 27 at exactly 200 ns
and 268,435,392 available samples against 262,501,459 required per channel.
The HF2LI remained the high-resolution spectral record. The slower PicoScope
record is explicitly limited to a full-duration detector-envelope/transport
witness and is not optical-pulse-shape evidence because it does not resolve the
142/150 ns pulse widths. The normal 48 ns workflow default remains unchanged.

The operation root is
`evidence/experiments/runs/authorized_preliminary_mbco_100cm_2cmps_repeat_20260903T234012_8651278Z/`,
with the completed acquisition in `mircat_sweep_20260903T234103_244456Z/`.
MIRcat retained External Trigger mode, internal 2.1 MHz / 142 ns settings and
750 mA. T660-2 CHA/CHB retained the 2 MHz / 150 ns HF2LI-reference and MIRcat
TRIG IN roles. PicoScope EXT was armed before the single process event. T660-1
A/B pump outputs and the disconnected CHD route remained disabled; pump events
were zero.

Observed Sweep Active duration was 50.045591771 s. Both HF2LI inputs retained
90,028 in-sweep samples with zero internal gaps, zero clipping and zero
clipping-read errors. All 21 requested wavelength-marker rising edges were
observed. Each PicoScope detector record contains 262,501,459 samples at 200 ns
with zero overflow. Full native detector data, original scan outputs, readbacks,
the timing/capacity preflight and cleanup records are preserved.

The preserved local-maximum method recovered broad diagnostic maxima at
**1940.9188 cm^-1** (strongest, approximately 0.10986 relative absorbance unit)
and **1972.8531 cm^-1** (approximately 0.10043 relative absorbance unit). The
3 cm^-1-smoothed diagnostic curve resolves local maxima near 1944.2822,
1941.7752, 1938.4507 and 1935.0618 cm^-1 within six cm^-1 of the strongest
broad center. These remain provisional diagnostic features, not assigned MbCO
substates.

`mbco_40_vs_2cmps_local_maxima.png` and its JSON companion compare the two scan
speeds. The strongest broad center changed from 1941.1539 to 1940.9188 cm^-1,
a -0.2351 cm^-1 difference. The higher-wavenumber maximum changed from
1973.0588 to 1972.8531 cm^-1, a -0.2056 cm^-1 difference. Both scans therefore
recover the same two broad features, and the provisional follow-up center is
retained as **1941.0 cm^-1**. The intended 10 cm^-1 window comfortably contains
the strongest center from either scan.

`preliminary_mbco_2cmps_scan_verification.json` checks the requested 2 cm^-1/s
profile, current and timing roles, all markers, disabled pump outputs, complete
HF/Pico transfers, one process event, zero pump events and final shutdown; every
check passes. Final readbacks verify the red pointer off; MIRcat emission off,
disarmed, untuned, no active scan and system error zero; SDK deinitialized; and
both T660 units idle with channels A-D disabled. Numeric settings remain
retained. The single-scan authorization is complete and does not authorize
another emission or pump operation. The endpoint-marker identity remains
unresolved, so axes, maxima and scan-speed differences remain provisional and
not publication results.

After adding the explicit custom PicoScope timing contract and its regression,
the complete offline software suite passed **212 tests, 15 skipped, and 24
subtests**. `git diff --check` reported no whitespace errors apart from existing
informational Windows line-ending warnings.

### MbCO Phase-Scan pump-off background/test qualification

The operator authorized the next scans after confirming that the MbCO sample
and reference blank remained in their beam paths. This authorization was
interpreted as one compatible Phase-Scan background followed by one pump-OFF
test, with the pump physically blocked, T660-1 pump outputs A/B disabled and
T660-1 CHD disconnected. The operator subsequently authorized as many repeats
as necessary. That standing repeat authorization applied only to compatible
pump-off qualification attempts and terminated as soon as both records passed;
it did not authorize pump firing or the 1,601-event phase-delay series.

The fixed acquisition profile was 1946 to 1936 cm^-1 at a requested 10,000
cm^-1/s, 5 us reconstruction intervals, 2 ms pre-pump and 5 ms post-pump timing,
250 ms cadence, one repetition, MIRcat internal 2.1 MHz / 142 ns / 750 mA,
T660-2 CHA/CHB at 2 MHz / 150 ns, HF2LI at the installed supported
28,782.8947 Sa/s with 50 us time constants, and PicoScope at 16 ns/sample.
The derived pumped plan of 1,602 total scans and 1,601 pump events was recorded
but not executed. Both pump-off operations used zero pump events.

The original pair is retained under
`evidence/experiments/runs/authorized_mbco_phase_qualification_pair_20260904T000245_9725934Z/`.
Both optical scans completed with measured three-marker axes, positive sample
and reference signals, zero HF2LI clipping, zero PicoScope overflow and verified
safe shutdown. They were nevertheless rejected for pulse-coverage purposes
because the nominally 1 ms request produced approximately 2.284 to 2.293 ms of
observed Sweep Active while the PicoScope record extended only to approximately
1.300 ms after trigger. The incomplete records, diagnostic analysis and plot
remain preserved and are not promoted to acceptable evidence.

The adapter was then corrected to retain at least 5 ms of anticipated Sweep
Active plus the configured pre/post-trigger margins. It now requires MIRcat TEC
ready continuously for five seconds both after arm and after manual-tune
cancellation; re-verifies external-trigger state at the relevant transitions;
requires the red pointer off; verifies emission before the process event; and
records HF2LI input status/clipping both before emission and after Sweep Active.
Pulse opportunities now retain the T660-2 rate readback as the authoritative
period, fit only the circular phase from the primary CHB optical witness, and
record extra or unmatched threshold crossings without allowing them to insert
opportunities. The complete offline suite passed **213 tests, 15 skipped, and
24 subtests** before the retry.

The successful retry is preserved in
`retry_01_20260904T001308_6621280Z/` below the original pair root. The
background observed 2.297371429 ms of Sweep Active and passed 457 of 460
5 us intervals at 100 percent coverage and three isolated intervals at the
configured 90 percent boundary. It contained 4,594 fixed-grid opportunities,
of which 4,591 were observed by at least one optical witness; three were absent
from both, for a 0.06530 percent missing fraction and a maximum consecutive
missing count of one. The immediately following pump-OFF test observed
2.288685714 ms of Sweep Active and covered all 4,578 opportunities, with zero
missing and zero unclassified opportunities. Every 5 us interval in both
records therefore met the configured 90 percent criterion, the whole-scan
missing fractions were below the 5 percent limit, and the consecutive-missing
limit of two was not reached.

The retained detector-path diagnostics show 17 CHA-only and 578 CHB-only
fixed-grid detections in the background, and 8 CHA-only and 528 CHB-only
detections in the test, plus respectively 65/3 and 59/2 unmatched CHA/CHB
threshold edges ignored for timing. These single-path discrepancies are not
hidden and should remain a sensitivity diagnostic. They do not redefine the
2 MHz grid or count as an opportunity absent from both optical witnesses.
Both HF2LI channels remained positive, all three wavenumber markers were
observed in each scan, HF2LI clip flags were zero before and after each sweep,
and both PicoScope overflow masks were zero.

`phase_qualification_retry_01_pass_v2.png` plots the measured sample/reference
records, the pump-off residual and interval coverage. The largest diagnostic
pump-off residual local maxima within this narrow window were 1944.8623,
1937.0101 and 1939.8384 cm^-1, at approximately 0.013795, 0.003917 and
0.002626 absorbance unit respectively. They are baseline/repeatability
diagnostics and are not pump-induced features. The original plot in the retry
directory remains preserved but is superseded because its interval-criterion
line was mislabeled 95 percent; the v2 plot correctly shows the configured
90 percent criterion.

The retry result is `QUALIFICATION_PASSED`. Final readbacks after the test
verify red pointer off; MIRcat emission off, disarmed, untuned, no active scan
and system error zero; and both T660 units idle with channels A-D disabled.
Numeric settings remain retained. This establishes exploratory pump-off
acquisition readiness for the selected window. It does not validate a pumped
MbCO response, remove the endpoint-marker or single-path sensitivity caveats,
authorize pump firing, or make any output publication eligible.

### Authorized MbCO phase-delay nominal pass and offline reconstruction

After the operator reported that the pump block was removed, all shutters were
open and the OPO was set to 540 nm, the operator explicitly authorized the
pumped phase-delay series and any necessary retries. The retained acquisition
root is
`evidence/experiments/runs/authorized_mbco_phase_reconstruction_20260904T002152_3132654Z/`.
Several failed or interrupted development attempts remain preserved there. They
include the operator-stopped per-record retuning path, an invalid MIRcat
multi-repetition path, and a consecutive-DDG path that could not maintain
acceptable detector-witness coverage. None is hidden or promoted.

The complete nominal single-rearm pass is retained below
`retry_06_buffered_single_rearm_ddg_20260904T021526_1936864Z/`, with its actual
run in `Phase Scan/2026-09-04/20260904T021539_510021Z_run/`. The MIRcat was tuned
once and left armed through the series, but `StartSweepScan(1)` was rearmed
before each DDG event. T660-2 CHB was enabled only across the rearm/sweep and
verified off between records. All 1,602 nominal records were acquired: one
unpumped baseline and 1,601 pumped phase records spanning -3,000 to +5,000 us
in exact 5 us increments. Every nominal NPZ is readable, every spectrum is
marked optically valid, the sample/reference and coordinate arrays are finite,
and every pumped spectrum retains a finite observed Nd:YAG electrical-sync
reference time.

The original run remains correctly labeled `ABORTED` because the operator
stopped a nonproductive targeted-retry pass before the runner created processed
outputs. The 1,602-record nominal acquisition itself is complete. The 315
retained retry records add no accepted completion claim. PicoScope coverage
reports marked most later phase records for reacquisition, but the witness was
configured at 5 V (sample) and 10 V (reference) in 8-bit mode while observed
signals occupied only approximately 2.7 and 4.4 percent of full scale. The
apparent missing-opportunity count is therefore not accepted as proof of
missing optical pulses. The new 0.5 V / 1 V recipe was prepared for a bounded
qualification, but the operator paused it before any record or pump event and
its zero-record safe cleanup is retained separately.

Raw storage was also diagnosed. The fixed 14.418 GB preflight estimate assumed
9 MB per record, whereas the 1,602 nominal records consumed 21.889 GB and the
315 retries another 4.300 GB. A representative 17.124 MB record contained
15.673 MB of uncompressed HF2LI polling chunks and 1.315 MB of PicoScope data.
The HF2LI stream had been subscribed before the blocking controller-rearm call,
so controller latency rather than the approximately 2.3 ms optical sweep
dominated each record. The consecutive path now starts HF2LI acquisition only
after the MIRcat reports that it is waiting for the DDG process trigger and
records that window contract explicitly. This change is offline-tested and has
not been used to alter the retained acquisition.

An immutable derived package was generated without new laser emission or pump
firing at
`evidence/experiments/runs/authorized_mbco_phase_reconstruction_20260904T002152_3132654Z/offline_nominal_reconstruction_20260904T031955_4331576Z/`.
It selects only nominal `attempt_00` spectra and preserves all 315 retries as
excluded source evidence. Native HF2LI tick quantization occasionally assigns
adjacent 5 us phase commands the same measured time coordinate. Reconstruction
now averages repeated observations at one identical measured coordinate rather
than rejecting that legitimate quantization case; the focused data tests pass.

The completed nominal reconstruction contains 33 measured wavenumber points
from 1936.3030 to 1945.8512 cm^-1 and 1,401 time points from -2 to +5 ms. It has
40,437 finite cells out of 46,233 (87.4635 percent); unsupported cells remain
blank with no extrapolation. Finite absorbance ranges from approximately
-0.023979 to +0.020051. Only one repetition exists, so no standard error can be
estimated. Time zero remains the observed Nd:YAG electrical sync rather than a
measured optical arrival at the sample, and the low-resolution PicoScope pulse
coverage is not qualified. The package remains explicitly exploratory and not
publication eligible.

`mbco_phase_delay_reconstruction_3d_requested_axes.png` is the requested 3D
render: X is wavenumber (conventional descending IR direction), Y is absorbance,
and Z is electrical-sync-relative time with positive time receding into the
page. It displays the unsmoothed supported surface and marks the top separated
mathematical local maxima. The reconstructed NPZ, long-form CSV, source-record
index, local-maxima tables, heatmap, analysis summary, rendering metadata and
derivation manifest are retained alongside it.

The operator subsequently requested a simplified title, a 90-degree clockwise
camera rotation, a fixed-band trace near 1941 cm^-1, removal of the footer and a
tighter crop. The corrected final render is
`mbco_phase_delay_reconstruction_3d_corrected_v2.png`. Its trace uses the nearest
measured reconstruction coordinate, 1941.089 cm^-1, and follows unsmoothed
absorbance versus electrical-sync-relative time. A white underlay and forced
foreground ordering keep the black trace visible across the colored surface.
The earlier renders and orientation trials remain preserved as superseded
diagnostics; `corrected_3d_plot_metadata_v2.json` records the final view and
trace selection.

The reconstruction was also rendered in the coarse X-Y-Z grid style supplied
by the operator so that the transient absorption excursion remains visible.
`mbco_phase_delay_reconstruction_3d_grid.png` uses a black-edged surface and an
eight-level floor projection, with wavenumber on X, absorbance on the vertical
Y axis, and time receding on Z. For display only, the unchanged full
reconstruction is aggregated into fourteen exact 0.5 ms time rows and seventeen
neighboring spectral groups using finite-cell means; no model fit or additional
reconstruction is applied. The overlaid primary-band trace is evaluated at the
nearest measured coordinate, 1941.089 cm^-1. The plotted display values and
provenance are retained in
`mbco_phase_delay_reconstruction_display_grid.csv` and
`grid_3d_plot_metadata.json`, while `reconstruction_nominal.npz` remains the
authoritative full-resolution result.

The operator then requested stronger visual separation of the absorbance rise
at the primary band and the time-axis label `Time relative to pump pulse at t=0
(ms)`. The final emphasized render is
`mbco_phase_delay_reconstruction_3d_grid_peak_emphasis_v4.png`. It keeps the
absolute-absorbance surface unchanged, overlays the 1941.089 cm^-1 band in
green against its dashed pre-pump mean, and adds a compact inset showing the
display-binned change from that mean. The maximum displayed rise is
approximately +1.4865e-3 absorbance units. The trace values and calculation are
retained in `mbco_phase_delay_primary_trace_peak_emphasis_v4.csv` and
`grid_3d_plot_metadata_peak_emphasis_v4.json`. Earlier peak-emphasis layout
drafts remain preserved as superseded visual diagnostics.
