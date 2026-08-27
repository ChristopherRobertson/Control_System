# HF-01 final report

Campaign: `system_recalibration_001`  
Phase run: `system_recalibration_001_HF-01_001`  
Governing plan: `HF01-PLAN-v3`  
Final phase decision: **PASS with an explicit MbCO applicability limitation**

## Scope and boundary

HF-01 completed the non-optical electrical characterization of HF2LI
`dev18500` using the monitored PicoScope 5244D generator and T660 timing
copies. Lasers remained in the operator-confirmed nonemitting state and
shutters remained closed. The phase made no detector, optical, chemical,
biological, later-phase, or canonical-promotion claim.

The manifest uses schema status `PASS` because the authorized electrical
characterization, model validation, configuration selection, confirmation,
reload, and restoration all completed. This does not convert the MbCO
limitation into a pass: the retained MbCO ID is explicitly outside the
mandatory 1 us envelope.

## Completed work

### Timing and reference integrity

The accepted nonemitting 10 Hz timing-copy record is
`HF01-TIMING10-R5-001` under `HF01-TIMING-COPY-v3`. It retained the required
T660/PicoScope/HF2LI DIO evidence. `CLOCK-SPLITTER-01` remained in its normal
T660-2-to-T660-1/HF2LI 10 MHz distribution. A bounded electronic recovery
returned T660-1 to its external-clock input and established T660-1 and HF2LI
lock without a physical splitter change.

The retained HF2LI external reference is the T660-2 channel-A DIO0 route. A
bounded analog-reference diagnostic did not lock and is preserved as rejected
diagnostic evidence rather than silently omitted.

### Manufacturer-model validation

Exactly three sparse paired-demodulator primary anchors were accepted under
`HF01-MODEL-RESIDUAL-v3`:

| Anchor | Accepted acquisition | Order | Time constant | Rate | Corrected complex RMS residual | Decision |
|---|---|---:|---:|---:|---:|---|
| Fast | `HF01-ANCHOR-FAST-V3-001` | 1 | 4.000020 us | 230263.158 Sa/s | 0.00005360 | PASS |
| Intermediate | `HF01-ANCHOR-INTERMEDIATE-V3-001` | 4 | 1.001889 ms | 899.465 Sa/s | 0.00024149 | PASS |
| Slow | `HF01-ANCHOR-SLOW-V3-R1-001` | 8 | 71.1531 ms | 112.433 Sa/s | 0.01767391 | PASS |

The first v3 slow record is retained as rejected because one rising transition
exceeded the prospective 120% settling limit. The authorized identical-setting
repeat passed. No fourth anchor or physical parameter grid was run. Earlier v1
and v2 records remain preserved as rejected, diagnostic, or superseded evidence.

The accepted analysis used exact overlapping HF2LI timestamps, a synchronized
wideband reference demodulator, explicit reference-filter restoration, and one
zero-intercept paired-pipeline delay bounded below a native sample interval.
Magnitude, phase, complex RMS, cutoff, step/settling, group-delay, noise,
positive/negative cutoff-pair, clipping, loss, lock, and final-idle criteria all
passed for the three primary anchors.

### Complete supported-space evaluation

`HF01-HF2-SUPPORTED-SPACE-001` retained the installed parameter domain:

- 11 input ranges;
- eight filter orders;
- eight input modes;
- three readout modes;
- 21 dual-channel rates from 230263.1579 to 0.219596 Sa/s; and
- the complete writable time-constant interval from 0.7831859 us to 582.888 s.

`HF01-ANALYSIS-SUPPORTED-CONFIGURATIONS-001` evaluated 133,056 discrete
candidate rows while retaining the continuous time-constant interval
analytically. It did not use a physical parameter grid. No ambiguity challenger
was invoked because the retained decisions were unique under the frozen rules.

### Restorable configuration outputs

| Configuration ID | Order | Time constant readback | Rate | Disposition |
|---|---:|---:|---:|---|
| `HF01-SWEEP-SELECTED-001` | 4 | 1.001888708 ms | 899.465461 Sa/s | Selected within the electrical scan-response envelope; AR-01 retains final optical distortion authority. |
| `HF01-HRP-SELECTED-001` | 4 | 1.001888708 ms | 899.465461 Sa/s | Explicit numeric alias of the sweep setting with a distinct HRP validity envelope. |
| `HF01-MBCO-SELECTED-001` | 1 | 5.600017468 us | 230263.157895 Sa/s | Fastest valid two-channel boundary configuration; invalid for the mandatory 1 us claim. |

All use a nominal 1 V range, DC coupling, high impedance, single-ended input,
continuous timestamped XY plus full DIO, external 10 MHz master clock, and DIO0
reference. The nominal 1 V range is the smallest installed range above twice
the prior documented 0.4651 V detector maximum. DET-01/DET-02 remain responsible
for installed detector noise and clipping qualification.

### Selected-setting confirmation

The sweep/HRP selected rate-to-cutoff ratio was 13.017; its immediately lower
rate gave 6.509 and was rejected against the required minimum of 8. The MbCO
boundary ratio was 8.102; its immediately lower rate gave 4.051 and was
rejected. All accepted records had lock, clipping, loss, source-voltage, and
safe-idle guards.

Signal Input 2 equivalence passed for both selected numeric settings. The
largest sweep/HRP inter-input differences were 0.0117% gain, 0.0678 degrees
phase, 0.0879% cutoff, 0.571% settling, and 7.14% zero noise. MbCO differences
were smaller except for a 1.85% settling difference, still below the 5% limit.
The Input 2 connected endpoints measured 0.0103726 and 0.101189 Vpp; their
ratio was within 2.446% of the expected 10x and no clipping or loss occurred.

`HF01-CONFIG-RELOAD-001` loaded every restorable ID twice. Integer nodes
matched exactly and every observed double-node relative difference was zero.
The pre-HF-01 HF2LI configuration was then restored exactly.

## Hard MbCO limitation

No supported HF2LI two-channel configuration preserves the mandatory 1 us
MbCO feature. At the fastest valid boundary, the stream contains only
0.230263 sample per 1 us and the manufacturer-model response is attenuated by
82.420989%, leaving 17.579011% magnitude. The boundary configuration may be
used only when that limitation is explicit and the scientific claim is
changed or another acquisition path supplies the required bandwidth. Repeating
HF-01 at another supported HF2LI setting cannot resolve this limitation.

## Uncertainty, ambiguity, and downstream validity

The machine-readable acceptance table is
`tables/hf01_uncertainty_acceptance.csv`. The uncertainty record includes
stimulus measurement, repeatability, manufacturer-model residual, paired-
pipeline delay, setting quantization/readback, channel equivalence, range
endpoint behavior, PicoScope timing/voltage terms, loading, and drift limits.
Where detector noise or biological tolerances were not frozen, HF-01 reports a
validity envelope rather than inventing a numerical target.

Sweep feature-width/distortion acceptance remains with AR-01. HRP's fastest
accepted early feature, precision, and maximum duration remain downstream
requirements. Detector phases must establish the installed detector voltage
and noise interval. `revalidation_triggers.md` defines changes that invalidate
or require checking the provisional electrical bundle.

## Restoration and closeout

The operator confirmed default wiring in `HF01-OPCONF-014`. T660-2 B is
restored to MIRcat `TRIG IN`; T660-2 D is restored to T660-1 `TRIG IN`;
T660-2 A and C remain at HF2LI DIO0/DIO1; `CLOCK-SPLITTER-01` remains in normal
distribution; and the temporary stimulus assembly and spare tee are
disconnected from instruments. Standing default exclusions were imported from
`docs/default_wiring_state.md`.

`HF01-FINAL-RESTORATION-STATE-R1-001` passed after one preserved COM3-
contention attempt. The accepted record confirms T660 safe idle, PicoScope AWG
programmed zero, all 25 retained HF2LI prechange nodes matched, external-clock
selection and lock, HF2LI outputs off, and no ADC clipping or demodulator sample
loss. Photographs were declined by the operator and are recorded as deviation
`HF01-DEV-001`; no photograph is fabricated or inferred.

All 42 attempted acquisitions are indexed, including accepted, rejected,
diagnostic, partial, and superseded records. The retention audit passed. No
later phase was executed and no canonical promotion occurred.
