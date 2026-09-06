# Prospective slow-scan and time-resolved acquisition procedures

Status: **REQUIREMENTS-LEVEL; NOT EXECUTABLE; NO BIOLOGICAL DATA ACQUIRED**

These procedures apply independently to HRP and MbCO at room temperature and 77 K.
Numeric
recipes remain locked until promoted calibration/characterization bundles exist.
All modes preserve native pulse-level and stream-level Sample, Reference, complete
DIO, MIRcat readback, observed pump, temperature, configuration, exclusion, and
restoration evidence under the measurement-campaign data contract.

The HF2LI is the primary normalized Sample/Reference recorder. The PicoScope is an
independent waveform, trigger, detector-response, saturation, branch-transfer, and IRF
diagnostic; its records do not silently replace the primary spectral streams. Normal
simultaneous dual-detector wiring and temporary sample-detector/pump-detector timing
wiring have separate configuration IDs and are bridged only by calibrated quantities.
The [default detector wiring](../../instrument/default_wiring_state.md) is one
female-to-female BNC adapter -> male-to-two-female BNC tee per detector signal:
sample feeds HF2LI Signal 1 In (+) and PicoScope CHA; reference feeds HF2LI
Signal 2 In (+) and PicoScope CHB. Both receivers remain connected in normal
operation. Temporary timing/IRF work records changed branch connections/loading
and restores both default split paths after measurement.
T660-1 supplies the probe/reference pulse train: channel A feeds HF2LI DIO0,
channel B feeds MIRcat TRIG IN, and channel C feeds T660-2 TRIG IN. T660-2
uses its train/frame engine for the event schedule: channel A drives Surelite
FIRE, B drives Q-switch, and C drives MIRcat DB9 pin 4 Process Trigger. Both
channel-D outputs are disabled and unwired; HF2LI DIO1 is unwired. MIRcat DB9
pin 2 Sweep Active feeds HF2LI DIO21 and PicoScope EXT through the qualified
high-impedance branch; pin 1 direction feeds DIO20 and pin 3 wavelength markers
feed DIO22. Connector pin numbers and captured DIO bit indices are distinct.
T660-2 CLOCK OUT supplies the 10 MHz clock distribution to T660-1 CLOCK IN and
HF2LI CLOCK IN. This frequency-reference distribution is separate from the
T660-1 probe pulse train.

A finite run preloads the complete bounded T660-2 frame table while outputs
are disabled. Per-frame channel OFF states suppress unrequested outputs,
including pump outputs in unpumped baselines; terminal padding has all outputs
OFF. Train count zero disables additional pulses, not the first pulse of an
enabled channel. Train count and spacing are shared by enabled channels within
each frame. The frame predivider, frame repetition, train count/spacing,
channel enables/delays/widths/polarities, terminal padding, and physical frame
count are recorded and checked against readback before arming. Acquisition
is ready before the event sequence starts; software polling does not schedule
pump/probe/scan edges. Frames and train counts schedule electrical commands;
independent optical observation establishes emitted pump counts and sample time
zero. Each experiment freezes its own cadence, recovery interval, and data budget;
the Phase Scan 0.3 s frame period is not a default for other experiment types.

## Mandatory initial slow scans

Before time-resolved work, acquire and accept a condition-specific slow scan for each
of room-temperature HRP–CO, room-temperature MbCO, 77 K HRP–CO, and 77 K MbCO.
Each determines actual centers, widths, integrated areas, baselines, interference,
direction dependence, sensitivity, and local windows. Literature values are search
anchors, not final setpoints. A new preparation, cell reload, temperature/thermal
cycle, matrix, material time gap or state change, optical/acquisition configuration, or
failed reference checkpoint triggers the applicable scan again.

## Fixed-wavelength kinetics

For prospectively declared primary, secondary, and off-band wavelengths: settle and
accept a pre-pump baseline; acquire matched negative-delay or pump-blocked controls;
observe rather than infer the pump event; record through the entire required
recovery; enforce cumulative exposure and recovery before another accepted event;
and randomize or balance wavelength and delay order. Abort or exclude without
deleting data when state, recovery, exposure, temperature, saturation, timing, or
stream-quality gates fail.

## Phase-shifted rapid-scan stroboscopy

Repeated recoverable events scan the declared window while pump time shifts relative
to scan start over a frozen phase schedule. Both directions, pump-blocked, and no-
sample/artifact controls are mandatory. Every sample retains corrected instantaneous
wavenumber and delay relative to the observed pump. Measure scan-to-scan power and
wavelength repeatability. Freeze the two-dimensional reconstruction, weighting, and
interpolation support rule before opening biological results; publish the actual
`(wavenumber, delay)` coverage matrix and label unidentifiable regions. Unsupported
interpolation is rejected. Demonstrate reconstruction on a nonbiological surrogate
first. A single rapid scan is never an instantaneous spectrum.

## Single-scan phase-delay reconstruction

When an equivalent initial state can be demonstrated, acquire one rapid scan per
accepted pump event at a prospectively varied pump phase. Retain the actual scan
trajectory, direction, start/turnaround history, observed pump, complete native
coverage, and state/reset evidence. This architecture is distinct from repeated
rapid-scan stroboscopy and is rejected when recovery, fresh-position, or equivalent-
state criteria fail. Its reconstruction must pass the same nonbiological bias,
missing-data, noise, edge, filter-memory, and interpolation tests.

The finite implementation preloads baseline, pumped, and padding frames on
T660-2; each nominal phase is acquired once in each planned repetition. The
LabOne detector history is triggered by observed Sweep Active, with a separate
synchronized pump-event record. Preserve one consolidated native acquisition,
complete event identities, readbacks, and the actual time/wavenumber coverage.
Reconstruction uses the calibrated scan trajectory and observed pump and scan
timestamps. Requested delays and electrical pump sync are not optical time zero.

Use qualified paired PicoScope detector diagnostics when establishing pulse
fidelity, thresholds, and omission envelopes. Expected optical opportunities
come from read-back T660-1 probe rate; a pulse absent in both detectors differs
from a one-channel path discrepancy. Diagnostics must resolve pulses with the
qualified sampling, saturation, noise, record, and trigger envelope.

The production method uses single-pass reconstruction and preserves missing
regions and deficient-run status. It does not automatically repeat affected
phase delays, combine attempts to fill gaps, or perform programmatic etalon
removal. A deliberately authorized repeat is a distinct native acquisition;
planned independent repetitions retain separate identities and uncertainty.
Unexpected frame, scan, pump-event, or recorder counts abort the finite block
and preserve partial evidence. Accepted coverage and signal quality remain
prerequisites for any scientific claim.

## Single-pump rapid/logarithmic scan-burst reconstruction

For slow cryogenic recovery where repeated pumping cannot preserve state, admit one
independently observed pump event followed by a frozen sequence of rapid scans or
logarithmically scheduled scan bursts. Preserve the full command/event/scan schedule,
actual `(wavenumber,time)` coverage, thermal and probe-duty history, missing bursts,
and observation-limit accounting. Unsupported gaps are labeled; interpolation cannot
create a measured region. Additional pump events require a new qualified state,
position, or preparation and remain separate records.

## Wavelength-by-wavelength stroboscopic reconstruction

At each wavelength, use the frozen delay grid and repeat accepted events at every
delay. Change wavelength only after recovery and state checks. Acquire matched
pump-off, negative-delay, and off-band controls. Normalize through the qualified
sample/reference covariance model, then combine independent traces into
`DeltaA(wavenumber,time)`. Retain wavelength-dependent probe power, linewidth,
timing, detector response, uncertainty, and provenance. Different configurations
cannot be pooled without an explicit bridge study.

Nanosecond and microsecond wavelength-by-wavelength acquisition are separate
configurations even if the wavelength list is shared. Each requires its own optical
time origin, integration aperture, detector/branch response, HF2LI filter and stream
envelope, jitter/IRF, SNR, dose/recovery schedule, and nonbiological reconstruction
validation.

## Experiment-specific boundaries

HRP targets approximately second-scale recovery and only faster features supported
by IRF and SNR. Use the minimum duty and rate meeting resolution/precision. Low-rate
and high-rate probe architectures have separate IDs and a bridge if both are used;
neither inherits a final value from the pump's rate limit.

MbCO begins only after HRP closeout, verified restoration, explicit handoff, QB-01M,
and MbCO-specific promotion. The cryogenic timescale is a hypothesis until measured.
Pulse-level resolution uses the direct detector/PicoScope path; HF2LI contributes
only inside its qualified envelope. Every mode remains in this design if later
evidence rejects it; the result is recorded as a limitation, not deletion.

All five reconstruction methods—nanosecond and microsecond wavelength-by-wavelength,
repeated rapid scan, single-scan phase delay, and single-pump rapid/log scan burst—are
validated separately against native coverage and a known nonbiological target before a
matching biological claim. Missing scans/samples, drift, heteroscedastic noise, phase
error, direction, edge effects, filter memory, interpolation, and identifiable regions
are explicit validation outputs. Chemical time zero is an optically observed
sample-plane pump/probe relation, never an electrical-command or equal-cable-length
assumption.
