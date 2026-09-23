# Microsecond Stroboscopy

The two independent tabs are **Microsecond Stroboscopy** and **DD Microsecond
Stroboscopy**. Their instance IDs remain
`microsecond_stroboscopy:single` and `microsecond_stroboscopy:dual`.
Each tab has its own settings, retained references, results and cancellation.

## Inputs and actions

Enter wavenumbers in cm⁻¹, delays in µs, averages and event spacing. The right
pane shows the selected detector response, sample rate, delay range and estimated
time/storage above the plots. The framed **Advanced overrides** form is always
visible. It contains detector filter order, time constant and sample rate,
integration aperture, **Repetition rate** and **Pulse width**; dual mode also
exposes the reference detector's filter settings. Changing one field leaves the
other automatic choices active. Device capability
checks run as owned operations. Constructing or editing a tab performs no device
I/O.

Normal acquisition uses the installed device factories. There is no execution-mode
selector or approval checkbox. Saved plan temperature, condition, qualification and
sample-selection fields remain readable metadata and do not select an acquisition
procedure or gate raw measurements. Simulated acquisition requires explicit
developer injection and is used by tests.

1. Select the application's **Save Location** and enter the acquisition inputs.
2. Optionally acquire or load a blank in single-detector mode. A compatible blank
   enables measured transmission and absorbance. Relative sample measurements
   do not require one. Dual mode acquires sample and reference together.
3. Optionally acquire an unpumped preliminary sample. **Sample** acquires its own
   unpumped baseline at each wavenumber, so a separate preliminary is optional.
4. Start the sample acquisition. Compatible acquired or loaded references are
   reused automatically. Incompatible references are omitted; a new baseline is
   measured. Sample/blank physical loading remains an operator action.
5. Inspect native points, spectral maps, kinetics and coverage. The numeric and
   slider slice controls use measured coordinates, preserving missing support.

**Save Plan**, **Load Plan**, **Load Run**, **Export** and **New Run** remain
available. New Run clears the displayed result and retains reference candidates
for compatibility checks on the next operation. Loading a native run does not
require its saved condition metadata to match the current labels.
Loading a plan or saved GUI preferences returns former overrides whose controls
have been removed to automatic defaults and retains their original values as
source metadata. Visible overrides keep their independent Auto or explicit
selection. Loading native measurement evidence preserves its original settings.

## Acquisition and scientific limits

At each wavenumber, T660-1 supplies the continuous reference/probe train and
T660-2 supplies finite tables containing isolated pump events. Hardware tables
define precise edges; host waits handle settling, event spacing and completion.
Frame spacing within one block is distinct from spacing between pump events.
The compiler checks pulse ordering, quantization, duty, finite-frame capacity,
capture bounds and transfer/storage capacity.

The installed optical source is QCL1. Acquisition, tuning, pulse settings and
restoration address QCL1 explicitly; stored device-selection metadata cannot
route a new operation to another QCL. Wavenumbers must lie within its reported
tuning range. **Repetition rate** is the emitted optical cadence set by the
external T660 trigger. **Pulse width** sets the MIRcat SDK optical pulse width;
the T660 electrical trigger width is a separate automatic setting.

The MIRcat internal pulse rate remains separate, using its connected readback or
an explicit frozen instrument configuration. It must exceed the external trigger
rate. Both the external rate and internal rate, each multiplied by the optical
pulse width in seconds, must stay at or below 0.30 and any stricter selected or
vendor duty limit. Requested values and actual device readbacks are checked;
vendor rate/width limits and T660 trigger-timing constraints also apply.

Time and memory estimates include the installed T660 command delays, table setup,
subscribed acquisition overhead and cumulative native retention. The default
retention limit is an explicit 8 GiB planning allowance, not a measurement of
available RAM. Blank, preliminary and sample actions use their own capacity
estimates; a large sample request does not block a smaller preliminary action.

HF2LI is the recorder: sample demodulator 0, reference demodulator 3 in dual
mode, and timing demodulator 2. Actual receiver settings, phases, filter orders,
time constants, rates and acquisition health are retained. Native X/Y and
unsigned device timestamps remain unchanged. Finite negative quadratures remain
available as raw data; they are never made positive to create absorbance.

DIO17 records electrical Variable Sync. Without an applicable measured optical
latency, the reconstruction uses an explicitly electrical time origin. This
allows relative-delay measurements while leaving optical arrival and optical
resolution uncalibrated. Entering a delay increment or an engineering response
estimate does not establish optical resolution. Pre-pump recovery differences
are retained as diagnostics and limit equivalent-state kinetic claims.

For valid positive support, dual mode uses `Q = S/R` and
`ΔA = −log10(Q/Q0)`, with paired sample/reference covariance and baseline
uncertainty. Absolute transmission and absorbance require measured background
support; Q0 is not a substitute for that background. Single mode uses its own
unpumped sample for relative changes and an optional compatible measured blank
for transmission/absorbance. Optional measured dark corrections act on copies.

Recovery fits filter intensity before taking the logarithm. They use actual
matched native aperture times, the causal HF2 response and explicitly retained
timing uncertainty. Constant and freely estimated recovery models are compared
with AICc; literature times are not fixed fit parameters. Unknown optical origin,
unqualified response, inadequate support, unequal uncharacterized detector
responses, or measured nonrecovery limit kinetic claims. Native measurements
remain available. Local band areas integrate measured coordinates with gaps and
uncertainty; they are not fitted as if they were detector intensity.

## Preservation and stopping

The host freezes settings, configuration and output location before dispatch.
Runs are saved beneath
`<Save Location>/measurements/microsecond_stroboscopy/<single|dual>/<run UUID>/`.
Immutable revisions retain native streams, partial/rejected blocks, actual
readbacks, analysis and restoration outcomes; `latest.json` selects the latest
durable revision. Native array dtype, integer ticks, signed zero and missing
values survive loading. No repository hash-matching gate is used.

**Stop** cancels the current tab's operation. Ownership remains held through
cleanup and native preservation. Real interlock/device errors, failed restoration
and failed saving remain actionable errors. Acquisition cleanup inhibits timing
outputs and verifies MIRcat emission, scanning and armed state are off, including
partial preparation and a laser that was initially armed; SDK deinitialization
does not establish that outcome. **Retry native save** preserves
retained arrays at a writable location after a storage failure; it performs no
device operation and does not clear an instrument recovery fault.

Software verification uses injected device transports and explicit simulators.
It covers QCL1 routing, separate optical and trigger pulse settings, exact duty
boundaries and upward readback rounding, saved-plan migration, native settings
preservation, cancellation and cleanup. UI checks use both detector modes at 1100 × 780 with visible override rows.
These checks do not perform physical laser or sample acquisition.
