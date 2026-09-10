# Steady-state slow scans

The top-level **Slow Scan** and **Dual-Detector Slow Scan** tabs implement
`steady_state_slow_scan:single` and `steady_state_slow_scan:dual` using measurement
host API 1. They record unpumped static spectra for initial characterization,
local high-quality spectra, short state verification and post-exposure
comparison. FIRE and Q-switch remain inhibited for every operation and every
frame, including preliminary measurements, controls and terminal frames.

The independent condition profiles are room-temperature HRP–CO,
room-temperature MbCO, 77 K HRP–CO and 77 K MbCO. Each retains its own entered
sample, preparation, cell/reload, position, matrix, temperature, material lot,
thermal history and exposure/state identifiers within the detector tab. Switching
conditions does not create another acquisition engine or invent an ARC ID.

## Installation and starting the tabs

Install this package directory beside the completed measurement host and start
the existing application normally with its UI dependencies. Discovery reads the
package's `registration.py`; no main-window or central-registry change is needed.
The original Phase Scan tabs and their scientific formats remain unchanged. The
package imports no sibling experiment. Registration, widget construction, plan
editing, simulation and saved-data analysis perform no hardware access.

This implementation was developed on the integrated host baseline `7152d66` in
the isolated `codex/steady-state-slow-scan` worktree. That baseline includes the
completed single/dual Phase Scan work and fixes. The original checkout was not
reset, stashed or modified.

Choose the save location in the app's top bar. Each operation freezes that root
and saves to
`<root>/measurements/steady_state_slow_scan/<single|dual>/<run_uuid>/`.
Changing the save location affects subsequent operations. Preferences use
`measurements/steady_state_slow_scan/<mode>/v1/` through the scoped host interface;
the module never changes a shared QSettings group.

## Operator sequence

1. Select the condition and purpose. Enter its actual sample/preparation/cell/
   position/temperature identities and temperature observation with uncertainty.
   A bath temperature alone does not establish sample temperature. Confirm
   equilibration using the applicable recorded procedure; the installed adapters
   do not operate a cryostat, temperature sensor, stage or shutter.
2. Enter the applicable promoted operating-bundle IDs and load the profile.
   Select **Use connected instruments** and **Read connected capabilities**.
   Capability discovery takes the same exclusive instrument ownership as an
   acquisition. It records installed QCL ranges, HF2LI supported settings and
   T660 frame capability, then verifies cleanup. Merely loading a plan or bundle
   does not authorize emission or accept any campaign phase.
3. Declare each QCL segment explicitly. Review resolution, native rate, selected
   speed, measured response, settling, repeat count and the wall-clock/storage
   estimate. Blank overrides use the applicable operating profile. Supported
   editable overrides remain subject to its measured validity envelope. **Save
   plan…**, **Load plan…**, and **Inspect plan and frame/channel schedule** expose
   requested, selected and actual values with explicit units and provenance.
4. Select the physically blocked state and confirm it, then **Acquire dark**,
   or load a complete compatible dark record. The software inhibits MIRcat
   emission and both pump outputs. Optical blocking is a manual action; no
   connected shutter is assumed.
5. In **Slow Scan**, put the matched matrix/buffer/cell background in the sample
   path, confirm that physical state, and **Acquire matched blank**, or load a
   compatible completed blank. This is the complete planned forward/reverse
   sequence, including all replicates. In **Dual-Detector Slow Scan**, leave the
   matched-buffer reference in its reference path. It is recorded simultaneously
   with the sample; there is no routine separate full blank sequence.
6. Load the sample and confirm the sample state. Select **Acquire sample
   preliminary**. Both directions and their individual replicates are retained.
   Review signal support, direction differences, noise, fitted components,
   residuals, references and quality flags. Select the explicit preliminary
   review checkbox.
7. Select **Start unpumped slow scan**. This is a separate action from review;
   neither action ever requests a pump event. Every declared block is configured,
   tuned, settled, uploaded, acquired, retrieved, restored and saved. The status
   displays actual stages and acknowledged timing-frame progress. The HF2LI is
   the spectral recorder.
8. Select a segment, direction and replicate in the spectrum view. Inspect raw
   detector signals, normalized ratio, available absorbance, the independent
   fitted peaks and residuals. Numeric coordinate entry and held-arrow controls
   select actual observed spectral coordinates. Missing support stays missing.
   Enter local band/off-band bounds, refit prospective alternatives if justified,
   or load a compatible pre-exposure state for comparison. Navigation and image
   export remain in the plot toolbar. **Load native run…** requires no hardware.
9. Export quantitative data as a new immutable analysis record. Exporting an
   accepted sample-state selection additionally requires a named reviewer,
   explicit scientific acceptance, bounded rationale, valid fitted support and
   the applicable uncertainty/calibration evidence. Simulated data cannot accept
   a physical sample-state record.

**Abort** targets this tab's operation. It requests cooperative cancellation,
retains available native/partial records and attempts all restoration actions.
Wait for saving and cleanup. A normal stop says **Acquisition stopped**; an
unverified restoration or storage failure remains a failure. Host-wide emergency
stop and manual instrument recovery are separate lifecycle actions. Ownership
persists through cleanup and preservation; a failed outcome leaves the host's
actionable recovery fault. **New run** clears this tab's controls, preliminary
approval and results while retaining entered settings and all saved files.

Settings, sample/condition, selected controls, calibration and relevant instrument
changes invalidate incompatible preliminary approval. The mismatch identifies
the differing fields. Restoring compatible values clears compatibility errors
without silently granting review. Operator physical confirmations are checked
separately from scientific control identity.

## Planning and installed execution

`EXPERIMENTS.md` sections 7, 9.1, 10.1, 11.2 and 14–17 are the scientific
requirements. Their literature anchors and illustrative values are not operating
settings. The planner uses the requested resolution, measured line width,
intrinsic resolution, sample/reference native rates and independently
characterized detector/HF2LI response. Its engineering estimate is

\[
r_{eff}^2 = r_{intrinsic}^2 + (v/f_{native})^2 + (v\,t_{response})^2.
\]

Native spacing must also resolve the requested resolution and measured feature
width. Both detector constraints apply in dual mode, with aggregate throughput
including the timing stream. The HF2LI filter bandwidth estimate is
\(\sqrt{2^{1/n}-1}/(2\pi\tau)\). These estimates are labeled as engineering
planning models; they do not replace measured optical linewidth or trajectory
validation. An unsupported combination is reported rather than silently split.

Each segment/direction is a declared finite block. Replicates within a block
share the preloaded hardware schedule. QCL and direction changes explicitly
stop, configure, tune and check readiness; they are not represented as continuous
spectral scans. T660-1 supplies the characterized reference/probe/frame-input
train. T660-2 uses the existing acknowledged pending-field upload optimization.
Its A (FIRE), B (Q-switch) and D outputs are OFF in every frame; C alone carries
the qualified active-low Process Trigger. Every block ends with an all-OFF
terminal frame. Train count is zero (no extra train pulses). Hardware dividers
and quantized timing fields define electrical edges. Polls and cancellable waits
retrieve data and enforce settling/readiness; they do not define precise edges.

The adapter uses the host's fresh MIRcat, T660 and HF2LI services, under its
operation token, including discovery, configuration and cleanup. The maintained
wiring maps sample to HF2LI ADC 0/demodulator 0, reference to ADC 1/demodulator 3,
and timing to demodulator 2. MIRcat direction/Sweep Active/wavelength markers use
DIO20/21/22. The detector tee branches and receiver terminations must be qualified.
PicoScope remains a qualified diagnostic instrument, not an alternate spectral
recorder; this module performs no routine scope acquisition or rewiring.

The operating manifest section is
`steady_state_slow_scan.planner_inputs`. Its typed fields are documented in
`settings.py`; `planner.py` validates applicability and `acquisition.py` consumes
the explicit service settings. The scientific profile includes measured
resolution/response/settling and probe evidence, separate HF2LI input/filter/PLL
settings and qualified health-node identities, each QCL's pulse/current and
marker-channel settings, calibration IDs and overhead estimates. Installed
readbacks can constrain supported ranges/rates; they cannot create calibration
qualification. A loaded profile is rechecked through the host promotion loader
before hardware use. No checksum matching is an operational gate.

The profile separately declares `external_pulse_acceptance` for each QCL;
accepted external TTL requests and the controller's internal pulse-rate/width
settings need not be numerically identical. `direction_bit_by_direction` records
the qualified installed polarity, and `t660_clock_readbacks` identifies the
expected 10 MHz clock configuration/lock observations. Missing identities are
readiness items, never invented wiring or inherited Phase Scan operating values.

## Native data and equations

Every returned HF2LI poll chunk is journaled before interpretation. Lossless NPZ
arrays preserve native dtypes and integer ticks; JSON supplies readable parentage.
Integer timestamp epochs are subtracted before floating-point conversion.
Observed Sweep Active intervals and qualified controller markers establish
spectral support. Marker-count errors invalidate the axis instead of shifting
later observations onto invented coordinates. The native streams, original
values, controller readbacks and applied corrections remain available separately.

Sample/reference values align by observed timestamp support, including applicable
recorded delay corrections. Original streams remain intact. The primary dual
quantity is \(Q=S/R\), a **reference-normalized ratio**. Its variance retains the
sample/reference covariance term:

\[
\operatorname{var}(Q)=\operatorname{var}(S)/R^2+
S^2\operatorname{var}(R)/R^4-2S\operatorname{cov}(S,R)/R^3.
\]

A compatible separately retained unpumped \(Q_0\) provides
\(\Delta A=-\log_{10}(Q/Q_0)\). Absolute dual absorbance requires an applicable
measured path-balance factor \(B\): \(A=-\log_{10}(Q/B)\). Q0 is never used as B.
In single mode, the dark-corrected sample is divided by its matched sequential
blank, with the independent-noise assumption and drift limitation retained.
Missing variance stays unknown; it is not silently assigned zero. A dark mean
uses the observed emission-OFF data; correlated-noise limitations are retained.

Control matching is exact by default. A promoted profile may explicitly declare
`control_match_max_gap_cm1` for bounded interpolation between adjacent valid
control points; its use and bound are recorded. Invalid intervals, absent
markers, long gaps, nonpositive references and unsupported endpoints remain
missing. Axis/path corrections require applicable configuration and calibrated
support; original axes and detector values are never overwritten.

Each sweep is processed and fitted independently. Pairwise comparisons report
repeatability, mean drift and direction-dependent differences before any pooling;
the implementation performs no automatic pooling. Gaussian and Lorentzian
components have freely fitted centers, widths and amplitudes. Constant, tilted
or quadratic baselines and explicitly selected sinusoidal fringe periods are
supported. Prospective component count is editable; peaks are never added or
centers fixed to match literature. Cryogenic data are independently initialized
from their observations.

Fits retain full parameter/overlap covariance, residuals, center/width/height/area
uncertainty, AICc and alternative baseline/line-shape models. Area uses the fitted
analytic line shape, with extrapolated-tail limitations flagged. Local Jacobian
uncertainty is conditional on the model and noise assumptions; omitted variance
is labeled as a residual-noise estimate. These results do not establish molecular
state assignments or temperature effects without supporting evidence.

`run.json` and `native.npz` preserve controls, individual sweeps, fits, native
timing streams, requested/selected/actual values, failures and restoration.
`native_chunks/` preserves incremental observations even when later processing
fails. Reanalysis creates a new file/sidecar rather than modifying native data.
The host's standalone version-1 `SampleSpectralSelection` format carries sample,
condition/configuration, fitted windows and uncertainty, source run, acceptance
reviewer/time and rationale. Consumers can load it without importing this module.
It neither promotes an instrument bundle nor accepts a campaign phase.

## Verification and commissioning boundary

Hardware-free verification covers both discovered top-level tabs and isolated
sessions; deterministic complete pump-OFF schedules; independent controls and
review; synthetic overlapping/shifted cryogenic peaks, tilted/fringed baselines,
uneven/reversed axes and missing intervals; detector covariance, invalid
references and normalization; native integer precision and lossless persistence;
abort during preparation/acquisition/processing; storage failure and cleanup
failure precedence; owned injected-device execution and contention with sibling
and manual owners. The host compatibility and existing Phase Scan regression
suites are run without editing their tests.

Run the experiment suite with the repository's existing UI environment:

```powershell
python -m pytest software/tests/measurement_modules/steady_state_slow_scan -q
```

No physical instruments were operated for this development. The maintained
promoted registry is empty at this baseline. Actual usable QCL ranges,
trajectory/settling, optical linewidth, marker polarity/channel identities,
external probe acceptance, tee loading, HF2LI lock/clipping nodes and simultaneous
throughput, axis/path balance, temperature validity, sample-state/reset
equivalence and optical timing remain commissioning items where not established
by applicable promoted evidence. Optical pump arrival/time zero and IRF are not
measured by static spectroscopy. The four sample-state claims must remain bounded
by their own measured preparation and temperature evidence. Hardware readiness,
sample-state acceptance, campaign documentation completion and instrument
promotion are distinct decisions.
