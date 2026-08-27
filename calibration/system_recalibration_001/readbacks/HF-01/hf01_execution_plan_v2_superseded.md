# HF-01 governing execution plan (superseded v2)

Plan version: `HF01-PLAN-v2`  
Authorization: `HF01-AUTH-001` with `HF01-AUTH-AMEND-005`

## Objective and boundary

HF-01 characterizes the installed HF2LI electrically, validates its supported
cascaded-filter response model at three sparse instrument anchors, evaluates
the supported configuration space computationally, selects separate sweep,
HRP-C-CO, and MbCO configurations, physically confirms only those selections,
checks Signal Input 2 equivalence, and restores the default wiring.

HF-01 remains non-emitting. Laser arming, firing, optical emission, shutter
opening, optical alignment, sample work, biological work, later campaign
phases, and canonical calibration promotion are prohibited.

## Installed topology

- `CLOCK-SPLITTER-01` remains unchanged. T660-2 CLOCK OUT feeds the splitter;
  its branches continue to T660-1 CLOCK and HF2LI CLOCK.
- PicoScope AWG -> `HF01-STIMULUS-TEE-01` -> `RG58-01` -> HF2LI Signal Input 1.
- The second tee arm -> `RG58-02` -> PicoScope channel A.
- T660-2 A -> HF2LI DIO0 continuous reference; B -> PicoScope channel B.
- T660-2 C -> HF2LI DIO1; D -> PicoScope EXT for the bounded timing-copy check.
- No HF-01 output reaches MIRcat, T660-1 timing inputs, or a laser controller.

## Response validation

The three primary anchors and all acceptance rules are defined in
`validation_point_declaration.md` and `model_residual_criteria.md`.

Demodulator 0 carries the test filter. Demodulator 1 is a minimum-time-constant
reference using the same HF2LI input, oscillator, harmonic, device clock, and
sample grid. Timestamp-aligned complex division identifies the filter response
without cross-instrument phase ambiguity. PicoScope measurements remain the
connected-voltage and clipping authority.

The manufacturer model must pass all three anchors before any supported-setting
enumeration begins. Rejected acquisitions are repeated only at the identical
declared setting and receive new stable IDs. No model point is selected from
observed residuals.

## Computational selection and confirmation

After model acceptance, every supported combination of input mode, range,
filter order, installed time constant, and installed output rate is evaluated
for the three experiment cases. The candidate table propagates attenuation,
shape or lifetime bias, phase and delay, settling memory, noise bandwidth,
sampling, clipping headroom, throughput, record duration, data volume, and
validated-model uncertainty.

One configuration ID is retained for each experiment even when numeric settings
are identical. A boundary challenger is allowed only under the frozen ambiguity
rule. Physical work then confirms only the selected configurations, the selected
rate versus the immediately lower installed rate, any invoked challenger, and
Signal Input 2 equivalence.

## Restoration and closeout

Before restoration, the AWG and temporary T660 outputs are disabled. Temporary
wiring is removed under operator observation, `CLOCK-SPLITTER-01` remains
unchanged, default T660/MIRcat wiring is restored, and final device readbacks
confirm safe idle. HF-01 closes only after the mandatory artifact, acquisition,
condition, measurement, exclusion, calibration-link, uncertainty, limitation,
reload-equivalence, restoration, and revalidation-trigger records are complete.
