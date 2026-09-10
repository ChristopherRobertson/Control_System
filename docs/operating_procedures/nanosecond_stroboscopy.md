# Nanosecond stroboscopy

The two top-level tabs are **Nanosecond Stroboscopy** and **Dual-Detector
Nanosecond Stroboscopy**. They use experiment ID `nanosecond_stroboscopy` and
instance IDs `nanosecond_stroboscopy:single` and `nanosecond_stroboscopy:dual`.
They reconstruct equivalent-time local spectra one measured wavenumber at a
time. The MIRcat does not perform a nanosecond spectral sweep.

## Installation and isolation

This package targets the frozen measurement-host API version 1, foundation
commit `7152d66`. That baseline contains the working Phase Scan code and its
recent fixes. Development is in the isolated `codex/nanosecond-stroboscopy`
worktree. The package, its tests, and this procedure are its only integration
changes. Install `software/control_app/measurement_modules/nanosecond_stroboscopy/`
beside the host and restart the application using the repository's normal
`python -m control_app.ui.app` launch from `software/` with its UI dependencies.
Discovery loads `registration.py`; no central registry or other experiment is
required. Import, discovery, and widget construction do not contact hardware.

Each tab owns its settings, blank or Q0, preliminary review, cancellation,
runner, results, and preferences. Preferences use
`measurements/nanosecond_stroboscopy/<mode>/v1/`. The app's top-bar Save Location
is frozen at operation start. Native files go beneath
`<save root>/measurements/nanosecond_stroboscopy/<mode>/<unique run ID>/`.
Changing the location during an operation affects the next operation.

## Guided use

1. Select the condition profile and selected measured wavenumbers. Accepted
   sample spectral selections can be loaded as the host's standalone versioned
   interchange records without installing Slow Scan. Record sample,
   preparation, condition, matrix, cell, day, position, and measured temperature
   identity. These are sample records, not promoted instrument calibration.
2. Inspect the requested/quantized delay schedule, channel/frame schedule,
   response kernel, simulation, event/reset burden, storage estimate, and
   readiness messages. The initial numerical settings are explicitly
   **EXAMPLE ONLY** simulator values. Edit the supported scientific settings
   and advanced overrides or load a saved plan. A condition label supplies no
   established kinetic lifetime, fraction, pulse recipe, or reset cadence.
3. In single mode, physically load the matched blank and acquire or load the
   compatible complete blank record. Then load the sample and acquire the
   unpumped preliminary measurement. In dual mode, sample and matched-buffer
   reference remain in their separate detector paths and the preliminary
   measurement supplies simultaneous Q0; there is no routine separate full
   blank acquisition. Physical sample exchanges and manual controls are
   explicit operator actions, not invented automatic shutters or stages.
4. Review the preliminary spectrum and quality/support information, select the
   explicit review checkbox, then press Start. Changes to scientific settings,
   calibration/sample selections, or relevant instrument state invalidate
   approval with a specific mismatch. Restoring compatibility clears stale
   errors but does not grant approval automatically.
5. At each wavenumber the runner tunes and verifies readiness, settles,
   uploads acknowledged timing fields, completes that wavelength's delay and
   control events with equivalent reset, and only then retunes. Progress
   distinguishes configuration, upload, tuning, reset/recovery, acquisition,
   retrieval, restoration, preservation, and processing. Estimates include
   preparation, controls, resets, tuning, and final work; they are estimates,
   not measurements of precise edges.
6. Inspect the native observable and reconstructed map, local spectra, and
   linked point kinetics. Numeric delay/wavenumber inputs select actual
   slices, and held arrows traverse the available coordinates. Nanosecond
   commands use ns units. Map columns are command bins; independently
   calibrated optical coordinates are retained separately. Missing support
   stays missing. Navigation and image export use the plot toolbar.

Stop targets this tab's operation and requests cooperative cancellation. The
worker retains available native records, attempts every cleanup action, saves
restoration outcomes, and reports normal cancellation as **Acquisition stopped**.
Cleanup or preservation failure takes precedence over a normal stop message.
The host retains an actionable ownership fault when safety or preservation
cannot be verified. Emergency stop is a separate host-wide lifecycle action.
New run clears this tab's baseline, review, and results while preserving entered
settings, other tabs, and all saved files. No biological pump is retried.

## Measurement kernel and the commissioning boundary

The implemented candidate is `sparse_single_probe_demod_impulse`. The T660
places a probe pulse at a selected delay from the pump within a repeated,
explicitly planned reset cycle. It moves the pump's FIRE and Q-switch commands
relative to the probe anchor, keeping their qualified separation. Its finite
frame table contains warmup, selected pump/probe, impulse-tail, and terminal
frames. An event is a planned burst; this is not an undisclosed split of a
continuous full-spectrum acquisition.

If an isolated probe has energy E and sample transmission T(nu,t), the linear
detector/demodulator response is proportional to E*T(nu,t) times its measured
impulse response h. Integrating a qualified phase projection of the complete
HF2LI response, with measured area gain, baseline, and response-tail correction,
retains a spectral estimate proportional to T(nu,t). Changing optical delay
changes the transmission sampled by that probe. The HF2LI measures this
pulse-energy observable over its slower response interval; its timestamp is
not the optical delay or the time resolution. Background probes, phase
projection, finite aperture, filter history, and reset must be qualified for
this estimator. Generic averaging of an unrelated continuous trace does not
implement it.

The maintained wiring has T660-1 A to the HF2LI external reference, B to MIRcat
TRIG IN, C to T660-2 TRIG IN; T660-2 A/B command FIRE/Q-switch. D outputs and
HF2LI DIO1 are disconnected. This module does not assume or enable a connected
acquisition-window gate. It preserves the sample/reference detector tee paths
to HF2LI and PicoScope. The HF2LI is always the spectral recorder; PicoScope
waveforms are timing/IRF diagnostics. Default PicoScope CHB observes the reference
detector, not a pump photodiode. Independent sample-plane optical pump timing
requires its separately documented diagnostic configuration and restoration.

The promoted-bundle registry in the foundation contains **no promoted bundles**.
Connected Start therefore cannot certify the candidate kernel. It reports the
missing qualifications and/or exact unsupported installed-service capability.
In particular commissioning must establish:

- MIRcat acceptance and reproducibility of the selected sparse pulse mode,
  tuned/settled readbacks, and measured probe envelope;
- HF2LI reference lock at the selected cadence, calibrated impulse-area gain
  and phase projection, sufficient acquisition aperture and tail decay,
  channel-specific response, covariance, linearity, and aggregate throughput;
- installed timing routes, shared-clock receiving locks, FIRE/Q-switch and
  optical route offsets, pump/probe counts, sample-path optical time zero,
  jitter and configuration-specific IRF;
- detector tee/receiver loading and skew, calibrated wavenumber selection,
  applicable blank/control and background/path-balance identities;
- measured reset equivalence, dose/event budget, temperature and sample-state
  preservation, including fresh-position identity if used.

A software flag, profile, nominal MIRcat width, 10 ps T660 command increment,
or a successful simulated run cannot establish these qualifications. Connected
access, including capability discovery, uses the host's exclusive instrument
ownership. Ownership spans connection, configuration, acquisition, cleanup,
restoration verification, and required preservation. Simulation is hardware
free and can run while another tab owns the instrument. Development verification
does not operate or commission the instrument.

## Scientific profiles, controls, and forward modeling

`RT-HRP-G` / `ARC-RT-HRP-NS` supports the two sample-fitted CO populations.
`RT-Mb-G` / `ARC-RT-MB-NS` starts with A1; A0/A3 require quantified selection.
`77K-HRP-G-F` / `ARC-77-HRP-NS` and the nanosecond branch of
`77K-Mb-G-F` / `ARC-77-MB-NSUS` retain their own fitted conditions and windows.
Neither the historical approximately 180 ns/4% MbCO result nor a sub-100-ns HRP
response is fixed in the model.

The schedule includes multiple negative delays outside IRF support, dense
early coverage, justified later and bridge delays, and pump-blocked/off-band
controls. Counterbalanced or seeded randomized order exposes drift while
keeping an entire delay series at one wavelength. Control applicability and
record IDs retain dark, optical/electronic artifact, cell/matrix, damage,
pre/post state, and temperature requirements. A pump's maximum repetition
rating is not a reset cadence. Repetitions are technical averages, not
independent preparations. Cryogenic repetition requires demonstrated equivalent
spectral/thermal state or independently identified equivalent fresh positions;
ordinary delay stepping does not reset persistent photoproduct.

The simulator convolves a free exponential recovery plus long-lived component
and baseline with the IRF, jitter, and probe aperture, incorporates filter
history and reset defects, and adds noise/drift. Prospective simulation tests
the selected event budget before a confirmatory plan is accepted. Lifetime
inference profiles a free lifetime while solving the linear amplitudes and
offset. Boundary solutions, weak signal, broad response, poor coverage,
unqualified optical timing, significant carryover, or failed reset yield an
unresolved/bounded outcome. These tests assess information in the schedule;
they do not identify a molecular pathway from a fitted exponential alone.

## Native data and equations

Every event retains identities, condition, technical repetition, position,
wavenumber, requested/quantized delay, observed electrical delay, calibrated
optical delay if available, kernel, reset/pump evidence, detector streams,
timing/readbacks, quality flags, and native device payloads. Failed/rejected
events are retained. Arrays use explicit dtype, shape, and their original bytes;
large integer timestamps and nonfinite values survive round trips. No
hash-matching gate is used. `manifest.json` freezes operation inputs;
`events.jsonl` is flushed per event; named records retain qualifications and
diagnostics; `finish.json` records outcome, restoration, and derived results.
An incomplete journal loads its complete records as interrupted data.
When a journal append fails, the runner attempts a separate
`emergency_native_events.json` rescue record and retains an ownership fault.
Loading exposes that rescue record and any additional event identities; it
does not treat the rescue attempt as verified normal preservation.

For dual detection, Q=S/R and Delta A=-log10(Q/Q0), where Q0 is a compatible
unpumped simultaneous sample/reference record. Raw Q is reference-normalized
signal, not absolute transmission or absorbance. Absolute A=-log10(Q/B)
requires a separately applicable measured background/path-balance B. The
unpumped sample Q0 is never substituted for B. Single-mode absolute A uses the
compatible sequential blank; its Delta A uses the unpumped sample baseline.

Detector alignment uses explicit corrected timestamps and a declared tolerance
with unique one-to-one matches. It never assumes equal array indices, fills a
gap, or extrapolates a reference. For ratio estimates,

    Var(Q) = Q^2 [ Var(S)/S^2 + Var(R)/R^2 - 2 Cov(S,R)/(S R) ]
    Var(Delta A) = [ Var(Q)/Q^2 + Var(Q0)/Q0^2 ] / ln(10)^2

The baseline term remains common when technical repetitions are combined and
does not average down as independent shot noise. Unknown uncertainty remains
unknown. Nonpositive/unsupported references, clipping, unlock, count/trigger
errors, reset failure, and unresolved optical coordinates do not become valid
kinetic points. Local band integration requires complete measured spectral
support; quantitative area uncertainty additionally needs band covariance.

## Verification

Run from the isolated worktree with its `software/` on `PYTHONPATH` and Qt's
offscreen platform when headless:

```powershell
$env:PYTHONPATH = "$PWD/software"
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest software/tests/measurement_modules/nanosecond_stroboscopy -q
python -m pytest software/tests/test_measurement_host_contract.py software/tests/test_measurement_host_contract_interchange.py software/tests/test_measurement_host_integration.py software/tests/test_measurement_host_presentation.py -q
```

Tests cover deterministic timing/schedules, synthetic recovery and honest
non-identifiability, two-tab discovery and independent sessions, full guided
simulation, native round trips and compatibility, covariance/alignment/gaps,
invalid references and device-quality flags, cancellation and preservation,
exclusive ownership and cleanup-failure precedence using injected devices.
Development verification completed with **80 module tests and 28 unchanged host
compatibility/presentation tests passing (108 total)**. The broad regression run
reported **827 passed, 9 skipped, and 24 passing subtests**, with the one legacy
fixed-tab-count failure described below. Both guided simulator workflows and the
dual-result layout were also rendered without hardware access.
The host compatibility tests exercise the unchanged frozen boundary. Live
commissioning remains explicitly outstanding; no promoted calibration,
campaign status, hardware action, or phase acceptance follows from these tests.

The foundation's existing `test_gui_layout_smoke.py` still asserts exactly seven
tabs. Installing this package correctly produces nine, so that one legacy
assertion fails in an unrestricted full-suite run. It is intentionally left
unchanged under this task's file-ownership boundary. The module's
`test_ns_app_shell.py` verifies real-shell discovery of both new tabs and
preservation of both existing Phase Scan tabs. The foundation owner can replace
the fixed total with discovery-aware title/identity assertions; no host API
change is required.

Scientific requirements are [EXPERIMENTS.md](../../EXPERIMENTS.md), particularly
sections 8.1, 9.2, 10.2, 11, 12.1, 13.1, and 14–18. Installed topology and device
roles follow [default wiring](../../instrument/default_wiring_state.md),
the maintained hardware configuration and wiring map, and manufacturer manuals
under `references/manuals/`. Operating values require applicable promoted
instrument evidence and retained readbacks.
