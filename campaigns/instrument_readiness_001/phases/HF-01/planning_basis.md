# HF-01 PicoScope-AWG parameter-characterization design

> **Prospective downstream amendment (2026-08-26):** HF-01 remains PASS. Its shared
> sweep/HRP numerical choice is historically valid provisional electrical evidence.
> Planned `hf01_1_experiment_specific_optimization.md` performs future selection;
> HF-01 evidence, decisions, and configuration identities are unchanged.

## Purpose and boundary

HF-01 uses the registered PicoScope 5244D arbitrary-waveform/function generator
as a monitored electrical stimulus to characterize the HF2LI parameter-response
relationship before selecting the sweep, HRP-C-CO, and MbCO acquisition
configurations. This is a non-optical calibration: all lasers remain inhibited
and shuttered. It qualifies the HF2LI electronics, demodulator filters,
readout, configuration persistence, and the temporary electrical test assembly.
It does not qualify detector response, optical response, chemical kinetics, or
biological acquisition.

The design validates the installed HF2LI against the manufacturer response
model at three deliberately separated electrical instrument-model validation
points. These are not proposed experiment settings and are not assigned to
sweep, HRP-C-CO, or MbCO. Only after their measurements validate the response
model does software evaluate every supported order, time constant, range, and
output-rate combination against each experiment's frozen requirements.
Physical testing is restricted to the three model-validation points, the
experiment configurations subsequently selected by that analysis, and at most
one decision-boundary challenger per experiment case when uncertainty does not
identify a unique selection. No HF2LI parameter grid is run on Mylar.

## Authorities and prerequisites

- HF2LI device `dev18500` and PicoScope 5244D serial `10261`.
- `references/manuals/HF2LI/Zurich Insturments HF2LI User Manual.pdf`, especially the
  discrete-time cascaded-filter, noise-equivalent-bandwidth, settling-time, and
  sample-readout-rate sections.
- `references/manuals/PicoScope/PicoScope 5000D Series Data Sheet.pdf` for the monitored AWG
  capability and applicable generator bounds.
- Completed S0 safe-idle evidence, T2-01 external-reference route evidence, and
  the applicable MS-01/MS-02 PicoScope timing corrections.
- CH-00 experiment envelopes. Before acquisition, HF-01 must identify the
  retained claim/waveform family, fastest required feature, scan or recovery
  interval, channel count, and maximum record duration for sweep, HRP-C-CO, and
  MbCO. A separately guessed precision target is not required: the selection
  minimizes measured/predicted total error while preserving the required
  feature. Unknown claim boundaries remain `USER_INPUT_REQUIRED`; they are not
  replaced by literature kinetics or zero uncertainty.

## Temporary electrical topology

Preserve `CLOCK-SPLITTER-01` in its normal installed 10 MHz distribution:
T660-2 CLOCK OUT to the splitter input, with the existing branches to the
T660-1 CLOCK input and HF2LI CLOCK input. HF-01 uses the HF2LI external clock
and must not repurpose, bypass, or reterminate this splitter. Record the HF2LI
external-clock selection and lock/readback before and after acquisition.

Use a separate campaign-identified passive 50 ohm, DC-coupled BNC male-to-two-
female tee (`HF01-STIMULUS-TEE-01`) for the stimulus path. Attach its male port
to the PicoScope AWG female bulkhead output. Connect its two female ports using
the two retained identical RG-58 50 ohm BNC male-to-male cables: one cable to
one HF2LI signal input at a time and the other to high-impedance PicoScope
channel A. Support both cables so their weight does not strain the PicoScope
bulkhead connector. Perform one destination/cable exchange at the common-path
screen to measure or bound arm/cable gain and phase asymmetry; the PicoScope
observation is not assumed identical to the voltage at the HF2LI connector.

The normal T660-2 channel-A reference remains connected directly to HF2LI DIO0.
During HF-01 only, disconnect T660-2 channel B from MIRcat and configure it as a
read-back-verified copy of channel A routed directly to high-impedance PicoScope
channel B. Keep T660-2 channel C directly connected to HF2LI DIO1. Disconnect
T660-2 channel D from T660-1 and configure it as a read-back-verified copy of
the channel-C acquisition marker routed to the PicoScope external trigger.
Thus the HF2LI and PicoScope share T660 timing without a second splitter and no
HF-01 timing output reaches MIRcat, T660-1, or a laser controller.

Before the AWG response acquisitions, use one bounded non-emitting PicoScope
check to measure A-versus-B reference-copy timing and C-versus-D marker-copy
timing with the exact retained cables and settings. Import the applicable
MS-01/MS-02/T2-01 corrections and retain the observed copy offsets and
uncertainty. Use the copy channels throughout the response acquisition without
changing the installed 10 MHz clock distribution.

The HF2LI signal input and PicoScope monitor use high impedance unless a
separately reviewed source/termination calculation requires otherwise. The
actual connected amplitude, offset, carrier frequency, transition time, and
loading are measured; the programmed AWG value is never the sole stimulus
authority. No output is enabled until voltage limits, grounds, coupling,
termination, tee/cable identities, HF2LI clock lock, and absence of another
source on the selected HF2LI input have been verified. Inputs 1 and 2 are
tested sequentially with the same stimulus assembly. Each physical connection
or exchange is an operator-led action. Restoration reconnects channel B to
MIRcat and channel D to T660-1 only after all T660 outputs are disabled and
read back safe; `CLOCK-SPLITTER-01` remains in its normal wiring throughout.

HF-01 preflight must prove that one owner can operate PicoScope capture and its
AWG concurrently and can read back or preserve every generator setting. A
focused repository utility is preferred; the PicoScope GUI plus native exports
is acceptable when the installed SDK path cannot control the generator. This
choice changes the producer/software provenance, not the measurement content.
The generator is always disabled before connection, channel exchange,
restoration, software ownership transfer, or an abnormal stop.

## Stimuli

1. **Zero/steady carrier:** AWG output disabled or zero for the connected-path
   baseline, followed by a stable carrier at the retained 2 MHz reference.
2. **Carrier-amplitude step:** gate or change the monitored 2 MHz carrier
   between two safe levels while T660 supplies the independent continuous
   external reference. Use both rising and falling transitions. This measures
   gain, delay, monotonicity, and settling without an optical detector.
3. **Offset carrier:** drive a monitored sine at `2 MHz + f_offset`. After
   demodulation against the T660 reference, the HF2LI baseband is at
   `f_offset`. This measures amplitude and phase transfer without requiring a
   long amplitude-modulated AWG buffer. Offset sign is reversed at the cutoff
   neighborhood to expose sideband or sign asymmetry.
4. **Optional boundary waveform:** replay a monitored ramp, finite burst, or
   exponential-like envelope only when the fitted transfer model predicts an
   experiment metric within its uncertainty guard band, or when step/frequency
   residuals reject the cascaded-filter model. It is not a mandatory extra
   acquisition used merely for illustration.

Every enabled HF2LI signal-input stimulus is therefore a 2 MHz carrier or a
carrier at `2 MHz +/- f_offset`; HF-01 does not apply a standalone 10 Hz analog
signal to an HF2LI signal input. The offset is a demodulated-baseband test
frequency chosen from the filter cutoff and retained transient bandwidth, not
from the Nd:YAG/OPO firing cadence. An offset may equal approximately 10 Hz
only if the normalized cutoff rule independently selects it.

The retained 10 Hz Nd:YAG/OPO cadence is a digital event/recording-timing
quantity, not an HF2LI analog-carrier frequency. With all lasers inhibited,
HF-01 performs only one bounded T660-marker/PicoScope/HF2LI-DIO timestamp check
at the retained 10 Hz cadence. This check qualifies marker capture for the
selected configurations; it does not add a filter-response point, model anchor,
or parameter sweep. HF-02 later tests stream alignment and duration, and FE-01
later reconciles commanded versus independently observed optical pump events.

## Minimal model-validation and selection design

### A. Readback and selection of three instrument-model validation points

Read back the installed HF2LI-supported filter orders, time constants, rates,
input modes, and ranges. Before acquiring response data, select exactly three
electrical instrument-model validation points spanning the required operating
envelope:

- a fast/high-bandwidth anchor using a short retained time constant and low or
  moderate order;
- an intermediate anchor, normally including the repository's provisional
  order-four setting when it lies inside the valid envelope; and
- a slow/low-noise anchor using a long retained time constant and higher order.

Choose these points before response data are viewed and record why they span
the required time-constant, order, bandwidth, and settling envelope. They are
sparse checks of the manufacturer model, not candidate experiment presets.
No sweep, HRP-C-CO, or MbCO setting is selected at this stage, and a validation
point receives no experiment label. Add one targeted validation point only if
a predeclared model-residual test fails and identifies a region not bounded by
the original three; otherwise additional filter settings are prohibited.

### B. Common-path and range screen

On Signal Input 1, use the intermediate anchor to acquire:

- connected zero/baseline;
- low and high safe carrier amplitudes spanning the provisional electrical
  interval;
- the proposed input range plus its immediately smaller and larger supported
  ranges where safe; and
- three independent windows at each retained endpoint. Add one midpoint only
  if endpoint residual, overload recovery, or range-transition behavior is
  inconsistent with the manufacturer model.

Select the smallest range that does not clip or overload at the high endpoint
including the uncertainty margin and whose low-end noise/SNR meets the frozen
criterion. A smaller range that clips and a larger range that materially loses
precision provide the bounded selection evidence. If the two neighboring
ranges lead to the same decision within uncertainty, retain the larger safety
margin and stop.

### C. Three-anchor filter-model validation

For each of the three anchors, acquire on Signal Input 1:

- three rising and three falling monitored carrier steps;
- connected-zero noise windows of the same analysis duration; and
- offset-carrier points at approximately `0.1`, `1`, and `5` times the anchor's
  predicted cutoff, clipped to the generator/HF2LI valid range.

The three normalized frequencies test passband gain, cutoff, and out-of-band
behavior against a manufacturer model whose form is already specified; they do
not fit an unconstrained empirical filter. Add one reversed-sign offset at the
intermediate anchor cutoff to expose sideband/sign asymmetry. Add a frequency
point only when the observed cutoff is not bracketed or a predeclared residual
test fails. A single acquisition may contain multiple settled offset segments,
but every segment retains its own stimulus and settings readback.

Estimate complex transfer, cutoff, effective delay/group delay, rise/fall
settling, overshoot or nonmonotonicity, effective noise bandwidth/noise, gain,
and model residuals. Compare measured results with manufacturer predictions;
do not replace measurement uncertainty with the prediction.

### D. Computational evaluation and selection

After the three-point instrument model passes, use it to evaluate every
supported order, time constant, input range, and output rate without applying
those combinations to hardware. This full computational evaluation, rather
than the identities or numerical values of the three validation points, selects
the experiment configurations. For each experiment case, propagate its
representative waveform family through the filter and intended analysis.
Calculate amplitude/shape bias, peak shift or broadening, lifetime/recovery
bias, settling, noise-equivalent bandwidth, expected variance, samples per
feature, throughput, and record size.

Rank configurations by estimated total measurement error,
`bias^2 + variance`, subject to preservation of the required feature, no
clipping, valid sampling, and sustainable data limits. Reject dominated
settings analytically. Select one sweep, one HRP-C-CO, and one MbCO setting.
When two leading settings have overlapping total-error intervals or the winner
lies inside an acceptance guard band, identify exactly one nearest boundary
challenger for that case. Otherwise no challenger is measured.

### E. Readout-rate selection

Acquire the anchor validation initially at one supported reference rate that
is at least eight times the measured filter bandwidth where the device and aggregate
throughput permit, consistent with the HF2LI manual. Screen lower rates by
timestamp-aware offline decimation of that native record. For each selected
experiment configuration, reacquire only:

- the selected supported output rate; and
- the immediately lower supported rate.

The selected rate passes only if it meets the frozen reconstruction/timing
criterion and the lower rate fails or is rejected by the predeclared safety
margin. If the lower rate also passes with margin, it becomes the selected rate
and the comparison repeats downward. Test the immediately higher rate only if
the selected-rate record fails, lies inside the uncertainty guard band, or
cannot distinguish filtering from readout decimation. HF-02, not HF-01,
qualifies loss-free maximum-duration operation at the selected rates.

### F. Selected-setting confirmation and second-channel equivalence

Confirm each selected sweep, HRP-C-CO, and MbCO setting on Signal Input 1 with
zero/noise windows, three rising/falling steps, and the same three normalized
offset frequencies. If a selected setting is identical to an anchor, link the
anchor evidence rather than reacquiring it. Test the single boundary challenger
only when invoked by Section D.

Exchange the same monitored stimulus assembly once. On Signal Input 2, repeat
the range endpoints and selected-setting confirmations only; do not repeat the
three-anchor search or computational enumeration. Retain before/after source
checks. If inter-channel complex gain, cutoff, settling, noise, clipping, or
residual differences exceed their equivalence limits, repeat only the affected
selected setting or invoked challenger. A full second-channel filter matrix is
outside HF-01 unless the manufacturer model itself is rejected on that channel
and a prospective amendment is approved.

### G. Repetition, ordering, and stopping

Each reported condition contains three independent acquisition windows or
transitions. Randomize or counterbalance candidate order within safe operating
blocks; repeat the initial common check at block end to detect drift. Preserve
all failed, clipped, interrupted, superseded, and excluded records. Do not add
repeats after viewing results unless a predeclared precision, residual, drift,
or data-integrity rule invokes them.

The three windows may be contained in one native segmented acquisition when
the segment boundaries and independent stimulus transitions are retained. A
window is a statistical replicate; it does not require an unnecessary physical
rewire or separate software session.

Stop acquiring when the three-anchor model is accepted, all three computational
selections are unique after uncertainty or their one allowed challengers have
resolved the decision, both channels pass the selected-setting equivalence
rule, and reload/revisit checks pass. A selected setting does not require a
measured rejected neighbor when its model-predicted selection is unambiguous.
If two candidates remain equivalent after the one challenger, retain the one
with the larger temporal/clipping margin unless the lower data rate materially
improves the frozen long-record resource limit.

## Selection outputs

HF-01 produces separate configuration IDs for sweep, HRP-C-CO, and MbCO. Each
contains the complete HF2LI node snapshot and its applicable signal, temporal,
spectral-sweep, noise, duration, and throughput envelope. Identical numeric
settings may be represented by an explicit alias relationship, but one
biological ID is never silently substituted for the other.

Selection uses the validated response model and measured noise:

- **Sweep:** smallest noise bandwidth that meets peak-shift, broadening,
  direction-bias, marker/dwell, and settling limits at the retained scan speed.
- **HRP-C-CO:** smallest noise bandwidth that preserves the fastest retained
  HRP feature while meeting the longest-record drift, precision, and recovery
  envelope.
- **MbCO:** smallest noise bandwidth that preserves the fastest claimed MbCO
  feature within attenuation, delay, lifetime-bias, and sampling limits.

Configuration uncertainty includes stimulus measurement, repeatability,
channel equivalence, fit/model residual, HF2LI setting quantization/readback,
PicoScope timebase/voltage terms where applicable, loading/placement, and drift.

## Downstream reuse and non-duplication

- **HF-02** tests timestamp integrity, buffering, loss, and maximum duration
  only at the selected configuration/rate envelopes; it does not repeat filter
  response mapping.
- **DET-01/DET-02** use the selected ranges/settings and establish installed
  detector noise and illuminated transfer; the AWG baseline is not detector
  noise evidence.
- **DET-03** measures the installed detector/amplifier/cable response using the
  fastest required acquisition path, then composes it with the HF-01 complex
  transfer for HRP and MbCO. It repeats a slower configuration only if the
  linear time-invariant composition check fails or is marginal.
- **AR-01** validates the selected settings in the installed optical workflow.
  It retains the slower-reference sweep needed to measure scan distortion, but
  it does not repeat the electrical filter grid. A biological bracket is added
  only after HF-01 prediction disagreement or an acceptance-boundary result.
- **IR-01** measures the complete optical instrument response under the actual
  retained experiment configurations and imports, rather than redetermines,
  the HF-01 electrical transfer.

## Mandatory HF-01 evidence

- Reviewed temporary wiring diagram showing the unchanged
  `CLOCK-SPLITTER-01` clock distribution and separate
  `HF01-STIMULUS-TEE-01` path; source/load calculation; stable tee/cable IDs;
  reference-copy and marker-copy offset check; photographs; HF2LI external-
  clock selection/lock evidence; safe voltage envelope; and initial/final safe
  states.
- Native PicoScope stimulus/reference captures synchronized or linked to native
  HF2LI Sample/Reference data, settings/readbacks, timestamps, and segment IDs.
- Three-anchor declaration and model-validation results; computational table
  for every supported setting with total-error terms and disposition; and any
  single boundary-challenger invocation.
- Complex-transfer, step/settling, noise, range/clipping, rate/decimation,
  selected-setting channel-equivalence, drift/revisit, and uncertainty results
  with residuals.
- Complete accepted/rejected ledger, model-failure/challenger invocations, and
  evidence that no unrecorded parameter grid or post-result expansion occurred.
- Three restorable experiment-specific configuration IDs, reload equivalence,
  an optional explicit alias/equivalence record, revalidation triggers, and
  downstream validity links.
