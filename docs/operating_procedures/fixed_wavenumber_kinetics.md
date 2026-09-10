# Fixed-wavenumber discovery and recovery

The independently installed module supplies exactly two top-level tabs:

- **Fixed-Wavenumber Kinetics** (`fixed_wavenumber_kinetics:single`).
- **Dual-Detector Fixed-Wavenumber Kinetics** (`fixed_wavenumber_kinetics:dual`).

Both use experiment ID `fixed_wavenumber_kinetics`. This is a supporting/pilot
measurement under [EXPERIMENTS.md](../../EXPERIMENTS.md), not another principal
reconstruction family or ARC experiment ID. Protein and temperature select
condition profiles inside these tabs. Existing Phase Scan tabs are unchanged.

## Installation and launch

Start from the completed measurement-host API 1 baseline, including the working
single- and dual-detector Phase Scan implementations. Install the directory
`software/control_app/measurement_modules/fixed_wavenumber_kinetics/` and restart
the normal Control System application. Its own `registration.py` supplies both
tabs through host discovery; no central registry or application changes are
needed. The normal application dependencies (NumPy, PySide6, Matplotlib, and the
installed device services) suffice. No other new experiment package, SciPy,
experiment builder, or command-line acquisition script is required.

The foundation must include its additive guarded
`HF2LIService.read_acquisition_health()` API. This task includes the implementation
supplied by the foundation owner; the experiment does not modify that service.

Registration and widget construction perform no device enumeration, connection,
configuration or acquisition. Native saved runs and plans can be inspected without
connected instruments. **Use synthetic example settings** selects explicit
simulation and supplies labelled surrogate evidence; it never falls back to real
devices. Simulation records cannot establish instrument or sample readiness.

## Routine operation

1. Choose the top-bar **Save Location**. Each acquisition freezes that root and
   saves in `measurements/fixed_wavenumber_kinetics/<single|dual>/<unique-run-id>/`.
   Later root changes apply to subsequent operations. Save/Load Plan preserves
   editable settings and rejects another experiment or detector mode.
2. Load an applicable **promoted operating profile**, select the protein and
   temperature condition, and enter sample, preparation, cell, physical position,
   temperature and control record identities. Resolve the displayed readiness
   items. Requested overrides must fit the measured profile and supported device
   settings; they are never silently lowered. The supplied registry currently
   contains no promoted bundles.
3. Enter one measured position or an explicitly ordered list, labelling band and
   off-band observations separately. An accepted version-1 host sample-selection
   JSON can populate the list without installing its producer. Alternatively,
   enter candidate positions and acquire this module's own unpumped preliminary.
   Reviewing that result accepts only the actually observed local points; it does
   not determine a fitted band center, full band area, or conformer assignment.
4. In **single** mode, physically load the buffer in the sample optical path and
   select **Acquire complete buffer blank**, or load a complete compatible saved
   blank. Pump outputs remain inhibited throughout the full ordered blank
   schedule. Then load the sample and acquire its unpumped preliminary. In **dual**
   mode, load the sample and matched-buffer reference together and acquire their
   simultaneous unpumped preliminary; there is no routine separate full blank.
5. Inspect the native signals, normalized signals, pre-pump statistics, reference
   support and quality flags. Select **I have reviewed the preliminary
   measurement**. Acquisition, review and Start are separate actions. Settings,
   selected records or relevant instrument changes clear incompatible approval.
6. Select **Start finite fixed-point acquisition**. The worker configures fresh
   owned services, checks readbacks, uploads acknowledged finite timing frames,
   verifies actual MIRcat `Tuned`/wavenumber and characterized settling, acquires
   the stationary pre-pump signal, and executes the finite event. It retains the
   HF2LI detector and electrical timing streams through the recovery window.
   Later equivalent events require both applicable reset evidence and observed
   return/stationarity. Failed or missing pump events are never retried.
7. Inspect individual events, equivalent-event aggregates and dose/order trends.
   Numeric event/time controls and held arrows select retained coordinates.
   Unsupported support remains a gap. The toolbar contains view and image-save
   controls. **Load native run** opens saved results; **Export data** writes the
   plotted/analysed observations with event and position identity.

**Abort acquisition** requests only this tab's cancellation. Wait for cleanup and
native preservation. A normal stop says **Acquisition stopped**; restoration or
storage errors take precedence and remain failures. Partial, rejected,
interrupted, control and restoration records are retained. **New run** clears
this tab's baseline, blank, review and plots while preserving entered settings,
the other tab and all saved files. Host emergency stop remains a separate action.

## Condition profiles and physical actions

Room-temperature HRP–CO supports high-SNR local discovery, off-band controls and
selected-band long recovery. Observation duration, accepted dose and reset
interval come from the actual preparation's evidence, not the literature's
approximately one-second recovery prior. Room-temperature MbCO begins at an
accepted A1 selection. A0/A3 require retained quantification and separation
evidence; nominal literature centers alone are insufficient.

Cryogenic profiles require separately qualified matrix, cell, temperature and
response evidence. A non-resetting state is observed with one pump per operation.
Establish and document a fresh equivalent state before a new pumped operation;
no position stage, flow, thermal reset or temperature sensor is invented by this
module. Full-state equivalence cannot be established from return of one point
alone. Incomplete recovery is retained as an observation-limit/censoring result.

Every dispatched pump clears preliminary approval, including interrupted or
missing-marker attempts. Real cryogenic consumption is journalled before dispatch
in `%PROGRAMDATA%/ControlSystem/fixed_wavenumber_kinetics_state_history.jsonl`,
independently of detector mode and Save Location. New run, a different tab, or a
changed position label cannot make the state unused. **Load accepted fresh-state
equivalence record** accepts JSON with `accepted: true`, `record_id`, matching
sample/preparation/cell/condition/position IDs, `accepted_by`, `source_run_id`, and
`equivalence_basis`. It describes an already established measured equivalent
state; loading it does not perform a reset. Each accepted state record can be
consumed once. Synthetic cryogenic history is separately retained beneath its
simulation save root and cannot alter physical history.

The app cannot mount a sample or buffer, verify an uninstrumented sample
temperature, change an unwired optical gate, or establish physical reset by
software. These are explicit physical actions/readiness items. Acquiring a
control or accepting a local preliminary does not promote an instrument bundle,
authorize a campaign phase, or complete a phase procedural writeup.

## Operating-profile and exchange records

The host validates promotion by bundle ID. A bundle's `manifest.yaml` supplies
either a `fixed_wavenumber_kinetics` mapping or a
`fixed_wavenumber_kinetics_profile` relative JSON filename inside that bundle.
The profile mapping may be an evidence envelope with `operating_profile` and
`sample_selection`, or the operating profile itself. Sample-derived selection is
kept separate from instrument calibration; a plain sample JSON is never promoted
calibration. Plans cannot carry synthetic qualifications into connected work.

The measured operating profile resolves these groups, with stable record IDs and
the applicable condition identity:

- `record_id`, `qualification_kind=measured`, `configuration_id`,
  `condition_profile`, `condition_id`, topology/response/temperature/dose IDs.
- Independent `sample` and (for dual) `reference` demodulator/input indices,
  `rate_sps`, `timeconstant_s`, and filter `order`; `hf2li.signal_inputs` and
  `hf2li.pll`; separately retained timing demodulator/rate/marker qualification.
- The complete `probe_recipe`, MIRcat QCL pulse parameters and actual tuning
  envelope; `settling_s`, `tune_tolerance_cm1`, and measured acquisition response.
- `timing` input frequency, FIRE/Q-switch delays, widths, polarity/termination and
  hardware quantization/capacity; no Phase Scan recipe is implicitly reused.
- Aggregate throughput, qualified continuous streaming/backpressure behaviour,
  minimum accepted event interval/reset evidence, tolerance validity envelopes,
  and stage-specific overhead estimates.

See the pure planner and its module-local tests for the executable schema.
`simulation_profile()` is a complete synthetic example of the shape, explicitly
unrelated to commissioning or established biological settings. Missing evidence
is displayed as readiness work; it is not filled from illustrative numbers.

The planner retains requested, selected and actual-value slots, all frame/channel
states, finite counts, units, memory/storage accounting and an estimate basis.
The runner adds actual readbacks. Human-readable IDs, paths, versions, timestamps,
configuration and producer records establish provenance. No checksum/hash match
is an operational, acceptance, analysis or loading gate.

## Timing, retention and installed services

HF2LI is the primary recorder. Sample/reference roles are selected from the
qualified topology and checked independently, including aggregate throughput.
The normal installed signal paths preserve both BNC tee/receiver branches.
PicoScope remains the timing/IRF diagnostic instrument; this module consumes
qualified diagnostic records and never substitutes PicoScope for the HF2LI.

T660-1 supplies the qualified probe/reference train. T660-2 executes preloaded,
bounded frames; FIRE and Q-switch enable only the authorized event, process
trigger remains OFF for stationary acquisition, channel D stays OFF, and terminal
padding inhibits all channels. Train count zero means one pulse for an enabled
channel, so count alone is never used to suppress pump outputs. Upload uses the
existing pending-field optimization with acknowledgements, progress and cancel.

Pump edges are defined by the device timing table, not polling or host sleeps.
The observed Surelite Fixed Sync on maintained DIO16 supplies an electrical
reference, distinct from programmed Q-switch commands and independently observed
optical arrival. Actual timing streams and the original device-tick pump epoch
are retained. Numerical timestamp precision does not establish optical time zero
or an HF2LI response faster than its measured detector/filter bandwidth.

One continuous acquisition is retained per explicitly planned event/position
block. Tuning, preparation and inter-block dead time are explicit; disk chunks
are storage boundaries within a continuous subscription, not new acquisitions.
Every chunk is written before validation and preserved even when rejected.
Timestamp overlap, internal/boundary gaps, loss flags, bad reference, clipping,
unlock and count mismatch are detected. No rolling buffer silently overwrites
data. Long records use incremental native NPZ chunks plus a journal; incomplete
files remain identifiable and completed chunks can be recovered if a final
manifest write fails. Native integer ticks, numeric dtypes and detector values
remain exact.

Safe inhibition precedes one bounded final retrieval of available HF2LI samples
before unsubscribe. Tail-retrieval failure records the uncertain native boundary
and does not bypass the remaining cleanup. Saved records identify their explicit
blank/preliminary parent files and run IDs. Loading an interrupted record can
reanalyse its preserved chunks without changing its acquisition disposition;
missing or mismatched parent files are reported rather than replaced.

The host owns all real access, including connection, configuration, readback and
restoration, through required native preservation. A sibling detector tab or
manual control cannot take the coupled spectrometer. Safe idle inhibits both
timing sources and all outputs, turns MIRcat emission off/disarms, restores
retained detector/MIRcat settings where applicable, verifies readbacks and closes
services. Unverified cleanup or preservation leaves an actionable host fault.

## Calculations and displayed limits

At matched valid detector ticks, dual mode retains `Q=S/R`. Its compatible
unpumped baseline is `Q0`, and difference absorbance is

`ΔA = −log10(Q/Q0)`.

Raw `S/R` is reference-normalized signal, not absolute transmission. Absolute
absorbance is available only with a compatible measured path-balance factor
`B`, using `A = −log10(Q/B)`. A loaded Q0 is never substituted for B. Single mode
uses the complete compatible sequential blank to form its detector ratio and
the compatible unpumped sample to form its difference signal. Invalid,
nonpositive or missing reference support is masked, not repaired.

Ratio uncertainty includes sample variance, reference variance and their
covariance. Matched pre-pump covariance and baseline statistics are retained with
their source. The displayed apparent recovery model is

`measured response * [amplitude H(t) exp(−t/τ)] + offset + drift·t`.

Fits use the measured acquisition-response kernel, retain prediction/residuals,
parameter covariance, conditional standard errors and a profiled interval for
τ. They flag unsupported/unresolved components and report incomplete recovery.
Response uncertainty and correlated noise can widen the conditional intervals;
these limits are not silently presented as complete physical uncertainty.
Aggregation uses only eligible equivalent-state events at the same position on
matched retained support; controls and rejected events remain individual.

To bound analysis memory, long-run plotting/fitting uses an explicit subset of
actual native observations and endpoints. Each event reports native count,
analysed count and sampling stride. Gaps are detected before sampling and stay
visible; full native chunks and streaming baseline statistics remain available.
This display/fit subset is not a claim that every recorded point was fitted.

Fixed-point amplitudes do not establish full band area or a microscopic pathway.
An apparent recovery is not automatically a geminate or solvent-rebinding
lifetime. **Export discovery evidence for stroboscopic comparison** writes a
versioned file identifying source data, condition, response and unresolved
requirements. Compare it with an appropriate existing nanosecond or microsecond
stroboscopic data product via file exchange; no producer package import or
installation is required.

## Verification and commissioning

Hardware-free verification is in
`software/tests/measurement_modules/fixed_wavenumber_kinetics/`, using uniquely
named tests. It exercises both real widgets and their guided simulated workflow,
finite timing/count/quantization, full blank and preliminary paths, condition and
mode compatibility, covariance-aware alignment, known recovery with drift,
missing support, controls, clipping/unlock, long-record boundaries, cancellation,
preservation/restoration failures, and host ownership contention. The frozen host
contract, interchange and presentation tests run separately without modifying
other experiments' tests. The final combined verification completed with
**346 passed and 6 skipped** across this module, the host compatibility and
integration suites, the additive HF2LI health API tests, and the existing single-
and dual-detector Phase Scan regression suites. The dual-detector tab was also
visually inspected with retained synthetic data.

No hardware was operated during development. Connected commissioning still
requires promoted calibration/characterization profiles, receiver/topology and
filter qualification, lossless long-record endurance, observed optical
pump/timing qualification, real temperature history and preparation-specific
dose/reset equivalence. Passing synthetic or injected-device tests does not
complete those measurements or change scientific phase status.
