# Phase Scan tab

For simultaneous sample/reference detection, use the separate
[DD Phase Scan tab](dual_detector_phase_scan_tab.md). The workflow
below and saved single-detector runs retain their existing meaning.

Use **Phase Scan** for the regular single-detector swept-wavenumber phase
experiment. The app provides a complete matching buffer-blank sequence,
preliminary unpumped sample review, explicit pumped acquisition, and quantitative
reconstruction. The 48-scan diagnostics and fixed-wavenumber fast measurements
are separate experiments and are not actions in this tab.

Use **HF2LI CH1 SIG IN +** for both buffer and sample. Keep the detector, cell
geometry, optical alignment and any diagnostic tee loading consistent between
them. Configuration checks cannot detect a physical optical-path change. See
[default wiring](../../instrument/default_wiring_state.md) for the fixed wiring.
The fixed probe recipe uses 2 MHz external triggering with 150 ns TTL pulses;
MIRcat internal acceptance settings are 2.1 MHz and 142 ns. These settings are
displayed for reference and are not normal editable experiment controls.

## App-only acquisition

1. Open **Phase Scan** and choose the save location through the app. Override
   dropdowns are available immediately from saved device choices (or the
   retained experiment settings on first use). The tab automatically checks
   connected HF2LI settings and installed MIRcat tuning ranges, then restores
   settings. You can continue editing while this check runs. It does not enable
   laser emission or acquire an optical measurement. Acquisition waits for a
   successful check; **Check connected device** retries a failed check or checks
   a newly connected device. No refresh action is needed to view the choices.
2. Set the pump rate, start/stop wavenumber, scan speed and phase-delay spacing.
   The defaults are **10 Hz, 2000 → 1900 cm⁻¹, 10,000 cm⁻¹/s and 50 µs**.
   Inspect the derived scan count, duration, timing coverage, automatic HF2LI
   settings and estimated resolution. Resolve any reported conflict before
   proceeding. **Save plan…** records the preview without starting hardware.
   **Load plan…** restores editable settings and overrides, recalculating the
   experiment using current device capabilities.
3. Load the buffer blank and select **1 · Acquire buffer blank sequence**.
   Confirm the app's probe acquisition action. Every pump output is inhibited.
   The blank has the same complete signed scan schedule, cadence, trajectory,
   probe and detector configuration as the upcoming sample sequence. Alternatively,
   use **Select saved buffer blank…** to select a compatible completed run.
   A newly acquired blank keeps the instrument connections and exclusive ownership
   for the preliminary and pumped stages. The T660-1 A reference remains running,
   HF2LI acquisition settings stay applied, and MIRcat remains armed with emission
   off. Probe and scan/pump triggers are inhibited while you exchange the sample.
   Settings, blank selection and capability discovery are locked until you end
   the experiment. Loading a saved blank starts a new session; it cannot preserve
   continuity with the earlier blank's reference or settling history.
4. Load the sample and select **2 · Acquire preliminary sample (pump OFF)**.
   Review the **Preliminary spectral review** view and select **I reviewed the
   preliminary unpumped spectrum**. This is one unpumped sample scan matched to
   blank sequence position zero; it remains a separate saved acquisition.
5. Select **3 · Start pumped phase scan** and explicitly confirm the pumped
   acquisition. Reviewing the preliminary spectrum does not itself enable the
   pump. The continuous sample sequence first captures its own unpumped baseline,
   then all signed phase steps. Resolved HF2LI settings and effective instrument
   readbacks must still match the blank before acquisition starts.
   Each subsequent stage verifies the retained configuration and reference without
   reconnecting or reapplying the HF2LI preset. A changed configuration or lost
   reference fails the operation and triggers cleanup rather than silently retuning.
6. Inspect **Reconstructed phase-scan data**. Select absolute absorbance or its
   change from the unpumped sample baseline; rotate, zoom, use the toolbar Home icon, and
   inspect linked spectral/time slices and cursor values. Use **Export quantitative
   data…** or the toolbar Save icon as needed. The arrow-shaped **Mouse selection**
   toolbar action exits pan/zoom. Sliders are labeled by the coordinate they change:
   **Time** selects the spectrum; **Wavenumber** selects the time trace.
   Enter a time in ms or a wavenumber in cm⁻¹ beside its slider and press Enter
   to select the nearest reconstructed coordinate. The field updates to the
   actual selected coordinate; missing data stay missing and no interpolation
   is added. Sliders and mouse selection update the numeric fields too.
   **Load phase-scan run…** also opens
   existing reconstructions without accessing hardware.

**Abort acquisition** stops timing and emission, retains available native data,
and attempts every restoration and safe-idle action. Wait for the completion or
failure message. An abort, partial acquisition, integrity failure or unverified
restoration does not become a compatible blank or a completed quantitative run.
There are no automatic optical retries.

Between stages, **End experiment** restores the original settings and closes the
connections in a background worker. **New run** first performs the same cleanup.
Completion of the pumped sequence, an acquisition fault, or application shutdown
also ends the session. Full restoration is deferred until one of these boundaries;
completion of the blank or preliminary scan alone does not restore settings or
disconnect the instruments.

**Sequence duration** covers the hardware scan sequence. Before it starts, the
app programs every timing-table entry and prepares the instruments; large tables
can take several minutes to load. The status line reports timing-table progress,
instrument preparation, scanning, retrieval and saving separately. For example,
1,402 scans at 10 Hz require about 2 minutes 20 seconds of scanning, in addition
to preparation and final processing. A stopped run can contain partial native
measurements even when its completed scan count is zero.

## Parameters and combination limits

The editable pump rate is positive and no greater than 10 Hz. Its period must
be exactly representable by the T660's integer predivider of the 2 MHz source
clock; 10, 5, 2 and 1 Hz are examples. The app rejects an unrepresentable cadence
instead of rounding it. Start and stop are each limited to 1650–2050 cm⁻¹, must
differ, and must fit inside one installed MIRcat QCL's tuning range for an
uninterrupted sweep. Equal bounds belong to the future fixed-wavenumber workflow.

Scan speed accepts requests from 1 to 10,000 cm⁻¹/s. The connected MIRcat speed
readback must support the requested value; a numerical entry alone is not a
claim of hardware support. Phase-delay spacing accepts 1–1000 µs. The app checks
the complete signed schedule and capture/return margin against the chosen
cadence, timing-table capacity and available acquisition memory. An otherwise valid
speed or spacing can fail in combination with a large range or fast cadence.
An unsupported run is not silently slowed, divided into blocks or otherwise
changed.

**Reconstruct before pump** and **Reconstruct after pump** set the reconstruction
window relative to electrical pump sync (defaults: 1 ms before and 5 ms after).
There are no independently editable acquisition-time controls. The planner
derives sweep-start delays, scan count and capacity from this window, the full
nominal sweep duration and phase spacing. For sweep duration T, before/after
durations B/A and spacing d, start delays run from floor((-T-B)/d)×d to ceil(A/d)×d.
The reconstructed interval remains [-B, A]; measured marker support determines
valid cells and missing measurements are not extrapolated. Invalid combinations
disable acquisition with a brief setting-specific solution. Window changes
persist and invalidate blanks when they change the requested sequence.

At the defaults, one sequence contains **322 scans: one unpumped baseline plus
321 pumped phases** from −11 to +5 ms in 50 µs steps. At 10 Hz, this is about
32.2 seconds per blank or sample sequence, plus setup, settling and final data
retrieval. Nominal sweep duration is 10 ms. The engineering capture envelope is
20.28 ms, including trigger margins; it is not a calibrated trajectory.
Measured controller markers determine reconstructed wavelength coordinates and
whether particular time/wavelength cells have support.

The resolved pair includes cadence, scan count, signed phase range, sweep
settings, probe configuration, HF2LI selected settings and actual readbacks.
Changing any relevant field identifies a specific blank-compatibility conflict
and requires another matching blank and preliminary review. Selecting a different
saved blank also clears the previous preliminary review. A fresh capability
discovery timestamp alone is not a reason to reject unchanged settings.

## HF2LI automatic selection and manual overrides

The automatic selector uses values accepted and read back from the connected
HF2LI with CH1 detector and DIO timing streams enabled (API demodulators 0 and 2).
Other enabled demodulator streams affect rate capacity. Unsupported nominal
sample rates do not appear as valid manual choices. The retained profile is
identified as a preview until the automatic connected-device check succeeds.
Previously checked dropdown choices persist between app sessions, without
restoring acquisition permission or treating a disconnected device as verified.

Selection considers the requested phase increment and a 1 cm⁻¹ spectral target,
with a temporal target equal to the smaller of phase spacing and
`1 cm⁻¹ / scan speed`. The response estimate combines the cascaded RC filter's
10–90% step rise, two detector sample intervals and two DIO sample intervals in
quadrature. Spectral broadening is scan speed multiplied by filter rise time;
group delay is reported separately. These are engineering response estimates,
not a measurement of the optical impulse response. A fine phase grid or the
highest sample rate does not establish equivalent temporal resolution. If the
best supported configuration cannot meet the target, the displayed warning
states the estimated effective resolution; the requested experiment is retained.

Expand **Advanced HF2LI overrides** to select supported filter order, time
constant and CH1 sample rate from dropdowns. Time-constant choices depend on
an explicitly selected order. With order set to **Automatic**, constants for all
supported orders remain available. Valid combinations also depend on filter
bandwidth and enabled-stream rates. An invalid combination keeps all correction
controls available and explains which settings conflict, the required change,
and supported alternatives. An unavailable previous selection stays visibly
marked; choose another value or **Automatic** without losing the other choices.
**Restore automatic settings** clears overrides. The app displays the automatically or manually selected
settings and the actual post-configuration readbacks, and records requested,
selected and actual settings in the saved acquisition.

Supported hardware behavior is grounded in the
[HF2 specifications](https://docs.zhinst.com/hf2_user_manual/specifications.html),
[filter response documentation](https://docs.zhinst.com/hf2_user_manual/signal_processing_basics.html)
and [node documentation](https://docs.zhinst.com/hf2_user_manual/nodedoc.html),
plus device discovery/readbacks. MIRcat tuning and sweep capabilities use the
installed [SDK interface](../../references/sdk/MIRcat/include/MIRcatSDK.h) and
readbacks. These sources do not establish a universal list of nominal rates
accepted by every connected configuration.

## Timing, reconstruction and retained files

The regular execution path uses **250 µs FIRE → Q-switch**. Signed delays preserve
the tested Process Trigger schedule even when the matching blank inhibits FIRE
and Q-switch. DIO17 records electrical pump sync, DIO21 records Sweep Active,
and the identified controller-marker channel supplies wavelength anchors. A
commanded phase delay is not substituted for an observed pump timestamp.

Each complete blank/sample sequence uses one timing table and one uninterrupted
MIRcat emission interval. LabOne retains results on the host through the sequence;
normal data retrieval occurs after completion. Memory and timing capacity are
preflighted. There are no artificial 16-scan partitions or intervening MIRcat
emission restarts. Host allocation does not guarantee internal LabOne memory:
count, continuity, loss and clipping checks still determine whether acquisition
completed successfully. Partial native data remain saved if those checks fail.

For each sample scan `i`, the app interpolates blank scan `i` only between
adjacent supported measured wavelengths, then calculates:

`Transmission = CH1 sample / matched CH1 buffer blank`

`Absorbance = −log10(Transmission)`

The continuous sample run's position-zero unpumped baseline remains separate.
The change view subtracts that baseline's absorbance from absolute absorbance at
each supported wavelength. The earlier preliminary scan is retained for review
and provenance and does not replace that baseline. Nonpositive detector values,
unobserved wavelengths, invalid intervals and unsupported time regions remain
missing. No smoothing, fitted flattening, normalization, extrapolation or
filter-delay correction is applied to the quantitative values. Linked slices
show the stored grid; the full measured native records remain available.

Run folders under **Phase Scan / date / acquisition ID** contain `run.json`,
one lossless `raw/acquisition.npz`, `scan_index.jsonl`, settings/readbacks,
restoration/cleanup records and `result.json`. Completed sample runs also contain
`processed/reconstruction.npz` and `processed/reconstruction.csv`, including
absolute absorbance, delta absorbance and the unpumped baseline. Existing files
are not overwritten. Saved current blanks are checked against their frozen
configuration; supported full-sequence records can be imported only when actual
cadence, complete signed frame schedule, probe/HF2LI readbacks and safe shutdown
are reconstructable from their saved records. Incomplete or unmatched records
are rejected with the missing or conflicting evidence identified. No hash
matching is required to load data or accept a compatible blank.

Retained sessions also record `experiment_session.json` after each intermediate
stage and `experiment_session_resume.json` when continuing. These retain the
session ID and interstage readbacks. Intermediate results explicitly report that
full shutdown/restoration has not yet occurred. On final cleanup,
`experiment_session_close.json` links each stage to the final restoration record.
A saved blank from such a session can be selected in a later experiment only
after successful final cleanup is recorded; the current session uses its own
verified blank directly. Existing stage result records are not rewritten at close.

Time is labeled relative to **electrical pump sync**. Optical arrival at the
sample has not been calibrated. Marker wavelengths are controller readbacks,
not an independent absolute wavelength calibration. Sequential blank correction
assumes repeatable sequence-dependent intensity behavior and cannot remove
nonrepeatable inter-run drift. The surface alone does not establish photolysis
kinetics. Saving or processing data does not promote a calibration bundle or
establish instrument qualification. Store source observations, uncertainty
analysis and bounded scientific claims with the records in System_Research.

The 7–10× sample-rate-to-filter-bandwidth recommendation is an anti-aliasing
guideline, not a hardware acceptance limit. Automatic selection prefers settings
meeting its 7× lower margin where available. Supported manual settings below
that margin remain selectable and do not require an extra confirmation. The
UI displays a brief advisory and compact settings and resolution readouts.
The saved selection retains the sample-rate/bandwidth ratio and estimated
filter attenuation at Nyquist. That attenuation describes
the filter response, not measured total aliasing error; signal and noise content
also matter. If no automatic candidate meets the guideline, the app retains a
supported configuration with the same advisory. Actual hardware, cadence, timing
and memory constraints still apply. The resolved selection records the advisory
and its numerical estimates with the run.
See the [HF2 rate guidance](https://docs.zhinst.com/hf2_user_manual/functional_description/lock_in.html).

Memory quantities use decimal MB (1 MB = 1,000,000 bytes). Preflight separates
uncompressed samples/timestamps from estimated record storage. Record storage
includes per-record metadata, with no percentage margin or buffer/copy multiplier
in either planning or the exact DAQ preflight. It does not predict peak process
RAM or compressed saved file size. The 536.9 MB application memory advisory
is an advisory threshold, not a start gate or a measured HF2LI hardware limit.
Exceeding it displays a brief memory warning. Exact DAQ preflight checks current
available host memory (or an explicit executor memory limit); cadence, supported
hardware settings, timing-table capacity and reconstruction allocation limits
remain enforced.
Halving phase spacing approximately doubles scan count at fixed scan trajectory
and HF2LI rates. Automatic selection can also raise the detector sample rate
to improve temporal resolution, further increasing data volume. Inspect the
selected rates and resolution alongside the memory estimate.
To reduce scan span, bring **Start wavenumber** and **Stop wavenumber** closer
together. There is no separate scan-size control. Sequence scan count is derived;
increasing **Phase-delay spacing** reduces the number of phase scans.

After completion or failure, **New run** clears the session's blank selection,
preliminary review and plots without deleting saved files or changing the entered
settings. Acquire or select a blank to begin again. Editing settings updates the
selected HF2LI summary; actual acquisition readbacks remain in the saved run and
are displayed at completion, rather than being represented as current settings
after an edit.

Restoration commands include explicit frequency units. Sweep capability checking
is non-emitting: the check stops, the start wavenumber is retuned, and emission,
manual-tune cancellation and sweep arming occur in that order. Settings are
checked again before measurement frames start. Each sequence has one emission
interval. Saving a plan does not acquire a blank.

## Shared host and recovery

The shared measurement host registers `phase_scan:single` and `phase_scan:dual`.
Each mode has independent settings, supported HF2LI choices, runner, baseline,
review and cancellation. Preferences use the mode-specific namespace. The plan
and destination are captured before dispatch; subsequent changes apply to future
operations.

Connected-device checks take exclusive ownership before real discovery or
connection. If another tab or app task owns the instrument, use that owner's
Stop, Emission Off, Safe Idle or Deinitialize control and wait for cleanup and
saving. Retry **Check connected device** if its automatic check was blocked.
The workspace selector keeps all tabs reachable for offline plan editing,
simulation and saved-data inspection.

Normal **Abort acquisition** targets this tab only. Application close checks all
installed handles, including dual mode and future modules. Emergency exit
requests cancellation of live hardware operations and waits for their workers;
it does not abort unrelated offline analysis or simulation. A worker finishing
does not establish safe shutdown. Available native, partial and restoration
records are retained; cleanup/save failures remain failures after cancellation.

A restoration failure, preservation failure or abandoned process leaves an
instrument ownership/fault message. Owner cleanup controls remain available to
inhibit outputs. After physical restoration and required native-data preservation
have been verified, use **Review instrument recovery…**. Supply the named verifier
and a retained evidence file covering both outcomes, then confirm both checks.
Recovery performs fresh safe-shutdown checks and records their readbacks and the
verification evidence before releasing ownership. It never fires, repeats a run,
deletes partial records or erases fault history. Failed verification or a still
live SDK call keeps hardware unavailable.

The Windows lock is shared by app/task processes and checkouts under
`%PROGRAMDATA%/ControlSystem/`. Access failures require correcting permissions;
do not delete records or use a second lock to bypass an owner. Vendor apps are
outside this coordinator and must release their sessions separately. Host tests use synthetic instruments, offscreen Qt and self-contained native
records. They do not establish live shutdown, restoration or recovery behavior.
