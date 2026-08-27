# HF-01 — HF2LI configuration and external-reference qualification

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `historical_complete`  
Required dependencies: `T2-01, TR-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../shared/phase_execution_requirements.md`.

## Phase-specific procedure and deliverables

The detailed phase text below was materialized from the former combined procedure catalog. Git commit `75b138a` preserves that pre-split source.

### 12. HF-01 — HF2LI configuration and external-reference qualification

HF-01 is completed historical evidence. The procedure text below records its
execution-era design and does not define current experiment-mode requirements.
HF-01.1 may supersede future configuration use without changing HF-01's PASS status,
decision, or configuration identities.

Execute the bounded PicoScope-AWG electrical parameter-characterization design
in `plans/hf01_awg_parameter_characterization.md`. Keep all lasers inhibited
and shuttered. Use the monitored AWG carrier step and offset-carrier response to
measure, rather than merely assume, the relationship among input range,
time constant, filter order, acquisition rate, noise, settling, attenuation,
phase/delay, clipping, and throughput. Use exactly three separated electrical
points solely to validate the manufacturer response model; they are not
preselected experiment settings and receive no sweep, HRP-C-CO, or MbCO label.
After model validation, evaluate every supported order, time constant, range,
and output rate computationally against each experiment's requirements, then
physically confirm only the configurations selected by that analysis plus one
challenger per case when uncertainty leaves the selection ambiguous. Do not
run an HF2LI parameter grid on Mylar. Preserve `CLOCK-SPLITTER-01` in its
normal T660-2-to-T660-1/HF2LI 10 MHz clock distribution. Use a separately
identified passive 50 ohm, DC-coupled BNC tee for monitored AWG stimulus and
use measured, read-back-verified T660 reference/marker copy channels for
PicoScope timing.

All HF-01 signal-input stimuli remain centered at the retained 2 MHz carrier.
The 10 Hz Nd:YAG/OPO cadence is not an analog HF2LI test frequency and does not
create a fourth response point or anchor. Check it once, without emission, only
as the retained T660 digital event/recording-marker cadence across the
PicoScope and HF2LI DIO timestamps; leave stream endurance and optical-event
reconciliation to HF-02 and FE-01 respectively.

Qualify exactly three experiment-specific retained configurations across two
topologies: the probe-only continuous-sweep configuration used by
polystyrene/Mylar, an HRP-C-CO fixed-wavenumber/rare-pump configuration sized
for the longest retained HRP recovery, and an MbCO fixed-wavenumber/rare-pump
configuration sized for the fastest retained MbCO dynamics. Select acquisition
rate, time constant, filter order, phase, ranges, and record length separately
for each configuration against frozen temporal-bandwidth, settling/bias,
noise/SNR, clipping, loss, and data-volume criteria. The CH-00 settings and
repository presets are qualification seeds, not accepted values. A common
numeric setting may be retained for HRP-C-CO and MbCO only after measured
equivalence demonstrates that it satisfies both sets of criteria; even then,
retain separate configuration IDs with an explicit alias/equivalence record.
For each selected configuration, verify reference lock/readback, demodulator
assignments, model-predicted filter transfer and effective noise bandwidth,
used ranges, clipping margin, and one reload equivalence. Add a challenger only
under the ambiguity rule in the HF-01 AWG design; add a fourth model anchor only
after a predeclared model-residual failure.

Mandatory closeout deliverables: the complete evidence package required by the
HF-01 AWG design, complete node snapshots and reload diffs, reference-frequency
comparison, native monitored-stimulus and HF2LI records, analytical candidate-
disposition table, three-anchor model validation, complex filter/step/noise/
range/rate/selected-setting channel-equivalence results, uncertainty/acceptance
table, and three restorable experiment-specific
approved configuration IDs (or separate biological IDs supported by an
explicit equivalence alias).

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
