# Experimental architectures for HRP–CO and MbCO photolysis and recombination

Status: **requirements-level experimental design; not an executable recipe**

This document defines the experimental architectures, calibration and
characterization requirements, controls, analysis, and claim boundaries for
room-temperature and nominal 77 K HRP–CO and MbCO measurements. It does not
authorize hardware operation, change a campaign phase, or promote a device
configuration. Operational values must come from accepted calibration,
characterization, and sample-pilot evidence.

## Parameter-value policy

Numerical values in this document belong to one of four classes:

- **Literature prior:** a published value used to design measurement coverage.
  It is not a constraint on the present sample.
- **Manufacturer bound:** a documented device capability or limit. It is not
  proof of installed-system performance.
- **Illustrative example:** a calculation that demonstrates how a method would
  be configured. It is explicitly labeled `EXAMPLE ONLY` and is not an
  operating setting.
- **Measured/optimized value:** a value selected from accepted installed-system
  evidence and recorded with its uncertainty, validity envelope, and
  configuration identity. Only this class may enter a frozen biological recipe.

No pulse width, repetition rate, scan speed, wavelength interval, wavelength
increment, phase increment, lock-in filter, detector range, number of averages,
pump fluence, inter-pulse recovery time, cryostat equilibration time, or fitting
model is assigned here merely because the device can support it or literature
used it. Each must be measured, optimized, or justified as described below.

## 1. Purpose and scientific questions

The program is intended to determine, within the measured response and
sensitivity of the installed apparatus:

1. the sample-specific bound-CO spectrum of HRP–CO and MbCO at room temperature
   and 77 K;
2. whether visible excitation produces a reproducible bound-CO bleach;
3. the amplitude and temporal behavior of instrument-resolved geminate or
   intrapocket rebinding;
4. the room-temperature recovery envelope associated with CO that has escaped
   the heme pocket;
5. whether the bound conformational populations have distinguishable kinetics;
6. how cooling to 77 K changes band centers, widths, populations, recovery
   distributions, and the accessibility of ligand escape;
7. whether each mechanistic claim remains identifiable after convolution with
   the complete instrument response function and after accounting for
   preparation, temperature, dose, drift, and normalization uncertainty.

The minimum acceptable product is a calibrated, reproducible pump-induced
difference signal and an apparent recovery description over the
instrument-resolved interval. A geminate lifetime, geminate fraction,
state-specific mechanism, or solvent-rebinding assignment is a stronger claim
and requires the additional tests specified in this document.

## 2. Executive architecture assignment

| Condition | Assigned primary architecture | Supporting architecture | Principal claim boundary |
|---|---|---|---|
| Room-temperature HRP–CO geminate | **Nanosecond stroboscopic reconstruction** | Local fixed-wavenumber discovery kinetics and off-band controls | A lifetime is conditional on IRF-convolved identifiability; otherwise report a prompt component or upper bound |
| Room-temperature HRP–CO non-geminate | **Repeated rapid-scan phase-delay reconstruction** | Selected-band continuous recovery traces | Use the many consecutive scans after each rare pump event; do not treat an individual scan as instantaneous |
| Room-temperature MbCO geminate | **Nanosecond stroboscopic reconstruction** | A₁-first fixed-wavenumber discovery and optional A₀/A₃ extension | The historical approximately 4%, 180 ns result is a prior, not a fit constraint |
| Room-temperature MbCO recovery/non-geminate candidate | **Microsecond stroboscopic reconstruction** | **Single-scan phase-delay reconstruction** for spectral support | The approximately 185 µs and 1 ms literature components are phenomenological until mechanism tests support an assignment |
| 77 K HRP–CO geminate/intrapocket | **Nanosecond stroboscopic reconstruction** for the fast branch | **Single-pump rapid-scan and logarithmic scan-burst reconstruction** for slower branches | Repeated-event phase reconstruction is allowed only after an equivalent-state reset is demonstrated |
| 77 K MbCO geminate/intrapocket | **Nanosecond/microsecond stroboscopic reconstruction** for resolvable fast A-state recovery | **Single-pump rapid-scan and logarithmic scan-burst reconstruction** for slow recovery | Slow scanning alone cannot establish fast A-state kinetics; repeated pumping cannot be assumed to reset a cryogenic sample |

No dedicated 77 K process is initially labeled non-geminate. Below the glass
transition, ligand escape and bulk-solvent return are suppressed. Slow recovery
at 77 K remains a slow geminate/intrapocket candidate unless ligand escape is
demonstrated independently.

## 3. Terminology and time conventions

### 3.1 Geminate and non-geminate recombination

**Geminate recombination** means that photodissociated CO rebinds to the heme
from within the protein or heme pocket before equilibrating with bulk solvent.
At low temperature, the term includes distributed intrapocket recovery from a
heterogeneous ensemble.

**Non-geminate or solvent recombination** means that CO has escaped to the bulk
solvent and later returns to the protein and heme. A slow time constant or a
biexponential fit is not, by itself, proof of this mechanism. Concentration
dependence, temperature dependence, mass balance, and independent evidence for
escape must be considered.

### 3.2 Stroboscopic reconstruction

In this document, **stroboscopic reconstruction** means wavelength-by-wavelength
equivalent-time pump–probe acquisition. At each selected wavenumber, nominally
equivalent pump–probe events are repeated at a set of pump-to-probe delays. The
individual traces are combined into

\[
\Delta A(\tilde\nu,t).
\]

`ns stroboscopic reconstruction` and `µs stroboscopic reconstruction` are the
same architecture with different delay grids, integration apertures, IRF
requirements, and recovery burdens. Neither term implies that the MIRcat emits
a complete spectrum in one pulse.

### 3.3 Rapid-scan and phase-delay reconstruction

A MIRcat scan is a trajectory through both wavenumber and time. For scan phase
\(j\), scan index \(n\), and wavenumber \(\tilde\nu\),

\[
t_{j,n}(\tilde\nu)=\phi_j+nT_{scan}+\tau_{scan}(\tilde\nu),
\]

where \(\phi_j\) is the observed pump-to-scan phase, \(T_{scan}\) is the measured
scan period, and \(\tau_{scan}\) is the calibrated time at which that scan reaches
the wavenumber. A single scan is therefore a diagonal observation through
\((\tilde\nu,t)\), not an instantaneous spectrum.

**Repeated rapid-scan phase-delay reconstruction** retains many consecutive
scans after one pump event and repeats the recovery movie at a small number of
phase offsets.

**Single-scan phase-delay reconstruction** retains one deliberately phased scan
per pump event and repeats the event over a larger set of phase offsets. It is
appropriate only when every pump event begins from an equivalent sample state.

**Single-pump scan-burst reconstruction** uses one pump event followed by a
rapid early scan sequence and later scan bursts. It does not require the sample
to reset between different phase offsets and is therefore the default slow
cryogenic architecture.

### 3.4 Time zero and the instrument response function

Chemical time zero is the arrival of the pump at the sample, not a T660 command
edge. Define

\[
t= t_{probe,sample}-t_{pump,sample}.
\]

Positive delay means the probe interrogates the sample after pump arrival.
Negative delays establish the pre-pump baseline and test for artifacts.

The complete instrument response function (IRF) includes, as applicable:

- the pump optical pulse envelope;
- the MIRcat probe optical pulse envelope;
- pump–probe relative timing jitter;
- optical path differences at the actual sample position;
- detector and preamplifier impulse responses;
- cable, splitter, and acquisition-channel latency;
- the PicoScope sampling aperture and trigger uncertainty;
- HF2LI demodulation, filtering, sampling, and timestamp behavior;
- scan trajectory and scan/filter history for scanning modes.

The recorded signal is modeled as the underlying chemical response convolved
with the measured IRF, plus noise and drift. A nominal 20 ns MIRcat pulse does
not establish 20 ns system resolution.

## 4. Scientific basis and literature planning windows

### 4.1 HRP–CO

HRP–CO shows condition- and isoenzyme-dependent bound-CO features. HRP-C
literature commonly places two conformer-associated bands near 1905 and
1934 cm⁻¹, but their exact centers and populations depend on pH, solvent,
temperature, sample identity, and fitting convention. These bands are not
separate geminate and non-geminate products.

Doster and coworkers reported room-temperature solvent recombination of order
1 s⁻¹ at 1 atm CO and bond formation at the heme in less than 100 ns. At low
temperature they observed multiple internal HRP processes, including an
exponential \(I^*\) process and non-exponential \(I\) processes associated with
different carbonyl states. Those values establish the need for distinct fast
and slow architectures; they do not fix the present sample's rates.

### 4.2 MbCO

The bound MbCO A substates are generally found near:

- A₃: approximately 1932–1937 cm⁻¹ at room temperature;
- A₁: approximately 1943–1945 cm⁻¹ at room temperature;
- A₀: approximately 1965–1967 cm⁻¹ at room temperature.

At low temperature, published centers near 1929, 1947, and 1967 cm⁻¹ have been
used for A₃, A₁, and A₀ in a glycerol/buffer matrix. These are search anchors,
not programmed wavenumbers. The A states are bound conformational substates and
are not inherently geminate or non-geminate bands.

Henry and coworkers reported approximately 4% room-temperature MbCO geminate
rebinding with a 180 ns relaxation time. Schleeger and coworkers reported
phenomenological A₁ recovery components near 185 µs and 1.0 ms with 5 µs time
resolution. Below approximately 160 K, published MbCO results show
non-exponential, A-state-specific intrapocket rebinding, with A₀ fastest, A₁
intermediate, and A₃ slowest. At approximately 70 K, recovery of a strong band
near 1945 cm⁻¹ was observed over about 20 minutes while a band near 1926 cm⁻¹
showed no detectable recovery in that interval.

### 4.3 Observable spectral region

The installed MIRcat follows depletion and repopulation of the bound HRP–CO and
MbCO bands. Photodissociated-pocket MbCO B-state bands reported above the
installed MIRcat range cannot be observed directly with this configuration.
Consequently, mechanism must be inferred from the time, temperature,
concentration, dose, and state dependence of the accessible bound-band signals,
not from direct observation of every CO docking site.

## 5. Measurement topology and device roles

### 5.1 Timing and source roles

- The Nd:YAG/OPO pump can emit at no more than 10 Hz. The effective pump rate
  delivered to the sample may need to be much lower and must be determined from
  recovery and damage tests.
- The MIRcat probe frequency is independent of the 10 Hz pump limit. Its pulse
  width and repetition rate may be combined only within the manufacturer's
  duty-cycle limit and the narrower installed-system stability, detector,
  synchronization, and heating envelope established by characterization.
- The T660 timing system defines commanded relationships, but optical
  pump–probe delay is obtained only after the electrical-to-optical timing chain
  is calibrated.
- MIRcat `Tuned/Sweep Active`, scan-direction, wavelength-trigger, actual
  wavenumber, module, and emission/status records are retained whenever relevant.

### 5.2 HF2LI and PicoScope roles

The HF2LI is the primary instrument for recording the normalized sample and
reference spectral streams. The PicoScope does not replace it. The PicoScope
provides independent evidence for pulse shape, trigger behavior, path latency,
detector response, branch skew, saturation, and timing closure.

Two explicitly qualified wiring configurations are required:

1. **Normal dual-detector acquisition:** each detector signal passes through
   its own **female-to-female BNC adapter -> male-to-two-female BNC tee**,
   with separate cable branches to the two receivers. Sample feeds **HF2LI
   Signal 1 In (+) and PicoScope CHA (channel A)**; reference feeds **HF2LI
   Signal 2 In (+) and PicoScope CHB (channel B)**. Both receivers remain
   connected even when the PicoScope is not recording; the Arduino MUX is
   bypassed. See the [default wiring diagram](instrument/default_wiring_state.md).
   The two destinations need not have identical
   electrical input impedances; loading, attenuation, reflections, branch skew,
   and bandwidth must be measured in the installed configuration.
2. **Sample-plane timing/IRF configuration:** the sample IR detector is observed
   on PicoScope channel A and the UV–visible pump detector at the sample plane is
   observed on PicoScope channel B. This configuration measures relative optical
   arrival and the sample-path response. Because the sample and reference optical
   paths differ, reference-path latency and response must be measured separately
   when they enter the normalization or timing model.

The adapter/tee topology is the operator-reported default as of 2026-08-31;
its documentation is not evidence of qualified electrical transfer. MS-02.1
qualifies the installed branches without rewriting completed MS-01/MS-02 or
HF-01 records. Temporary timing/IRF work records any disconnected detector
branch and changed loading, then restores both default split paths.

The PicoScope external-trigger source, polarity, threshold, impedance, and
latency must be selected and qualified. An electrical trigger may aid stable
capture, but the optically observed pump remains the chemical time-zero
authority. Using a presently unused T660 output would constitute a topology
change and requires the corresponding wiring, timing, and safe-idle updates; it
is not assumed here.

### 5.3 MIRcat process trigger and readiness

The legacy MIRcat manual excerpt describes an active-low external-process pulse
of 250–500 ms. Later manufacturer correspondence specific to this installation
states that approximately 1–100 ms is sufficient. These values describe command
widths, not wavelength-settling times. The installed acceptable pulse-width
interval, one-command/one-transition behavior, and failure response must be
measured before a value is selected.

After a discrete wavelength command, acquisition begins only after the accepted
`Tuned`/readiness criterion and detector/HF2 settling criteria pass. No fixed
host delay is treated as a universal tune time.

## 6. Mandatory calibration and characterization program

### 6.1 Distinction

**Calibration** establishes mappings, corrections, reference-plane offsets, and
uncertainties needed to express results in physical units. **Characterization**
establishes stability, linearity, dynamic behavior, operating envelopes,
failure modes, and the tradeoffs used to optimize settings. Biological samples
verify sample behavior but do not calibrate the instrument.

### 6.2 Calibration quantities that must be systematically determined

| Quantity | Required determination and output | Claims supported |
|---|---|---|
| Installed identities and topology | Device, detector, cable, adapter, splitter/tee, connector, termination, firmware/software, and routing identities; reference planes and configuration ID | Reproducibility and traceability |
| Spectral axis | MIRcat commanded/readback wavenumber versus independently assigned reference features across every HRP/MbCO window; correction, residuals, uncertainty, and validity range | Peak centers, band shifts, component fitting |
| Scan trajectory | Actual \(\tilde\nu(t)\) for every retained scan speed, direction, width, start condition, and module transition; trigger/status alignment and uncertainty | Phase-delay reconstruction and spectral timing |
| Discrete tuning | Command-to-tune transition, `Tuned` assertion, optical settling, direction/history dependence, failures, and uncertainty | Stroboscopic wavelength stepping and dwell |
| T660 routes | Programmed-to-observed edge delay, width, polarity, amplitude, termination, jitter, route interaction, and uncertainty for each used path | Pump–probe delay and trigger closure |
| Pump arrival | Electrical command to post-iris 540 nm optical arrival at the sample plane, with event-to-event jitter | Chemical time zero |
| Probe arrival | MIRcat trigger/reference to MIR optical arrival at the sample plane for every retained probe mode and relevant wavenumber | Pump–probe delay and IRF |
| PicoScope channels | Timebase, sampling interval returned by the API, channel skew, external-trigger latency, threshold behavior, amplitude scale, bandwidth, and uncertainty at the used settings | Independent timing and waveform validation |
| Split detector branches | Tee/adapter/cable attenuation, loading, reflection/ringing, bandwidth, and skew to HF2LI and PicoScope; repeat after material rewiring | Cross-instrument comparisons and IRF |
| Detector transfer | Dark offset, gain, bandwidth, impulse response, latency, linearity, saturation and recovery for sample and reference detectors | Normalization, timing, SNR, artifact rejection |
| Dual-detector normalization | Wavelength-dependent sample/reference transfer ratio, covariance, common-mode rejection, residual baseline, and uncertainty | Absorbance and difference absorbance |
| HF2LI response | External-reference phase, demodulator mapping, filter impulse/step response for retained order/time-constant combinations, sample timestamps, actual stream rate, and settling | Kinetic convolution and scan fidelity |
| Average optical power | Working-reference identity, zero/range/stability, wavelength response, sample-plane transfer, and uncertainty for pump and probe measurements | Dose and heating bounds |
| Pump wavelength | Independent 540 nm center/status measurement with uncertainty and native response records; residual spectral content assessed by the appropriate source characterization | Pump identity and reproducibility |
| Cell path length | Assembled optical path with uncertainty, including temperature dependence where material | Quantitative absorbance and concentration comparisons |
| Temperature | Sensor calibration, location, repeatability, gradient from sensor to sample, stability, and uncertainty at room temperature and 77 K | Temperature-dependent spectral and kinetic claims |
| Complete IRF | Sample-plane pump/probe envelopes, relative jitter, detector responses, branch latencies, acquisition apertures, HF2 effects, and scan history combined and validated | Resolved lifetimes, fractions, and upper bounds |

Calibration results must be linked by stable human-readable configuration and
condition identifiers. A changed cable, splitter, detector, filter topology,
sample geometry, scan mode, or timing route is assessed against the calibration
validity envelope and bridged or recalibrated when necessary.

### 6.3 Characterization quantities that must be systematically determined

#### MIRcat probe

Determine, over every candidate biological spectral window:

- accessible wavenumber range and module identity;
- optical output versus wavenumber, commanded current, pulse width, and
  repetition rate;
- pulse-to-pulse amplitude, pulse-width, timing, and baseline stability;
- linewidth/effective spectral resolution and wavelength drift;
- duty-cycle calculation and observed thermal behavior;
- missing, double, or malformed pulses under external triggering;
- stability at low repetition and at high-rate carrier operation;
- scan speed accuracy, acceleration/deceleration regions, turnaround behavior,
  direction hysteresis, and scan-to-scan repeatability;
- discrete tune latency, optical settling, `Tuned` reliability, process-trigger
  accepted width, and transition-fault behavior;
- heating or baseline disturbance imparted to the sample by the probe.

The MIRcat manufacturer capability of high repetition and the 30% duty-cycle
ceiling are bounds only. The biological operating envelope is the intersection
of stable probe output, timing compatibility, detector linearity, HF2LI
reference capability, acceptable sample heating, and adequate SNR.

#### Nd:YAG/OPO pump

Determine at the unchanged biological 540 nm path:

- stable source cadence and the independently observed rate delivered to the
  sample;
- optical arrival, duration bound, jitter, and event-count reconciliation;
- center wavelength/status and residual-output bounds;
- post-iris average power and its short- and long-term stability;
- beam centroid, radii/profile, pointing drift, polarization when relevant,
  clipping/aperture margin, and spatial overlap with the probe;
- dose linearity, minimum detectable photolysis, saturation, cumulative exposure,
  local heating, and reversible operating interval;
- behavior of any pulse-division, picker, or shutter scheme used to preserve
  source thermal stability while limiting sample exposure.

Average power divided by independently verified repetition may be reported as a
derived mean pulse energy with propagated uncertainty. It does not establish
the pulse-energy distribution or peak power.

#### HF2LI, detectors, and PicoScope

Systematically determine:

- detector dark noise, illuminated noise, 1/f behavior, drift, cross-talk,
  linear range, clipping margin, latency, bandwidth, recovery from pump scatter,
  and temperature sensitivity;
- the effect of tee loading and simultaneous HF2LI/PicoScope connection on both
  detector outputs;
- HF2LI reference acquisition and lock quality over every candidate probe rate;
- external-reference frequency limits for the actual DIO/analog topology;
- demodulator phase, harmonic, order, time constant, output rate, filter memory,
  settling, and attenuation of synthetic and optical test features;
- timestamp continuity, missed samples, loss/relock behavior, stream alignment,
  and endurance over the longest planned record;
- PicoScope vertical range, resolution/bandwidth tradeoff, sampling interval,
  record length, trigger stability, pretrigger baseline, segment loss, and
  overflow behavior;
- agreement between HF2LI amplitudes and PicoScope pulse/waveform diagnostics
  within their separately calibrated transfer functions.

The HF2LI remains the primary spectral recorder. A kinetic claim outside its
measured response envelope requires an explicitly validated equivalent-time
measurement and supporting fast-path evidence; it must not be created by
unbounded deconvolution.

#### Cell, sample geometry, and cryostat

Determine separately for HRP–CO and MbCO and separately at room temperature and
77 K:

- window material, spacer/seal compatibility, assembled path, leak integrity,
  blank transmission, fringes, scatter, and repeatable placement;
- actual pump and probe beam profiles at the sample, overlap integral,
  illuminated volume, and sensitivity to realignment;
- sample/reference path imbalance and wavelength-dependent normalization;
- temperature sensor location, sample-to-sensor gradient, equilibration time,
  drift, and repeatability;
- cryostat-window transmission, reflections/fringes, contraction, focus/beam
  shift, icing/condensation, purge adequacy, and mechanical stability;
- matrix glass formation, absence of macroscopic ice segregation, protein/CO
  state retention, and temperature-dependent path/optical changes;
- pump- and probe-induced local heating and return to the accepted temperature;
- sample recovery, photoproduct accumulation, damage, and whether fresh
  positions or a thermal reset provide equivalent initial states.

The sample temperature is reported with uncertainty. A liquid-nitrogen bath or
nominal 77 K cryostat value is not by itself proof that the illuminated sample
is at 77 K.

#### Reconstruction algorithms and nonbiological validation

Before biological reconstruction, use an appropriate nonbiological optical or
electronic surrogate to determine:

- whether the system recovers a known prompt or imposed transient;
- bias and resolution of wavelength-by-wavelength delay reconstruction;
- phase-delay coverage, interpolation support, and edge effects;
- scan-direction dependence and wavelength/time covariance;
- HF2 filter-induced spectral smearing and phase bias;
- sensitivity to phase error, missing scans, dropped samples, drift, and
  heteroscedastic noise;
- the minimum phase density and average count needed for prespecified precision;
- which regions of \((\tilde\nu,t)\) are identifiable and which must remain
  unreported.

Publish the actual native \((\tilde\nu,t)\) coverage matrix. Reconstructed pixels
without adequate native support are not treated as observations.

### 6.4 Quantities to optimize rather than assume

Optimize in a staged, prospectively recorded sequence:

1. sample/cell transmission and detectable bound-CO absorbance;
2. probe operating envelope and detector linearity;
3. pump dose and reversible photolysis response;
4. timing/IRF and acquisition topology;
5. HF2LI filter/order/output rate and any PicoScope diagnostic settings;
6. steady-scan speed, direction, sampling density, dwell, and averaging;
7. stroboscopic delay grid and integration aperture;
8. rapid-scan speed/window and phase increments;
9. pump repetition/recovery interval and total event budget;
10. number of technical averages and independent preparations required for the
    target uncertainty;
11. final model complexity supported by the measured data.

Optimization must minimize total uncertainty and sample exposure, not maximize
one metric in isolation. For example, a shorter lock-in time constant can improve
temporal response while worsening SNR; a faster scan can reduce wavelength–time
distortion while increasing filter-induced spectral broadening; and a higher
probe rate can improve averaging while increasing heating.

### 6.5 Calibration/characterization completion gate

No architecture is frozen until all quantities that materially affect its claim
have accepted values, uncertainties, validity limits, and revalidation triggers.
At minimum, the applicable spectral axis, scan/tune behavior, timing closure,
IRF, detector response, normalization, power/geometry, overlap, temperature,
noise/sensitivity, and reconstruction validation must be complete.

## 7. Mandatory initial slow scan for every protein and temperature

An accepted slow steady-state scan is required before time-resolved work for
each of these four conditions:

1. room-temperature HRP–CO;
2. 77 K HRP–CO;
3. room-temperature MbCO;
4. 77 K MbCO.

Room-temperature peak locations are never copied into a 77 K recipe. A scan from
one preparation is not automatically valid for another preparation, lot, pH,
matrix, cell reload, temperature cycle, or changed optical configuration. The
campaign must define when a new initial scan is required and when a short
verification scan is sufficient.

### 7.1 Purpose

The initial slow scan determines:

- the exact sample-specific band centers and their uncertainties;
- peak widths, asymmetry, shoulders, and resolvable component count;
- integrated areas and relative conformer populations;
- local baselines and off-band control regions;
- water/matrix/cell transmission and interference fringes;
- whether the expected protein–CO state is present and quantifiable;
- the local spectral windows and spacing required by subsequent stroboscopic
  reconstructions;
- whether cooling shifts, splits, narrows, broadens, or changes the relative
  areas of the bands;
- pre-experiment reference values for post-exposure integrity testing.

### 7.2 Parameter selection

The slow-scan speed, direction, range, sampling interval, effective resolution,
HF2LI filter, settling/dwell, probe pulse settings, and number of averages are
selected from spectral-axis, MIRcat, detector, HF2LI, and noise
characterization. They are not assigned here.

`EXAMPLE ONLY:` an HRP survey might span a region wide enough to bracket the
literature anchors near 1905 and 1934 cm⁻¹ with off-band baseline on both sides.
An MbCO survey might span approximately 1920–1975 cm⁻¹ or a wider region if the
matrix/background requires it. These example ranges do not replace the
calibrated usable-range and sample-spectrum decision.

The wavelength increment should be fine enough to locate fitted centers and
line shapes but no finer than justified by effective spectral resolution,
wavenumber uncertainty, linewidth, stability, and SNR. Forward and reverse
directions must be compared before they are pooled.

### 7.3 Acquisition sequence

1. Verify accepted instrument configuration, safe state, cell identity,
   preparation identity, pH/matrix, temperature, and equilibration.
2. Acquire detector dark and the applicable empty-cell or matched-background
   spectra.
3. Acquire the unpumped sample in both scan directions using the characterized
   settle and averaging rules.
4. Retain native sample and reference channels, MIRcat status/readback,
   temperature, scan trajectory, overload/error flags, and rejected scans.
5. Fit the background and sample using a prospectively selected line-shape and
   baseline comparison. Do not add peaks solely to force agreement with
   literature.
6. Select local band windows and off-band regions from the accepted fit and its
   uncertainty.
7. Repeat a reduced verification scan immediately before the time-resolved block
   if the full scan and experiment are separated by a material interval or state
   change.
8. Acquire an equivalent post-exposure scan and compare center, width, area,
   baseline, and state integrity using prespecified tolerances.

### 7.4 Peak-fitting outputs

For every accepted band report:

- fitted center and calibrated wavenumber uncertainty;
- width and effective instrumental resolution;
- peak height and integrated area;
- baseline model and local residuals;
- covariance/correlation among overlapping components;
- forward/reverse scan comparison;
- preparation, temperature, pH/matrix, cell/path, and configuration identity;
- the selected local stroboscopic window and rationale.

## 8. Acquisition architectures

### 8.1 Nanosecond stroboscopic reconstruction

#### Measurement concept

The MIRcat is placed at a selected wavenumber and a probe pulse is positioned at
a controlled delay relative to an independently observed pump event. Equivalent
events are repeated and averaged. The delay is changed across events; after the
delay schedule at that wavenumber is complete, the MIRcat advances to another
wavenumber in the local band window.

This method reconstructs an early-time local spectrum without requiring the
MIRcat to tune during the nanosecond event. The tuning time occurs between
completed delay series and does not define temporal resolution.

#### Delay-grid rule

The grid must contain:

- multiple negative delays outside the measured IRF support;
- dense coverage of the rise and earliest recovery;
- point spacing no larger than justified by the measured IRF and timing
  uncertainty;
- coverage through enough expected lifetimes to separate a fast component from
  an unresolved offset;
- bridge points into the microsecond and slower regime;
- randomized or counterbalanced delay order where practical.

`EXAMPLE ONLY:` for a historical 180 ns MbCO prior, an exploratory grid could
include several negative controls, dense tens-of-nanoseconds sampling around
zero, coverage through approximately 0.9 µs, and bridge points beyond 1 µs. The
actual grid must be designed by IRF- and noise-aware forward simulation.

#### Event burden and timing

The approximate number of accepted events is

\[
N_{event}=N_{\tilde\nu}N_{delay}N_{average}N_{condition}.
\]

The wall-clock duration is set mainly by the effective pump rate and the
verified sample-reset interval, not by MIRcat wavelength tuning. Pump-on,
pump-blocked, negative-delay, dose, and other conditions must be included in the
event budget.

#### Required outputs

- native pump and probe timing evidence;
- native HF2LI sample/reference streams;
- PicoScope timing/waveform evidence inside its qualified role;
- pump-induced \(\Delta A\) at each native \((\tilde\nu,t)\) point;
- reconstructed local spectra and wavelength-specific kinetics;
- IRF-convolved fits and identifiability simulations;
- explicit unresolved-component bounds when the lifetime is not identifiable.

### 8.2 Microsecond stroboscopic reconstruction

The acquisition topology is identical to nanosecond stroboscopy, but the delay
grid and integration aperture target microsecond-to-millisecond recovery. It is
normally more tolerant of probe width and jitter, but HF2LI filter response,
detector latency, sample rate, and averaging aperture must still be included in
the response model.

The grid should be information-based rather than uniformly dense. Include an
IRF-resolved early region, logarithmically or model-optimally spaced recovery
points, and a demonstrated return to the pre-pump state. If a local band area is
required, acquire enough nearby wavenumbers to fit or integrate the band rather
than treating one nominal center as the complete spectrum.

### 8.3 Repeated rapid-scan phase-delay reconstruction

#### Measurement concept

The MIRcat scans continuously through the selected spectral window. After an
accepted pre-pump scan train, one pump event occurs at a controlled phase. The
system continues scanning through the complete recovery. The experiment is
repeated only after recovery, at a small set of pump-to-scan phase offsets.

This architecture is efficient when the chemical recovery is much longer than
the scan period because one pump event provides many spectral trajectories.

#### Parameter relationships

For measured scan width \(\Delta\tilde\nu\), scan speed \(v_{scan}\), and phase
increment \(\Delta\phi\),

\[
T_{scan}=\frac{\Delta\tilde\nu}{v_{scan}},\qquad
N_{\phi}\approx\left\lceil\frac{T_{scan}}{\Delta\phi}\right\rceil.
\]

This relationship is a planning equation. The final phase count is determined
from calibrated trajectory coverage, target temporal precision, missing-data
robustness, and reconstruction validation.

The approximate filter-induced spectral smear is

\[
\Delta\tilde\nu_{filter}\sim v_{scan}\tau_{eff},
\]

but final analysis uses the measured multi-stage HF2LI/filter response rather
than a rectangular approximation.

`EXAMPLE ONLY:` a 50 cm⁻¹ scan at 10,000 cm⁻¹/s would last 5 ms, and a 1 ms
phase increment would nominally require five interleaved phases. These values
illustrate the calculation only; actual scan speed, width, phase increment, and
filter must be optimized together.

#### Required acquisition features

- sufficient pre-pump scans to characterize stationarity;
- the pump-crossing scan retained rather than discarded;
- every post-pump scan through verified recovery;
- forward and reverse directions retained separately until equivalence is shown;
- pump-blocked, probe-only, and phase-matched artifact controls;
- actual scan trajectory and observed pump time for every sample;
- rejected, clipped, unlocked, or incomplete scans retained and flagged.

### 8.4 Single-scan phase-delay reconstruction

One scan is acquired at a controlled phase after each pump event. After complete
sample reset, the phase is changed and the event is repeated. The phase set
interleaves diagonal scan trajectories into a denser \((\tilde\nu,t)\) map.

This method is useful when the process is too fast for many sequential scans
after one event but slow enough that a practical phase grid can cover the
required window. It is less efficient than repeated rapid scanning for a
seconds-long recovery and more demanding than local stroboscopy for a weak,
nanosecond component.

For a process that changes appreciably during one scan, reconstructed spectra
must be based on the calibrated native trajectory and multiple phase offsets.
Moving the scan endpoint does not by itself create temporal resolution; the
resolution comes from the phase spacing, IRF, filter response, and native
coverage.

`EXAMPLE ONLY:` a 55 cm⁻¹ scan lasting 5.5 ms with 25–50 µs phase increments
would require approximately 110–220 nominal phases. That example shows why this
method can support microsecond–millisecond MbCO spectral reconstruction but is
not an efficient way to create a 20 ns-resolved full spectral movie.

### 8.5 Single-pump rapid-scan and logarithmic scan-burst reconstruction

This architecture is intended for cryogenic samples that may not reset between
pump events:

1. acquire stable pre-pump spectra;
2. apply one independently observed low-dose pump event;
3. acquire the fastest useful continuous scan train during the earliest
   interval allowed by SNR, data volume, and probe-heating limits;
4. reduce probe duty by collecting scan bursts at increasing elapsed times;
5. continue until each measurable band reaches a plateau or the planned
   observation limit;
6. preserve any unrecovered population as a result.

The elapsed-time schedule should initially be logarithmic or information-based,
then refined where curvature or model uncertainty is largest. The **chemical
timescale may be slow, but the individual scan should not be slowed without a
reason**. Each scan duration must remain negligible relative to the local
kinetic change or be explicitly represented as a wavelength/time trajectory.

Repeated phase offsets may be added only after full spectral recovery, a thermal
reset, or fresh-position equivalence is demonstrated. Otherwise a sequence of
pumped phase scans would describe progressive accumulation, not repeated
measurements of one kinetic process.

## 9. Room-temperature HRP–CO experiments

### 9.1 Mandatory initial HRP–CO slow scan

Acquire and fit the initial slow steady-state spectrum as described in Section
7. Search broadly enough to identify both sample-specific HRP–CO populations
and local baseline. Select the nanosecond stroboscopic windows and the
non-geminate rapid-scan range from the fitted centers, widths, overlap, axis
uncertainty, and SNR—not from the nominal 1905/1934 cm⁻¹ anchors alone.

### 9.2 RT-HRP-G: nanosecond stroboscopic reconstruction

#### Objective

Search for an instrument-resolved early HRP–CO intrapocket component at both
bound-CO populations and determine whether the data support a lifetime,
fraction, or only a prompt unresolved amplitude.

#### Spectral selection

- Use a small, symmetric local range around each fitted HRP–CO peak.
- Include sufficient baseline on each side to distinguish center/area changes
  from broadband artifacts.
- Include at least one off-band point or local off-band window.
- Select the number and spacing of wavenumbers from the measured linewidth,
  spectral resolution, tuning burden, and sensitivity.

#### Acquisition

1. Verify the accepted steady-state HRP–CO spectrum and sample integrity.
2. Establish time zero and the configuration-specific IRF in the sample path.
3. Acquire negative-delay and pump-blocked controls.
4. At each wavenumber, execute the optimized nanosecond delay grid with the
   required averages and dose/recovery checks.
5. Change wavenumber only after the completed delay block and accepted
   `Tuned`/settling state.
6. Counterbalance band order, delay order, and pump-on/control order to expose
   drift.
7. Repeat across independent preparations/days as determined from pilot
   variance.

Because room-temperature HRP recovery is slow, a single stroboscopic point may
require several seconds before the next equivalent event. The fast branch is
therefore a conditional mechanistic extension after the robust late-recovery
measurement is secured.

#### Analysis and claims

Fit both bands jointly where supported, allowing wavelength-dependent amplitude
and testing shared versus distinct early kinetics. Convolve all candidate models
with the measured IRF. A numerical sub-100 ns lifetime is accepted only when
simulation, profile likelihood or bootstrap analysis, and sensitivity to IRF
alternatives show that it is identifiable. Otherwise report the prompt bleach,
the resolvable fraction, and a bounded unresolved component.

### 9.3 RT-HRP-NG: repeated rapid-scan phase-delay reconstruction

#### Objective

Measure the complete bound-band spectral recovery after CO escape while using
the many scans available after one rare pump event.

#### Acquisition design

- Select a spectral window that includes both fitted HRP–CO bands and accepted
  off-band baseline.
- Optimize scan speed, direction, HF2LI filter, output rate, and phase increment
  jointly on a nonbiological surrogate and the unpumped HRP spectrum.
- Choose the post-pump record length from the observed recovery, not the
  approximately 1 s⁻¹ literature prior.
- Choose pump cadence from the lower confidence bound on recovery and the
  prespecified return-to-baseline requirement; the 10 Hz source maximum is not
  an acceptable sample cadence merely because it is available.

#### Sequence for each phase

1. Acquire sufficient pre-pump scans to establish spectral and normalization
   stationarity.
2. Apply one observed pump event at the selected phase.
3. Continue scanning without interruption through full recovery.
4. Confirm recovery using both fitted band areas and off-band baseline.
5. Repeat at the next phase only after the sample-state criterion passes.
6. Acquire phase-matched pump-blocked and probe-only controls.
7. Repeat forward and reverse scan directions and retain them separately until
   direction effects are bounded.

#### Analysis and claims

Fit native \((\tilde\nu,t)\) observations or a traceable likelihood derived from
them. Report reconstructed spectra for interpretation, but do not fit unsupported
interpolated pixels as though they were measurements. Begin with the least
complex IRF/filter-aware late-recovery model. Test whether the two bound bands
share a recovery rate. Add distributed, concentration-aware, or multiple
components only when residuals, uncertainty, and model-comparison simulations
support them.

The solvent-rebinding interpretation is supported by the room-temperature
timescale and literature but should be strengthened by CO-concentration or mass-
balance analysis when feasible. Instrument/filter relaxation, drift, heating,
and illuminated-volume exchange must be excluded as alternative explanations.

## 10. Room-temperature MbCO experiments

### 10.1 Mandatory initial MbCO slow scan

Acquire and fit the initial slow steady-state spectrum as described in Section
7. Locate A₃, A₁, and A₀ for the actual sample, pH, matrix, temperature, and cell.
Begin time-resolved work with A₁. Add A₃ and A₀ only if their fitted areas,
spectral separation, and pump-induced signals meet sensitivity and
quantification criteria.

### 10.2 RT-Mb-G: nanosecond stroboscopic reconstruction

#### Objective

Determine whether the apparatus resolves a small room-temperature geminate
component and, if supported, estimate its fraction and lifetime without fixing
the historical approximately 4% and 180 ns values.

#### Spectral and temporal design

- Use a local window around the fitted A₁ center as the primary measurement.
- Add local A₃ and A₀ windows only after their steady-state and pump-induced
  quantifiability is demonstrated.
- Include off-band and pump-blocked controls.
- Cover negative delays, the full IRF support, the candidate early decay, and
  bridge points into microsecond recovery.
- Select delay density and event count through forward simulation using the
  measured IRF, covariance, anticipated amplitude, drift, and allowed dose.

#### Required claim tests

A quantitative geminate fraction or lifetime requires:

- optically established time zero in the sample path;
- an IRF sufficiently narrow and stable for parameter identification;
- stable probe pulse amplitude and timing at the retained mode;
- adequate detector/HF2LI response with PicoScope timing support;
- recovery of simulated parameters without boundary solutions;
- fitted stability to baseline, IRF, noise, and averaging alternatives;
- independent replication and no cumulative-state or damage trend.

If these tests fail, report the prompt bound-CO bleach and the
microsecond–millisecond recovery without claiming a resolved 180 ns lifetime.

### 10.3 RT-Mb-R-K: microsecond stroboscopic reconstruction

#### Objective

Obtain the highest-SNR quantitative local spectral recovery through the
microsecond-to-millisecond region and complete return to baseline.

#### Design

- Use the fitted A₁ window as primary; add A₃/A₀ when supported.
- Include an IRF-resolved prompt bridge, dense coverage where curvature is
  expected, logarithmic or model-optimal late points, and recovery confirmation.
- Determine the pump repetition rate from measured state recovery and damage.
  A 100 ms interval at 10 Hz may exceed published millisecond components, but
  this does not prove pre-pump equivalence or absence of accumulated heating.
- Complete the delay series at one wavenumber before advancing, unless a
  prospectively validated alternative order better controls drift.

#### Analysis

Fit band areas or justified local spectral models rather than relying only on a
single nominal center. Treat approximately 185 µs and 1.0 ms as starting priors
for coverage, not fixed rates or automatically distinct molecular pathways.
Test single apparent recovery, distributed or multi-component recovery, and
concentration-aware/mass-balance alternatives under the measured IRF and noise.

### 10.4 RT-Mb-R-S: supporting single-scan phase-delay reconstruction

#### Objective

Determine whether A₀, A₁, and A₃ exhibit distinguishable spectral evolution
through the microsecond–millisecond recovery, while retaining the actual
wavelength–time coupling of every scan.

#### Design and use

- Select the full or segmented spectral window from the initial MbCO fit.
- Optimize scan speed, phase density, direction, HF2LI response, and event count
  using the measured recovery and a nonbiological reconstruction validation.
- Acquire one deliberately phased scan per accepted pump event, with full reset
  before the next phase.
- Retain negative/pre-pump, pump-crossing, pump-blocked, forward, reverse, and
  complete-recovery controls.
- Use segmented local windows if full A₃-to-A₀ coverage creates unacceptable
  scan duration, phase count, filter smear, or sample burden.

This measurement supports spectral interpretation; the microsecond
stroboscopic result remains the primary quantitative local kinetic measurement.
Agreement between the two architectures is a valuable robustness test. A
disagreement triggers investigation of scan/time coupling, filter memory,
normalization, drift, and reset equivalence rather than automatic pooling.

## 11. Common 77 K requirements

### 11.1 Temperature and matrix identity

The target condition is nominally 77 K because liquid nitrogen is used, but the
fitted condition is the measured illuminated-sample temperature and uncertainty.
Room-temperature aqueous samples must not simply be frozen and treated as
equivalent cryogenic preparations. The glass-forming matrix, buffer, pH/pD
interpretation, protein concentration, reductant, CO loading, cell, thermal
history, cooling rate, equilibration, and sample state must be separately
qualified and recorded.

Published low-temperature HRP and MbCO work commonly used high glycerol fractions.
Those formulations are literature precedents, not assigned recipes. The selected
matrix must demonstrate:

- optical transmission and manageable fringes in the required MIR windows;
- a homogeneous glass without visible or spectroscopic ice segregation;
- retention of the intended ferrous–CO state;
- reproducible cooling and warming behavior;
- acceptable temperature gradients and beam stability;
- no unmodeled matrix photochemistry or pump/probe heating;
- sample-to-sample reproducibility sufficient for the intended comparison.

Room-temperature and 77 K results are separate experimental conditions. They
must not be pooled as though temperature were the only changed variable if the
matrix, cell, path, or sample preparation also changed.

### 11.2 Mandatory cryogenic slow scans

After equilibration at the measured cryogenic condition, acquire a new slow
steady-state scan for each protein. Fit all peak centers, widths, areas, and
baselines anew. These spectra determine the actual 77 K stroboscopic windows and
the spectral range for slow recovery. They also establish the pre-pump state
against which recovery and accumulation are judged.

### 11.3 Repetition and reset

At 77 K, a photoproduct can persist for minutes or longer. Repeated pumping may
therefore create a photostationary or progressively damaged state rather than
repeat the same reaction. Begin characterization with one accepted low-dose
pump event per equilibrated sample state. Repetition is permitted only after at
least one of the following is validated:

- full spectral recovery;
- a thermal reset that returns all relevant observables to the accepted state;
- a fresh sample position proven equivalent within the required uncertainty;
- a flow/replacement method that restores the same initial condition.

Equivalent-state validation includes band centers, widths, areas, baseline,
temperature, detector state, and absence of monotonic exposure history—not only
one peak height.

## 12. HRP–CO experiments at 77 K

### 12.1 77K-HRP-G-F: nanosecond stroboscopic reconstruction

#### Objective

Measure any resolvable fast internal HRP–CO recovery separately at the two
sample-specific cryogenic bound-CO populations.

#### Design

- Select local windows from the 77 K slow-scan fit; do not reuse room-temperature
  centers.
- Include off-band points and cryostat/matrix controls.
- Derive the delay grid from the cryogenic IRF and expected broad temporal
  coverage, extending from negative delay through the prompt, nanosecond,
  microsecond, and early slower region as feasible.
- Establish an equivalent initial cryogenic state for every stroboscopic point.
- If reset is achieved through fresh positions, randomize/counterbalance delay
  and band assignments over positions and include position as a statistical
  factor.

#### Analysis and claims

Use the least complex IRF-convolved model supported by the data. Preserve the
possibility of an exponential component plus distributed non-exponential
components, but do not force the number or values reported under another
matrix/temperature. A resolved component must remain identifiable when the
cryogenic IRF, position variation, baseline, and reset uncertainty are varied.

### 12.2 77K-HRP-G-S: single-pump rapid-scan and logarithmic scan-burst reconstruction

#### Objective

Measure slower distributed intrapocket recovery and the different spectral
behavior of the cryogenic HRP–CO populations without requiring repeated phase-
equivalent pump shots.

#### Acquisition

1. Acquire accepted pre-pump spectra and temperature history.
2. Apply one independently observed low-dose pump event.
3. Acquire the optimized continuous rapid-scan sequence for the earliest
   interval allowed by SNR, storage, and probe-heating limits.
4. Continue with scan bursts at logarithmically or information-optimally spaced
   elapsed times.
5. Monitor temperature before, during, and after scan bursts.
6. Continue until the measurable bands recover, plateau, or reach the planned
   observation limit.
7. Report any unrecovered fraction rather than normalizing the final spectrum to
   full recovery.

`EXAMPLE ONLY:` a discovery schedule could sample seconds, tens of seconds,
hundreds of seconds, and thousands of seconds more densely where the response
curves. The actual schedule is selected from pilot data and thermal/probe-duty
limits.

#### Conditional phase-delay extension

The originally proposed single-scan phase-delay reconstruction may be added at
77 K only if the sample can be returned to an equivalent state between phase
offsets. Without that evidence, the default is the one-pump scan-burst method.
A single un-interleaved scan remains a diagonal time/wavelength observation and
must be modeled accordingly.

### 12.3 77 K HRP mechanism boundary

All 77 K HRP recovery is initially described as fast or slow
geminate/intrapocket recovery. A non-geminate claim requires a separately
designed warming or escape experiment above the relevant glass-transition
regime, with its own temperature steps, equilibration, concentration logic, and
controls.

## 13. MbCO experiments at 77 K

### 13.1 77K-Mb-G-F: nanosecond/microsecond stroboscopic reconstruction

#### Objective

Measure early A-state-specific intrapocket recovery where the cryogenic IRF,
sample reset, and sensitivity make it possible.

#### Design

- Select local A₀, A₁, and A₃ windows from the fitted 77 K spectrum.
- Treat each A-state trace separately; do not collapse them into one MbCO
  lifetime.
- Include negative delays, off-band controls, and a schedule spanning the
  instrument-resolved prompt through microsecond and early slower behavior.
- Allocate the finest accessible temporal coverage to the fastest measurable
  state only after discovery data justify it.
- Stop or narrow the branch if equivalent-state reset consumes an unacceptable
  number of positions, produces non-equivalent baselines, or cannot meet the
  target uncertainty.

Literature suggests A₀ may recover fastest, A₁ intermediately, and A₃ slowest
below approximately 160 K. This ordering is a hypothesis to test, not a fixed
model constraint.

### 13.2 77K-Mb-G-S: single-pump rapid-scan and logarithmic scan-burst reconstruction

#### Objective

Measure slow, non-exponential and A-state-specific recovery over seconds to
minutes or longer while avoiding repeated-event accumulation.

#### Acquisition

1. Acquire the accepted 77 K steady spectrum, background, and temperature
   baseline.
2. Apply one independently observed low-dose pump event.
3. Acquire rapid early scans when they provide information not already captured
   by the fast stroboscopic branch.
4. Acquire later scan bursts at information-based elapsed times extending
   beyond the historical approximately 20-minute observation where necessary.
5. Fit and report recovered and unrecovered fractions separately for A₀, A₁,
   and A₃.
6. Preserve cryostat temperature, scan duty, and probe-heating records throughout
   the long observation.

The term “slow” refers to the chemical observation window, not automatically to
a low scan speed. The scan speed is optimized so that individual scans are short
relative to the local change while retaining sufficient spectral fidelity and
SNR. If a scan is not short relative to the kinetics, its full calibrated
wavelength/time trajectory is modeled.

#### Conditional slow phase-delay extension

Phase-delay reconstruction across multiple pump events may be added only after
full recovery, fresh-position equivalence, or a thermal reset is demonstrated.
Otherwise, the single-pump scan-burst data are the authoritative slow-recovery
record.

### 13.3 77 K MbCO mechanism boundary

Below approximately 160 K, the literature supports intrapocket rebinding and
suppressed A-state interconversion. Therefore no 77 K component is labeled
solvent rebinding solely because it is slow. A separate controlled warming
series is required to test the onset of escape, solvent return, and A-state
exchange.

## 14. Common controls

### 14.1 Optical and electronic controls

Every architecture includes, as applicable:

- detector dark records;
- pump blocked with probe operating;
- probe blocked with pump operating when detector safety permits;
- pump and probe blocked;
- empty-cell and matched buffer/matrix cell;
- cryostat/window blank at the relevant temperature;
- pump-only response of cell, matrix, and solvent;
- off-band wavelengths on both sides of the fitted spectral region when
  accessible;
- negative-delay measurements outside IRF support;
- nonbiological prompt surrogate for time zero/IRF;
- nonbiological spectral/transient surrogate for reconstruction validation;
- forward/reverse scan comparison;
- wavelength-order, delay-order, and phase-order controls;
- reference-lock loss, detector overload, missing-trigger, and recovery-from-
  fault tests during nonbiological qualification.

Pump scatter, electrical pickup, detector recovery, cell motion, thermal lensing,
refractive-index change, water/matrix response, and HF2LI filter memory must be
measured or bounded before a small biological transient is accepted.

### 14.2 Sample-state and damage controls

For each protein and temperature include:

- accepted pre-preparation material identity and lot;
- independent verification of the intended reduced CO-bound state;
- pre- and post-run UV–visible or other accepted state verification;
- pre- and post-run slow MIR spectrum;
- matched pH, buffer/matrix, reductant, CO-loading, and cell records;
- a pump-dose ladder beginning below the eventual operating region;
- pump-cadence/recovery tests;
- cumulative accepted-event count and illuminated-position history;
- repeated no-pump observation over the duration of the experiment;
- independent cell reloads and independent sample preparations;
- post-exposure checks for oxidation, leakage, bubbles, precipitation, peak
  loss/shift/broadening, baseline change, or unrecovered population.

### 14.3 Mechanism controls

Where a non-geminate or second-order claim is intended, vary or quantify free CO
and protein/sample mass balance sufficiently to test the expected dependence.
Where a conformer-specific claim is intended, compare local band areas/kinetics
with a global spectral model and test whether apparent differences can be
explained by unequal SNR, overlap, axis drift, detector response, or scan timing.

## 15. Replication, randomization, and what constitutes a preparation

An **independent preparation** is a separately executed chemical preparation of
the protein–CO state, including its own reduction, CO loading/equilibration,
cell filling, and state verification. Multiple pump shots, delay points, scans,
or averages from one filled cell are technical repetitions, not independent
preparations.

The hierarchy retained in analysis is:

1. pulse/probe observations within a condition;
2. technical averages within a wavelength/delay/phase block;
3. repeat blocks or cell positions;
4. cell reloads;
5. independent chemical preparations;
6. independent days/configuration realizations;
7. temperature/matrix/protein conditions.

Pilot data determine the number of technical averages and independent
preparations required for a prespecified confidence interval or power. Do not
substitute thousands of technical pulses for preparation-level replication.

Randomize or counterbalance, where physically possible:

- band and wavenumber order;
- delay and phase order;
- pump-on and pump-blocked control order;
- forward and reverse scan order;
- dose and cadence order;
- sample position and preparation assignment.

When randomization is unsafe or incompatible with recovery, use a balanced or
blocked sequence and include acquisition order/time as a diagnostic covariate.

## 16. Analysis and uncertainty

### 16.1 Primary observables

Retain and analyze:

\[
T(\tilde\nu,t)=
\frac{[V_s(\tilde\nu,t)/V_r(\tilde\nu,t)]_{sample}}
     {[V_s(\tilde\nu)/V_r(\tilde\nu)]_{matched\ background}},
\qquad
A=-\log_{10}T,
\]

and

\[
\Delta A(\tilde\nu,t)=A_{pump\ on}-A_{pump\ off}.
\]

The native sample and reference streams, their covariance, detector ranges,
lock state, timestamps, scan trajectory, pump observation, and exclusion flags
are never discarded after forming normalized data.

### 16.2 Spectral analysis

For steady and time-resolved spectra report:

- calibrated peak centers and shifts;
- widths and line-shape uncertainty;
- peak heights and integrated areas;
- component populations with covariance;
- local/global baseline alternatives;
- forward/reverse and scan-speed sensitivity;
- reconstruction support and native-data coverage.

Peak areas are generally more robust than a single point when a band can shift,
broaden, or overlap. Single-wavenumber kinetics remain valuable for discovery
and high-SNR validation but do not replace local spectral reconstruction when a
spectral claim is made.

### 16.3 Kinetic models

Begin with the least complex model capable of addressing the claim:

- apparent single recovery plus offset;
- shared versus band-specific apparent rates;
- prompt/unresolved fraction plus resolvable recovery;
- geminate plus solvent component where identifiable;
- distributed/non-exponential intrapocket recovery at low temperature;
- concentration-aware or mass-balance kinetics when free CO is not constant.

Every model is convolved with the appropriate measured IRF/acquisition kernel.
Do not fix published lifetimes or fractions. Do not infer molecular pathways
from a biexponential without independent evidence. Do not deconvolve beyond the
measured bandwidth and noise support.

### 16.4 Model evaluation

Report:

- residuals versus time, wavenumber, order, dose, temperature, and preparation;
- autocorrelation and heteroscedasticity;
- parameter covariance/correlation;
- profile-likelihood, bootstrap, or equivalent uncertainty intervals;
- sensitivity to IRF width/shape, time zero, baseline, normalization, filter,
  scan trajectory, and exclusion decisions;
- predictive/held-out performance where feasible;
- model comparison using prospectively selected criteria, not \(R^2\) alone;
- simulations showing whether the claimed parameters are identifiable under the
  measured schedule, SNR, and event budget.

### 16.5 Uncertainty budget

Include at minimum:

- spectral-axis correction, resolution, and tune/scan repeatability;
- sample/reference raw noise, covariance, transfer correction, nonlinearity,
  drift, and baseline;
- pump/probe timing, pulse envelopes, jitter, detector latency, acquisition
  aperture, HF2LI filter, PicoScope timebase, and phase assignment;
- temperature, pH, matrix, concentration, free CO estimate, cell path, and state
  fraction;
- pump average power, verified repetition, beam geometry, overlap, absorbed-dose
  model, and event count;
- preparation, cell reload, position, day, and configuration effects;
- reconstruction and interpolation bias;
- model-form and fit-parameter uncertainty.

## 17. Acceptance, stopping, and fallback logic

### 17.1 Common acceptance criteria

An experimental block is accepted only when:

- the initial and post-run state spectra satisfy the frozen integrity criteria;
- detectors remain in their characterized linear ranges without range changes;
- the HF2LI remains locked and timestamps/streams are complete;
- observed pump events reconcile with authorized events;
- MIRcat wavenumber/status and scan/tune readiness are valid;
- temperature remains within the accepted condition envelope;
- pump-blocked and off-band reconstructions are consistent with the artifact
  and detection limits;
- recovery/reset criteria pass before any event assumed equivalent;
- no monotonic damage, accumulation, or baseline trend invalidates the block;
- all native, rejected, diagnostic, and control records are retained.

### 17.2 Architecture-specific decisions

- If the IRF/SNR cannot identify a nanosecond lifetime, stop increasing model
  complexity and report a prompt or unresolved bound.
- If A₃ or A₀ is below quantification, retain its discovery result and focus the
  confirmatory MbCO measurement on A₁ rather than accumulating unsupported data.
- If full-window single-scan phase reconstruction requires excessive phase
  count or produces filter/trajectory bias, segment the spectrum or retain only
  microsecond local stroboscopy.
- If repeated rapid-scan data are distorted at a chosen scan/filter combination,
  re-optimize on nonbiological evidence before another biological block.
- If a 77 K sample cannot be reset reproducibly, do not use repeated phase-delay
  reconstruction; use the single-pump scan-burst record and fresh-position
  designs only where equivalence is established.
- If a cryogenic component remains unrecovered at the observation limit, report
  the unrecovered fraction and censoring/limit rather than imposing full recovery.

### 17.3 Abort and safe-stop conditions

Abort on a CO alarm or gas-system anomaly; laser/interlock fault; unidentified
beam; cell leak/crack/bubble; detector saturation; missing reference channel;
MIRcat wavelength/status mismatch; lost reference lock; timing-marker mismatch;
unexpected or missing optical pump event; exceeded event budget; unrecovered
sample where equivalence is required; temperature excursion; photodamage flag;
data-path failure; source/controller exception; or operator stop. Preserve all
records and apply the repository safe-idle/restoration procedure.

## 18. Planning equations and acquisition-time estimates

For wavelength-by-wavelength stroboscopy,

\[
T_{wall}\approx
\frac{N_{\tilde\nu}N_{delay}N_{average}N_{condition}}{f_{accepted}}
+\sum T_{tune/settle}+T_{controls}+T_{recovery}+T_{overhead}.
\]

Here \(f_{accepted}\) is the effective rate of accepted, independent sample
events, not the MIRcat carrier rate or the 10 Hz pump maximum. At 77 K,
\(T_{recovery}\) or fresh-position handling may dominate.

For discrete step-and-measure operation, the process-trigger command width and
the actual tune/settle time are separate terms. `EXAMPLE ONLY:` if an accepted
configuration used a 500 ms command for 34 transitions, command overhead would
be 17 s, before measured tuning and settling. This example must not be treated
as the installed minimum or final setting.

For phase-delay scanning, estimate both the number of phase offsets and the
reset burden. A phase schedule that appears short at 10 Hz can become
impractical if each accepted pump event requires seconds of HRP recovery or a
fresh cryogenic position.

## 19. Recommended program order

The efficient scientific order is:

1. complete and promote the relevant nonbiological calibration and
   characterization results;
2. validate every reconstruction architecture on a nonbiological surrogate;
3. qualify cells, temperature, blanks, sample/reference balance, and optical
   overlap;
4. prepare and verify room-temperature HRP–CO;
5. acquire its initial slow scan and optimize a reversible pump dose;
6. execute room-temperature HRP non-geminate repeated rapid-scan reconstruction;
7. attempt room-temperature HRP nanosecond stroboscopy only after its IRF/SNR
   gate passes;
8. complete HRP analysis, restoration, and the authorized MbCO handoff;
9. prepare and verify room-temperature MbCO;
10. acquire its initial slow scan and dose/recovery pilot;
11. execute MbCO microsecond stroboscopy, then the supporting single-scan phase
    reconstruction;
12. attempt MbCO nanosecond stroboscopy after the measured identifiability gate;
13. qualify the cryostat, 77 K temperature model, matrix, cell, optical transfer,
    timing, IRF, sensitivity, and reset/fresh-position strategy;
14. acquire separate 77 K slow scans for HRP–CO and MbCO;
15. execute the 77 K fast stroboscopic branches only where equivalent initial
    states can be created;
16. execute one-pump rapid-scan/logarithmic scan-burst recovery for each accepted
    cryogenic sample;
17. complete locked analysis, uncertainty, retention, restoration, and
    thesis-quality procedural writeups.

This order prioritizes the most identifiable thesis results while retaining the
fast mechanistic branches as conditional extensions.

## 20. Data, provenance, and reporting

Each run must preserve:

- condition, sample, preparation, cell, position, temperature, and configuration
  identifiers;
- imported calibration/characterization bundle and validity information;
- programmed and read-back device values;
- complete sample/reference detector streams;
- PicoScope timing/waveform records acquired under their configuration identity;
- pump commands and independently observed optical events;
- MIRcat actual wavenumber/status, scan direction, wavelength triggers, and
  `Tuned/Sweep Active` signals where applicable;
- temperature and environmental records;
- pre-pump, post-pump, control, rejected, diagnostic, excluded, and restoration
  records;
- analysis version, equations, model definitions, uncertainty inputs, and
  parentage from every derived result to native data;
- deviations, aborts, exclusions, and their prospective rule/disposition.

Every campaign phase retains a canonical thesis-quality `procedural_writeup.md`
that explains why the phase was required, how it was actually performed, what
was observed, and which claims and limitations follow. Plans and this document
do not substitute for measured evidence or the completed writeup.

No hash or checksum match is an operational, analysis, acceptance, aggregation,
closeout, or promotion gate. Hashes may be recorded for information, while
stable IDs, paths, sizes, timestamps, versions, device identities, configuration
records, and producer/source records carry operational provenance.

## 21. Claim table

| Proposed claim | Minimum supporting evidence | Required limitation when evidence is absent |
|---|---|---|
| Exact band center at a condition | Accepted initial slow scan, calibrated axis, line-shape/baseline uncertainty, independent repeat | Report only an approximate observed feature or no assignment |
| Pump photolyzes bound CO | Negative bound-band \(\Delta A\), pump-blocked/off-band/cell controls, reversible state, dose response | Describe pump-correlated signal without molecular assignment |
| Resolved geminate lifetime | Optical time zero, narrow/stable IRF, sufficient SNR, convolved identifiability, reset equivalence, independent replication | Prompt component or upper/lower bound only |
| Geminate fraction | Resolved fast and total photolyzed amplitudes, spectral coverage, IRF correction, dose/overlap model, uncertainty | Instrument-resolved fraction only or no quantitative fraction |
| Room-temperature solvent recombination | Complete recovery, concentration/mass-balance or other escape support, artifact controls, appropriate kinetics | Apparent room-temperature recovery component |
| Different conformer/A-state kinetics | Quantified local spectra, comparable sensitivity, global/shared-vs-separate model, correction for overlap and latency | State-dependent amplitudes without rate distinction |
| 77 K intrapocket recovery | Verified cryogenic state/matrix, suppressed-escape rationale, one-pump or equivalent-reset kinetics, temperature uncertainty | Cryogenic recovery without microscopic pathway claim |
| Room-temperature versus 77 K comparison | Independently calibrated conditions, actual temperatures, matrix/cell differences represented, preparation replication | Descriptive comparison only; no isolated temperature effect |
| No damage or accumulation | Dose/cadence ladder, pre/post state spectra, cumulative trend tests, recovery/reset criteria within detection limit | “No damage detected within the stated tests,” never absolute absence |

## 22. Sources and traceability

### 22.1 Primary HRP–CO literature

1. W. Doster, S. F. Bowne, H. Frauenfelder, L. Reinisch, and E. Shyamsunder,
   “Recombination of Carbon Monoxide to Ferrous Horseradish Peroxidase Types A
   and C,” *Journal of Molecular Biology* 194, 299–312 (1987).
   [DOI](https://doi.org/10.1016/0022-2836(87)90377-9) ·
   [PubMed](https://pubmed.ncbi.nlm.nih.gov/3612808/).
2. I. E. Holzbaur, A. M. English, and A. A. Ismail, “Infrared Spectra of
   Carbonyl Horseradish Peroxidase and Its Substrate Complexes:
   Characterization of pH-Dependent Conformers,” *Journal of the American
   Chemical Society* 118, 3354–3359 (1996).
   [DOI](https://doi.org/10.1021/ja953715o).
3. M. L. Smith, P.-I. Ohlsson, and K. G. Paul, “Infrared Spectroscopic Evidence
   of Hydrogen Bonding between Carbon Monoxide and Protein in Carbonylhorseradish
   Peroxidase C,” *FEBS Letters* 163, 303–305 (1983).
   [DOI](https://doi.org/10.1016/0014-5793(83)80840-0).
4. W. J. Ingledew and P. R. Rich, “A Study of the Horseradish Peroxidase
   Catalytic Site by FTIR Spectroscopy,” *Biochemical Society Transactions* 33,
   886–889 (2005). [DOI](https://doi.org/10.1042/BST0330886) ·
   [PubMed](https://pubmed.ncbi.nlm.nih.gov/16042620/).

### 22.2 Primary MbCO and low-temperature literature

5. E. R. Henry, J. H. Sommer, J. Hofrichter, and W. A. Eaton, “Geminate
   Recombination of Carbon Monoxide to Myoglobin,” *Journal of Molecular
   Biology* 166, 443–451 (1983).
   [DOI](https://doi.org/10.1016/S0022-2836(83)80094-1) ·
   [PubMed](https://pubmed.ncbi.nlm.nih.gov/6854651/).
6. M. Schleeger, C. Wagner, M. J. Vellekoop, B. Lendl, and J. Heberle,
   “Time-Resolved Flow-Flash FT-IR Difference Spectroscopy: The Kinetics of CO
   Photodissociation from Myoglobin Revisited,” *Analytical and Bioanalytical
   Chemistry* 394, 1869–1877 (2009).
   [DOI/full text](https://doi.org/10.1007/s00216-009-2871-0).
7. J. B. Johnson et al., “Ligand Binding to Heme Proteins. VI. Interconversion of
   Taxonomic Substates in Carbonmonoxymyoglobin,” *Biophysical Journal* 71,
   1563–1573 (1996).
   [DOI](https://doi.org/10.1016/S0006-3495(96)79359-1) ·
   [Full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC1233623/).
8. M. R. Chance, B. F. Campbell, R. Hoover, and J. M. Friedman, “Myoglobin
   Recombination at Low Temperature. Two Phases Revealed by Fourier Transform
   Infrared Spectroscopy,” *Journal of Biological Chemistry* 262, 6959–6961
   (1987). [PubMed](https://pubmed.ncbi.nlm.nih.gov/3584103/).
9. M. Devereux and M. Meuwly, “Structural Assignment of Spectra by
   Characterization of Conformational Substates in Bound MbCO,” *Biophysical
   Journal* 96, 4363–4375 (2009).
   [DOI](https://doi.org/10.1016/j.bpj.2009.01.064) ·
   [Full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC2711460/).

### 22.3 Time-resolved IR method literature

10. B.-J. Schultz, H. Mohrmann, V. A. Lorenz-Fonfría, and J. Heberle, “Protein
    Dynamics Observed by Tunable Mid-IR Quantum Cascade Lasers across the Time
    Range from 10 ns to 1 s,” *Spectrochimica Acta Part A* 188, 666–674 (2018).
    [DOI](https://doi.org/10.1016/j.saa.2017.01.010) ·
    [PubMed](https://pubmed.ncbi.nlm.nih.gov/28110813/).
11. G. M. Greetham et al., “A 100 kHz Time-Resolved Multiple-Probe Femtosecond
    to Second Infrared Absorption Spectrometer,” *Applied Spectroscopy* 70,
    645–653 (2016). [DOI](https://doi.org/10.1177/0003702816631302) ·
    [Author manuscript](https://strathprints.strath.ac.uk/57815/).

The Greetham instrument obtains a spectrum from each broadband probe using a
multichannel detector. The present MIRcat provides one narrowband probe
wavenumber at a time; it can emulate repeated-delay logic but not the
single-pulse spectral multiplexing. The spectral dimension must therefore come
from calibrated scanning or wavelength-by-wavelength reconstruction.

### 22.4 Device and repository authorities

- [Daylight Solutions MIRcat manual](references/manuals/MIRcat/Daylight%20Solutions%20MIRcat%20Manual.pdf)
  and [installed-system process-trigger correspondence](references/manuals/MIRcat/daylight_db9_process_trigger_correspondence.md).
- [Zurich Instruments HF2LI user manual](https://docs.zhinst.com/hf2_user_manual/index.html)
  and the repository copy under `references/manuals/HF2LI/`.
- Highland Technology T660 manual and programming guide under
  `references/manuals/T660/`.
- Continuum Surelite and Horizon OPO manuals under `references/manuals/YAG/` and
  `references/manuals/SLOPO/`.
- PicoScope 5000D series documentation under `references/manuals/PicoScope/`.
- [Campaign master sequence](campaigns/master_sequence.md),
  [phase registry](campaigns/phase_registry.yaml),
  [time-resolved acquisition modes](campaigns/methods/time_resolved_acquisition_modes.md),
  [HRP requirements](campaigns/hrp_001/requirements.md), and
  [MbCO requirements](campaigns/mbco_cryo_001/requirements.md).

Manufacturer documentation supplies capability and safety bounds. Accepted
installed-system calibration and characterization evidence controls final
experimental settings and uncertainty.
