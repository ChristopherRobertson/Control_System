# HF-01 governing execution plan

Plan version: `HF01-PLAN-v3`  
Authorization: `HF01-AUTH-001` with `HF01-AUTH-AMEND-005`

## Objective and boundary

HF-01 electrically validates the installed HF2LI cascaded-filter model at three
sparse anchors, evaluates the supported configuration space computationally,
selects separate sweep, HRP-C-CO, and MbCO configurations, confirms only those
selections, checks Signal Input 2 equivalence, and restores default wiring.

HF-01 remains non-emitting. Laser arming, firing, emission, shutter opening,
optical alignment, sample or biological work, later phases, and calibration
promotion are prohibited.

## Installed topology

- `CLOCK-SPLITTER-01` is unchanged: T660-2 CLOCK OUT feeds T660-1 CLOCK and the
  HF2LI CLOCK input.
- PicoScope AWG -> `HF01-STIMULUS-TEE-01` -> `RG58-01` -> HF2LI Signal Input 1.
- Second tee arm -> `RG58-02` -> PicoScope channel A.
- T660-2 A -> HF2LI DIO0; B -> PicoScope B; C -> HF2LI DIO1; D -> PicoScope EXT.
- No HF-01 output reaches MIRcat, T660-1 timing inputs, or a laser controller.

## Response validation

`validation_point_declaration.md` and `model_residual_criteria.md` define the
three anchors and all acceptance rules. Demodulator 0 carries the test filter;
demodulator 1 supplies the same-clock wideband reference. Reference magnitude
identifies connected intervals. Exact common timestamps supply complex ratios.
The explicit reference transfer and a single bounded constant paired-pipeline
delay produce magnitude, phase, cutoff, step, and group-delay evidence without
using a host-clock phase relation.

All three anchors must pass before supported-setting enumeration. Rejected
records remain preserved and a same-setting replacement receives a new stable
ID. No model point is selected from observed residuals.

## Computational selection and confirmation

After model acceptance, every supported combination of input mode, range,
filter order, installed time constant, and installed rate is evaluated for the
three experiment cases. The candidate table propagates attenuation, shape or
lifetime bias, phase and delay, settling memory, noise bandwidth, sampling,
clipping headroom, throughput, duration, data volume, and validated-model
uncertainty. One configuration ID is retained per experiment. Physical work
then confirms only selected configurations, the immediately lower installed
rate, any invoked boundary challenger, and Signal Input 2 equivalence.

## Restoration and closeout

AWG and temporary T660 outputs are disabled before operator-observed removal of
the tee and cables. `CLOCK-SPLITTER-01` remains unchanged, default wiring is
restored, and final readbacks confirm safe idle. Closure requires all phase
indexes, uncertainty, limitations, reload-equivalence, restoration, and
revalidation-trigger records to be complete.
