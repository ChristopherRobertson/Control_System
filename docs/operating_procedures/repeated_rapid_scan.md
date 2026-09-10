# Repeated Rapid-Scan Phase Delay

This procedure covers **Repeated Rapid-Scan Phase Delay** and **Dual-Detector
Repeated Rapid-Scan Phase Delay**, the two top-level tabs registered by
`repeated_rapid_scan`. Their instance IDs are `repeated_rapid_scan:single` and
`repeated_rapid_scan:dual`. Each has its own settings, sample records, blanks,
preliminary review, cancellation, results and mutable runner. Protein and
temperature are condition profiles within these tabs.

The method implements RT-HRP-NG / ARC-RT-HRP-RRS: many consecutive spectral scans
after one rare pump event at each selected phase. It does not call the working
Single Scan Phase-Delay scientific runner. Its scientific requirements come from
[EXPERIMENTS.md §8.3, §9.3 and §§14–18](../../EXPERIMENTS.md). Numerical examples in
that document and the built-in settings are planning examples, not installed
operating values or evidence that commissioning has finished.

## Installation and host boundary

The module uses [measurement-host API version 1](../../software/control_app/measurement_host/README.md).
The task baseline was `7152d660a728a9b3c8bd9d2ebf8896d4623af60a`, “Build versioned
measurement host and coordinated hardware lifecycle.” This is an informational
source reference, never a required matching value. Work was performed in the
isolated `Control_System_repeated_rapid_scan` checkout. The existing working
single/dual Phase Scan packages and the shared host interface remain separate.

Install the complete
[`software/control_app/measurement_modules/repeated_rapid_scan/`](../../software/control_app/measurement_modules/repeated_rapid_scan/)
directory alongside the completed host and restart the normal application.
`registration.py` exports one `DESCRIPTOR`; the host discovers both tabs without
central registry or main-window edits. No other experimental package is needed.
Registration, typed planning and widget construction do not enumerate or open
devices. The established application environment supplies Qt, NumPy and the host
device services; this module adds no global dependency changes.

Hardware operations, including **Check instruments**, acquire the
host's exclusive instrument ownership. They use fresh devices through the frozen
operation context and hold ownership through restoration and preservation. A
sibling tab or manual hardware control cannot take the instrument during that
operation. Normal **Abort acquisition** targets this tab's operation. The
host-wide emergency stop is a separate lifecycle action.

## Routine operation

1. Set the application's top-bar **Save Location**. The chosen root is frozen at
   operation start; changing the top bar affects subsequent operations. Runs use
   unique host run IDs under `measurements/repeated_rapid_scan/<mode>/`. Preferences live only
   under `measurements/repeated_rapid_scan/<mode>/v1/`.
2. Select the condition and enter sample, independent preparation, cell,
   illuminated position and temperature identities. Record accepted state
   verification, temperature evidence and relevant concentration/free-CO,
   mass-balance and artifact-control metadata. A requested temperature without a
   measured record is explicitly an unverified condition claim.
3. Use **Sample selection…** for a compatible versioned sample
   selection. This loads data through the host interchange interface without
   importing the Slow Scan package. The sample and condition identities must
   agree. Include both target population bands and measured off-band support.
4. For installed operation, use **Promoted bundle…**, then
   **Check instruments**. The bundle supplies applicable instrument
   settings; connected readbacks supply actual values and capabilities. Resolve
   the readiness messages before installed acquisition. Loading an accepted
   sample selection does not promote instrument calibration.
5. Inspect the scrollable settings, complete phase/movie table and derived
   summary. **Save Plan** and **Load Plan** retain the method/mode/schema and
   editable scientific settings. Requested, selected and actual values remain
   separate. Unsupported frame counts, unrequested quantization, unsupported
   rates and inadequate memory/storage are rejected without silently changing
   the declared movie.
6. In **single-detector mode**, load or acquire the complete compatible
   sequential blank. Its unpumped scan schedule covers the selected phases,
   directions and controls. Load the sample and acquire the sample preliminary,
   or load a compatible complete preliminary. In **dual-detector mode**, load the
   sample and matched-buffer reference together and acquire their simultaneous
   unpumped preliminary. There is no routine separate full blank acquisition in
   the dual tab.
7. Confirm that the indicated physical preparation is complete. Review the
   preliminary plots and support, then explicitly approve that preliminary using
   the host review action. Press **Start recovery movies**. Configuration,
   acknowledged timing-table upload, tuning/settling, qualification, acquisition,
   retrieval, restoration, saving and analysis report their actual stage.
8. Respond to physical-action prompts when a control requires pump blocking,
   restoring the sample pump path, a detector-dark condition or sample/blank
   exchange. These are operator actions. The installed topology provides no
   automatic shutter, cell exchange, temperature controller or positioning stage
   for this experiment.
9. Inspect individual movies, native support, reconstructed maps, band kinetics,
   and phase/direction consistency. Use numeric coordinates and the actual
   available slices; missing support remains missing. Plot view/image actions
   use the toolbar. **Load Run** reopens preserved native and derived records;
   export provides a separate derived table rather than replacing native data.
10. **New run** clears this tab's blank, preliminary review and results while
    preserving entered settings and all saved files. It does not clear the other
    tab. Settings, condition, calibration, selected blank or relevant instrument
    changes invalidate incompatible review and explain the mismatch. Restoring
    compatibility clears the mismatch message but never silently grants review.

The default execution choice is **Simulation — synthetic records**. This path
uses explicit simulated devices and cannot fall back to installed hardware.
Selecting **Installed instruments** does not itself resolve commissioning items.

## Finite movie schedule and reset

For a sample movie, the workflow first acquires and accepts an immediate
unpumped qualification scan train. This is explicitly additional to the declared
movie. It then uploads and arms one complete finite movie containing the selected
pre-pump scans, the pump-crossing scan and every post-pump scan. It checks the
movie's own pre-pump region retrospectively as well. A failure there invalidates
the movie and prevents the next equivalent pump.

The separate qualification is necessary because the installed finite T660 frame
table cannot pause mid-table for a software stationarity decision without an
additional qualified hardware gate. No such gate is invented here. All edges
inside the declared movie are determined by the preloaded table; polling and
host waits only drain buffers or wait for status.

The [module timing contract](../../software/control_app/measurement_modules/repeated_rapid_scan/recipes/timing_contract.json)
assigns T660-1 A/B/C to the reference, probe and frame-input clock, with D disabled.
T660-2 A is Fire, B is Q-switch, C is the negative MIRcat process trigger and D is
disabled. There is one scan opportunity per scan frame. An additional final
`terminal_inhibit` frame disables A/B/C/D and has no scan index or spectral
trigger. The physical frame count includes it; the expected spectral scan count
does not. Fire and Q-switch each appear
exactly once for an authorized electrical pump; Fire may be in the preceding
scan frame when the selected phase requires it. They never repeat in every scan.
The negative process-trigger inactive level is high.

| Record kind | Fire/Q-switch commands | Expected sample optical exposure |
| --- | ---: | --- |
| Sample recovery movie | One each | One independently observed event when qualified optical observation is available |
| Phase-matched pump-blocked control | One each | Zero; operator confirms the beam is blocked |
| Probe-only control | Zero | Zero |
| Detector-dark control | Zero | Zero; operator establishes the dark condition |
| Blank/preliminary/qualification | Zero | Zero |

Electrical command counts and independent electrical sync observations are kept
separate from optical arrival evidence. The current installed sync source can
provide an electrical timing basis; it does not establish optical arrival at the
sample. An unexplained missing or extra observed electrical event rejects the
movie and does not cause an automatic pump retry.

The compiler uses the installed T660's 10 ps edge grid, 0.02 Hz DDS frequency
grid, integer external predivider and finite 8192-frame capacity. Each declared
movie plus its terminal must fit completely. Each qualification train has its
own terminal. For the example of five pre-pump scans, one crossing and 100
post-pump scans, the plan contains 106 spectral scans and 107 physical frames;
at the example 0.1 s period its full duration is 10.7 s. The terminal interval is
an output-inhibition allowance, not an extra biological recovery scan. The maintained
`T660Service.preload_frame_table` performs pending-field changes followed by
acknowledged frame storage, progress and cancellation checks. No circular buffer
is recycled, scan is silently slowed, pump-crossing scan is dropped or declared
uninterrupted movie is split to fit memory.

Stationarity and reset use measured population-band contrasts and off-band
baseline support. The implementation removes a line fitted to the measured
off-band log signal, then integrates each band as a relative population proxy.
It also integrates the native normalized off-band signal. Each selected band
must return within its relative tolerance and each off-band observable within
its absolute tolerance for the required final consecutive scans. Directions are
assessed separately. Missing, nonmonotonic, clipped, unlocked or invalid
reference support cannot satisfy these criteria.

The minimum recovery duration is checked against measured movie times. At the
finite duration limit, failure to demonstrate reset produces
`incomplete_recovery`, preserves the movie and inhibits the next equivalent
pump. A maximum reset-wait allowance in the plan is an estimate budget; it is not
permission to pump again after a timer expires. The current workflow does not
extend a declared movie or retry the biological event automatically. Sample
cadence is determined by accepted recovery evidence, never by the pump source's
10 Hz maximum or a literature lifetime.

Memory estimates cover the full native movie and the complete retained run,
including native chunks, reconstructed arrays, the full single-detector blank,
directional preliminary and qualification records. Wall-time estimates also
include these recordings, upload acknowledgments, preparation, tuning/settling,
reset allowance, restoration, storage and analysis. A dual recording increases
data throughput but does not double a simultaneous movie's duration.

## Coordinates, normalization and analysis

Native timestamps are retained in their original integer or floating dtype. A
documented clock correction uses

\[
t_{aligned}=(timestamp_{native}-origin)\,unit\,scale+offset-latency.
\]

Integer origins are subtracted before conversion to floating seconds, so large
native ticks do not erase fine timing. For each sample observation,

\[
t_{reaction,i}=t_{aligned,sample,i}-t_{aligned,observed\ pump}.
\]

The trajectory for that particular scan provides
\(\tilde\nu_i=\tilde\nu_{scan}(t_{aligned,sample,i})\). Calibrated marker times and
axis values define interpolation *within supported trajectory intervals*;
extrapolation is invalid, and configured excessive marker gaps remain invalid.
The method does not invent detector observations across acquisition gaps.
Requested phase, scan index, programmed opportunity time, measured sample time
and wavelength are different fields. Jitter, gaps and pump-crossing data survive
reconstruction. Forward/reverse records stay separate unless equivalence is
demonstrated outside this default analysis.

The relationships \(T\approx\Delta\tilde\nu/v\),
\(N_\phi\approx\lceil T/\Delta\phi\rceil\),
\(\phi+nT+\text{trajectory time}\) and
\(\Delta\tilde\nu_{filter}\sim v\tau\) appear only in planning summaries. They do
not replace acquired timestamps or a measured scan/filter response. An observed
electrical sync basis is labeled explicitly until applicable optical time-zero
and IRF evidence supports an optical-arrival basis. An applicable promoted
electrical-to-optical time-zero correction is labeled
`calibrated_optical_time_zero`. It shifts the measured electrical event using a
documented correction while retaining that native electrical evidence; it is
not an independent optical observation of every pump event.

In dual mode, sample and reference are aligned by their native clocks using
bounded, one-to-one matched support. The primary ratio and transient are

\[
Q=S/R,\qquad \Delta A=-\log_{10}(Q/Q_0).
\]

Here \(Q_0\) is the compatible accepted unpumped sample/reference ratio. Bad or
missing references are excluded while their original values remain retained.
Sample/reference covariance is preserved when supplied and propagated with

\[
\mathrm{Var}(Q)=\mathrm{Var}(S)/R^2+S^2\mathrm{Var}(R)/R^4
-2S\mathrm{Cov}(S,R)/R^3.
\]

When covariance or detector variances were not measured, propagated detector
uncertainty remains unknown rather than silently assuming independence. Absolute absorbance requires an
applicable measured background/path-balance factor,
\(A=-\log_{10}(Q/B)\). Without \(B\), the application labels ratio and transient
observables rather than presenting raw \(S/R\) as absolute transmission or
absorbance. Single-mode transient normalization uses the accepted unpumped
sample baseline and its complete compatible sequential background record.

A dual-mode promoted bundle can optionally name `background_file`, a relative
directory within that bundle containing a versioned `SpectralBaseline` native
record (`run.json` and `native.npz`). It must identify this condition and detector
mode, have kind `background`, and be complete and accepted. Loading that bundle
selects the measured B record, preserves its source/identity, and invalidates an
older review. The runner retains the actual B alongside its derived absolute
absorbance. If no applicable B is selected, the absolute display is unavailable.

Band-area points retain their earliest and latest native sample times, valid
coverage and direction. Their plotted midpoint is an inspection coordinate,
not an assertion that a scan was instantaneous. Fits operate on valid native
\((\tilde\nu,t)\) points, not unsupported reconstructed map pixels.

The optional offline **Load measured fit model…** / **Fit selected movie** actions use
an explicitly identified acquisition kernel and a supplied spectral model. The
single apparent-recovery model is evaluated as native quadrature,

\[
\Delta A_i=c+a\sum_j w_j\,f(\tilde\nu_i+\delta\tilde\nu_{ij})
\,H(t_i-d_j)\exp[-(t_i-d_j)/\tau].
\]

The fit profiles positive lifetime values, solves amplitude/offset at each
lifetime, and reports residuals, parameter covariance, a conditional profile
interval and identifiability warnings. The wavelength offsets are evaluated from
each scan's native calibrated trajectory over the kernel's history. Unsupported
history through flyback or gaps is excluded without extrapolation. Directions
are fitted separately. A constant spectral template is appropriate only for an
explicitly justified flat/local signal; full spectral fitting requires the
supplied template. Missing detector uncertainty uses a labeled residual-based
homoscedastic model. Intervals are conditional on the spectral model, time zero
and kernel and do not include every systematic uncertainty. This model is linear
in delta absorbance: it is a small-signal response approximation, which must be
justified for the measured transient.

The fit-model JSON requires the following structure. Replace every
`USER_INPUT_REQUIRED` value and every numerical example with the measured kernel,
accepted template and prespecified fit interval before applying it:

```json
{
  "kernel": {
    "measured": true,
    "calibration_id": "USER_INPUT_REQUIRED",
    "response_basis": "electrical_sync",
    "delays_s": [0.0, 0.001],
    "weights": [0.5, 0.5]
  },
  "spectral_template": {
    "record_id": "USER_INPUT_REQUIRED",
    "description": "USER_INPUT_REQUIRED: justify this spectral template",
    "wavenumbers_cm1": [1898.0, 1905.0, 1944.0, 1951.0],
    "values": [0.0, 1.0, 1.0, 0.0],
    "excluded_intervals_cm1": []
  },
  "tau_bounds_s": [0.001, 10.0],
  "grid_size": 500
}
```

These numbers are **EXAMPLE ONLY** syntax, not an IRF or accepted spectral model.
The response basis must match the pump basis (`electrical_sync`,
`calibrated_optical_time_zero`, or `optical_arrival`); template wavenumbers must
increase strictly. Loading an
analysis model neither promotes its source record nor changes hardware readiness.

A seconds-long component or biexponential does not establish solvent
recombination. Interpret the fit as apparent recovery until free-CO/concentration
or mass-balance analysis and artifact controls support a mechanism. Pump pickup,
detector/filter recovery, drift, heating, cell/solvent response and illuminated
volume exchange remain alternatives that require evidence.

## Promoted records and remaining readiness

The authoritative [promoted bundle registry](../../instrument/promoted_bundles/registry.yaml)
controls installed calibration loading. The host validates registry and manifest
promotion status. The module's
[bundle section contract](../../software/control_app/measurement_modules/repeated_rapid_scan/recipes/README.md)
uses `repeated_rapid_scan.calibration` and
`repeated_rapid_scan.device_configuration`. Calibration fields identify
trajectory, electrical timing, measured native response, detector linearity,
installed topology, condition and reset equivalence. `applicable_settings`
records the supported spectral window, scan period/speed, probe, Fire/Q-switch,
process pulse and independently selected detector/filter/rate settings.
`operating_values` contains explicit supported operating selections.

Connected readbacks are a separate capability record: actual detector/timing
rates, measured scan period, available demodulators, aggregate throughput,
finite-frame capacity, topology qualification and full-memory recording
qualification. The HF2LI is always the primary spectral recorder. PicoScope
receivers remain in the maintained tee topology and may support separately
qualified timing/IRF diagnostics; they do not replace spectral acquisition.
The maintained wiring does not provide a general-purpose gate on HF2LI DIO1,
T660 D output, MIRcat reserved control pin or inactive Arduino MUX.

| Commissioning evidence | Status until an applicable accepted record is loaded |
| --- | --- |
| Probe/scan/filter choice and full native reconstruction on a nonbiological transient | USER_INPUT_REQUIRED |
| Installed frame/process timing, aggregate throughput and complete finite-memory recording | USER_INPUT_REQUIRED |
| Calibrated trajectory/markers, direction polarity and clock/latency corrections | USER_INPUT_REQUIRED |
| Sample/reference detector linearity, covariance and tee/receiver transfer | USER_INPUT_REQUIRED |
| Equivalent-state recovery criteria for this preparation/condition and cumulative dose | USER_INPUT_REQUIRED |
| Independent sample optical arrival and measured IRF | USER_INPUT_REQUIRED; otherwise electrical-sync timing only |
| Temperature measurement and accepted envelope | USER_INPUT_REQUIRED for a quantitative temperature claim |
| Dark, pump-blocked, probe-only, matrix/cell and other applicable artifact controls | USER_INPUT_REQUIRED |

The development verification below does not complete these physical
commissioning items. It neither changes campaign phase status nor promotes a
bundle. Phase evidence and accepted procedural writeups remain in their
canonical campaign packages under the repository's existing phase-record
contract.

## Preservation, abort and verification

Each saved run has a versioned `run.json` manifest and `native.npz` native arrays.
The manifest records stable IDs, paths, timestamps, array shapes/dtypes/byte
sizes, operation settings, selected records, readbacks and analysis provenance.
There is no hash-matching operational gate. Existing run files are not
overwritten. Partial files from a failed write remain available for diagnosis.

Accepted, rejected, interrupted, clipped, unlocked, missing-trigger, incomplete
recovery, control and restoration records remain preserved. Abort stops further
work, inhibits outputs and retrieves surviving native data before cleanup and
saving. A normal stop reports **Acquisition stopped**. Restoration or storage
failure takes precedence over a normal cancellation message and keeps the
host's ownership outcome truthful. Previous active emission is not resumed
merely to restore a pre-run control value.

If storage fails, the tab keeps its in-memory native record and blocks **New
run** and app close until it is saved. Choose an available top-bar Save Location
and use **Save retained records** to write a separate recovery record containing
the original failure and source identities. This action never reacquires data
or repeats a pump. A physical ownership fault still requires the host's explicit
instrument recovery procedure after preservation succeeds.

Offline verification is provided in
[`software/tests/measurement_modules/repeated_rapid_scan/`](../../software/tests/measurement_modules/repeated_rapid_scan/)
and uses the host's compatibility tests. It covers typed settings/plan
compatibility, deterministic finite one-pump schedules, hardware quantization,
whole-movie and full-run memory, dual simultaneous duration, native timing and
detector normalization, known changing-within-scan transients, gaps and quality
exclusions, reset failure, cancellation, storage failure, cleanup precedence,
two-tab discovery/isolation and injected installed-device paths. The planner
suite specifically passed 21 tests during implementation; the task completion
report records the final combined suite results.

Run verification from the task checkout with the repository environment and
`software` on `PYTHONPATH`, for example:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'software'
python -m pytest software/tests/measurement_modules/repeated_rapid_scan -q
python -m pytest software/tests/test_measurement_host_contract.py -q
```

No physical hardware was operated during this development task. The maintained
[wiring state](../../instrument/default_wiring_state.md),
[wiring map](../../instrument/wiring_map.yaml),
[MIRcat manufacturer correspondence](../../references/manuals/MIRcat/daylight_db9_process_trigger_correspondence.md),
[T660 manual](../../references/manuals/T660/Highland%20Technologies%20T660%20Manual.pdf)
and [T660 programming guide](../../references/manuals/T660/Highland%20Technologies%20T660%20Programming%20Guide.pdf)
are the local primary hardware references. The existing
[single Phase Scan](phase_scan_tab.md) and
[dual Phase Scan](dual_detector_phase_scan_tab.md) procedures are behavioral
references, not sources of transferable operating values for this architecture.
