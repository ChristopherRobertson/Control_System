# Timing Calibration Prehardware Review Procedure

Status: **review plan only — not approved for hardware execution**

This document defines the complete, rerunnable timing-calibration procedure for the pump-probe control system. Creating or reviewing this document does not open hardware, enable a T660 output, move a cable, acquire a trace, update shared calibration files, or update an RSI paper/thesis draft. Hardware execution must remain blocked until the wiring, pinout, trigger-rate, laser-safety, and correction-model review checklist at the end of this document is approved.

## 1. System timing topology

The procedure uses this final-system topology:

| Source | Final destination |
|---|---|
| T660-2 CHA | HF2LI DIO0 EXT REF |
| T660-2 CHB | MIRcat TRIG IN |
| T660-2 CHC | HF2LI DIO1 DAQ trigger |
| T660-2 CHD | T660-1 TRIG IN |
| T660-1 CHA | Nd:YAG FIRE, DB9 EXT pin 7 |
| T660-1 CHB | Nd:YAG Q-switch, DB9 EXT pin 6 |
| T660-1 CHC | MIRcat Process Trigger, DB9 pin 4 |
| T660-1 CHD | MIRcat Laser On/Off, DB9 pin 5 |

The PicoScope uses CHA as the recorded reference channel and CHB as the recorded target channel. The measured sign is always

```text
d_raw = t_Pico_CHB - t_Pico_CHA
```

so a positive value means that the CHB event was recorded later than the CHA event.

The Arduino MUX is not part of this procedure. All timing measurements use direct cables, an approved DB9 breakout/adapter where needed, and the splitter only where this document explicitly calls for it.

## 2. Time-zero definitions

Two time origins must remain distinct in plans, raw data, analysis, tables, and thesis language:

- `t_master = 0` is the first programmed T660-2 timing event in a recipe. It is a programming origin, not automatically the arrival time at the end of a cable.
- `t_chem = 0` is arrival of the optical pump/OPO pulse at the sample or a sample-equivalent optical plane.

Most electrical measurements below use the arrival of the T660-2 CHA pulse at the destination end of the final HF2LI EXT REF cable as their physical reference. That event is a physical realization of the master reference, but it is not an absolute measurement of the delay from the T660-2 internal programming origin to the cable destination. Results referenced to this cable-end event must be labeled `HF2LI EXT REF arrival -> ...`, not unqualified `absolute delay from t_master`.

Step 7 connects the Q-switch electrical event to `t_chem = 0`. A value relative to `t_master` may be derived only by combining compatible, corrected measurements and stating every term used.

## 3. Common acquisition rules

### 3.1 Trigger rates

- Steps 0a, 0b, 0c, 1, 2, and 3 are direct T660-2 electrical measurements and use a **100 Hz** T660-2 synthesizer rate.
- T660-1 electrical Steps 4, 5, 6, 8, and 9 use a **10 Hz** T660-2 trigger into T660-1. Step 7 uses one-shot T660-2 `REM` triggers with a shared minimum 0.1 s interval across the blocked-control, preview, and measurement phases, so its effective rate is bounded at **10 Hz or lower** even at phase boundaries.
- A recipe must explicitly program and read back the applicable rate. It must never inherit the previously active synthesizer rate.
- The 10 Hz period prevents the 1 ms programmed delay from being confused with a later trigger and is also the maximum planned rate for the optical safety step.

### 3.2 Programmed-delay sweeps and exceptions

Unless a step is explicitly excepted below, an electrical programmed-delay sweep uses

```text
0 ns, 100 ns, 1 us, 10 us, 100 us, 1 ms
```

with 100 accepted shots per delay. The PicoScope capture window must be selected automatically for each delay and must include the reference edge, the expected target edge, and a validated post-target margin. A 1 ms point is part of the same step, not a separate run.

The only planned sweep exceptions are:

- Steps 0a, 0b, and 0c: no programmed-delay sweep is useful because both scope channels observe the same split test pulse. Acquire at least 100 accepted pulses in each orientation/geometry at 100 Hz.
- Step 7: use one approved Nd:YAG/OPO operating FIRE-to-Q-switch timing in bounded remote-trigger (`REM`) mode. Sweeping the Q-switch command would move both the electrical reference and the resulting optical pulse and would add laser exposure without identifying an electrical delay scale. The frozen plan must state the requested measurement-shot count and the total emitted-shot budget. The default budget is one beam-blocked control shot, one real optical preview shot, and 100 measurement shots: 102 emitted shots total. A rejected preview or measurement trace blocks Step 7; it does not authorize an automatic extra emission. Any different count or retry allowance must be bounded explicitly in the reviewed plan and have a written rationale.

Steps 1 through 6, 8, and 9 use the complete six-point electrical sweep.

### 3.3 Cable and safe-state conventions

- `Final cable destination end` means the device-end connector is unplugged from its normal destination and connected to the stated PicoScope channel. Its T660 source end remains on the normal T660 output.
- The same channel-assigned PicoScope patch leads/adapters used in Step 0 must be retained for later electrical steps so the measured scope-path correction remains applicable.
- Every cable removed from a device must be labeled, capped or insulated as appropriate, and recorded in the run manifest.
- Before cable handling, both T660 units must be stopped, all channels disabled, and the disabled state read back.
- Before each step, the workflow must print the complete connections for that step and wait for a recorded operator confirmation. A command-line flag supplied at process startup is not a substitute for this per-step confirmation.
- Between steps and after any error, apply and verify safe idle before prompting for a cable change.
- A safe-idle application or readback failure is itself a blocking safety failure. The run must not report PASS, continue to another setup, or publish a consolidated result after such a failure. Record the failure, close acquisition devices where safe to do so, instruct the operator to verify the T660 outputs manually, and mark the run as requiring intervention.
- Only channels listed as enabled for a step may be enabled. Every other channel must be explicitly disabled in the recipe and confirmed by readback.
- The approved DB9 breakout/adapter pinout, voltage rating, grounding, loading, and termination must be verified before connecting a PicoScope input to any DB9 timing line.
- Scope grounds must not create a ground loop or short a device output. This must be reviewed against the laboratory wiring and instrument manuals before execution.

### 3.4 Frozen pre-run inputs

The generated run plan is the executable review record. Before the first hardware connection, it must freeze the following inputs and refuse execution if any content or setting changes:

- Absolute path and SHA-256 digest for `recipes/timing_calibration.yaml`, `recipes/safe_idle.yaml`, the selected PicoScope recipe, and the selected Step 7 optical recipe.
- Hardware-configuration hash, procedure schema version, source revision when available, and the SHA-256 digest of this review document.
- Parsed PicoScope resolution; CHA/CHB enabled state, range, coupling, and offset; trigger source, edge, and threshold; base timebase/sample count; electrical threshold; Step 7 photodetector edge, threshold, saturation limit, and signal-to-noise criterion.
- Exact optical FIRE and Q-switch delays, widths, polarities, terminations, T660-1 external-trigger settings, T660-2 `REM` source, explicitly disabled unused channels, the minimum interval between every pair of remote shots, and the reviewed minimum/maximum Q-switch-to-OPO edge-search window.
- Resolved electrical step-recipe settings for every unit/channel (enabled state, signal, delay rule, width, polarity, termination, trigger source/rate, predivider/gate/burst/frames state). Store a deterministic digest of the resolved recipe template in the plan and a digest of each generated per-delay recipe in the run record.
- Photodetector response-delay correction, standard uncertainty, calibration source/identifier/date, detector and cable identifiers, and the sample or sample-equivalent placement record.
- Step 0 cable/adapter identifiers, the Step 0c load-equivalence method and evidence, and any independently supplied cable or path-length uncertainty.
- Requested electrical shots per delay, Step 7 control/preview/measurement counts, permitted retry count, and the resulting maximum emitted-shot budget.

A path without a content digest is not frozen. Numeric detector corrections such as `0 ns` or `0 ns uncertainty` require the same traceable calibration provenance as any nonzero value; entering zero is not evidence that the term is negligible. Inputs that the workflow cannot measure—such as detector calibration, sample-equivalent path uncertainty, connector/load equivalence, and manufacturer timing specifications—must be supplied before execution or carried explicitly as unresolved terms. The final table must say `not evaluated` or `not available` for an unresolved contribution rather than implying it is included in a combined uncertainty.

### 3.5 Mandatory safe-idle cable transitions

Every operator prompt must be standalone: it must describe both the final setup and how to leave the preceding setup. At minimum, perform and print these transitions after a successful safe-idle readback:

| Transition | Required cable action while safe-idled |
|---|---|
| Initial state -> 0a | Remove the final EXT REF cable from T660-2 CHA at the source, park/cap it, and install the dedicated CHA-to-splitter test lead. Leave T660-2 CHB/CHC/CHD final device cables connected but verified disabled. |
| 0a -> 0b | Swap only splitter outputs 1 and 2; keep `E_A` assigned to Pico CHA and `E_B` assigned to Pico CHB. |
| 0b -> 0c | Keep the test-pulse splitter input. Install the final Q-switch cable and exact Step 7 monitor lead in the load-equivalent 0c arrangement; neither branch may reach an enabled laser input. |
| 0c -> 1 | Remove the splitter and test lead, restore the final EXT REF cable to T660-2 CHA at its source, route its disconnected HF2LI destination end to Pico CHA, route the final DAQ destination end to Pico CHB, and park/cap the Q-switch cable away from the laser. |
| 1 -> 2 | Reconnect the final DAQ cable to HF2LI DIO1 with CHC disabled. Keep the EXT REF destination on Pico CHA and move Pico CHB to the disconnected MIRcat TRIG IN destination cable. |
| 2 -> 3 | Reconnect the MIRcat trigger destination with CHB disabled. Keep EXT REF on Pico CHA; disconnect the T660-1 TRIG IN destination and move that final CHD cable end to Pico CHB. |
| 3 -> 4 | Remove CHD from Pico CHB and reconnect it to T660-1 TRIG IN. Keep EXT REF on Pico CHA; disconnect the Nd:YAG timing connector and route FIRE pin 7 to Pico CHB through the approved breakout. |
| 4 -> 5 | Park or restore the disabled EXT REF destination as specified in the frozen plan. Move FIRE pin 7 from Pico CHB to Pico CHA and route the disconnected Q-switch pin 6 to Pico CHB. CHD remains connected to T660-1. |
| 5 -> 6 | Park/cap FIRE pin 7. Route the disconnected EXT REF destination back to Pico CHA; keep disconnected Q-switch pin 6 on Pico CHB. CHD remains connected to T660-1. |
| 6 -> 7 | Remove all electrical-only DB9 scope connections. Restore FIRE to Nd:YAG pin 7, insert the characterized splitter between T660-1 CHB and the final Q-switch cable, connect output 1 to actual pin 6 and output 2 through `E_A` to Pico CHA, and connect the attenuated sample-plane detector through `E_B` to Pico CHB. |
| 7 -> 8 | Verify safe idle, remove the splitter and photodetector acquisition leads, disconnect the Nd:YAG and MIRcat timing connectors for electrical probing, route FIRE pin 7 to Pico CHA, and route MIRcat Process Trigger pin 4 to Pico CHB. No splitter branch remains connected. |
| 8 -> 9 | Keep FIRE pin 7 on Pico CHA and move Pico CHB from Process Trigger pin 4 to Laser On/Off pin 5; both device connectors remain disconnected. |
| 9 -> final state | Apply and verify final safe idle before removing scope leads. Restore final device cables only under the approved shutdown/restoration checklist; do not enable any output as part of restoration. |

If the physical harness does not permit one of these actions exactly as written, stop during review and replace it with an equally explicit, pin-verified breakout procedure before hardware execution.

## 4. Measurement-system correction

Steps 0a, 0b, and 0c characterize the differential PicoScope acquisition path, bare splitter branch skew, and installed Step 7 splitter/lead geometry. These are measurement-system corrections, not system route delays.

For all three Step 0 setups, disconnect the final HF2LI EXT REF cable from T660-2 CHA and park/cap it. Connect T660-2 CHA to the splitter input with a dedicated short test lead. Program only T660-2 CHA at 100 Hz; T660-2 CHB, CHC, and CHD and every T660-1 channel remain disabled. The final T660-2 CHB, CHC, and CHD cables may remain physically connected to their devices only because their source channels are disabled and verified off.

Use two known short/nominally equal, labeled scope measurement assemblies, `E_A` assigned permanently to Pico CHA and `E_B` assigned permanently to Pico CHB. Each assembly includes every measurement-only adapter/probe between the stated event reference plane and its Pico input; in particular, the approved pin-6 adapter used in Step 0c belongs to `E_A` and must also be present in the 0a/0b characterization through the matching test adapter arrangement. Do not exchange these channel-assigned assemblies between setups.

### Step 0a — normal splitter orientation

**Purpose:** first observation needed to separate channel/path skew from splitter branch skew.

- Splitter input: T660-2 CHA test pulse.
- Splitter output 1 -> cable `E_A` -> PicoScope CHA.
- Splitter output 2 -> cable `E_B` -> PicoScope CHB.
- Remains connected to actual devices: T660-2 CHB -> MIRcat TRIG IN, T660-2 CHC -> HF2LI DAQ, and T660-2 CHD -> T660-1 TRIG IN may remain physically connected, but all three outputs are explicitly disabled. No T660-1 output is enabled.
- Disconnected: T660-2 CHA final EXT REF cable; no splitter output is connected to a final-system device.
- Operator confirmation: verify the branch labels, `E_A`/`E_B` labels, 100 Hz readback, scope ranges/termination, and that no laser-driving output is enabled.

Record the mean corrected-edge observation as `M_0a`, using the raw CHB-minus-CHA sign.

### Step 0b — swapped splitter branches

**Purpose:** isolate the two correction terms without changing the PicoScope channel-assigned paths.

- Splitter input: unchanged T660-2 CHA test pulse.
- Splitter output 2 -> cable `E_A` -> PicoScope CHA.
- Splitter output 1 -> cable `E_B` -> PicoScope CHB.
- Remains connected and disabled: identical to Step 0a.
- Disconnected: identical to Step 0a.
- Operator confirmation: verify that only the splitter outputs were swapped; `E_A` still terminates at CHA and `E_B` still terminates at CHB.

Record the mean observation as `M_0b`.

Define

```text
C_scope = (M_0a + M_0b) / 2
S_21    = (M_0a - M_0b) / 2
```

where:

- `C_scope` is the CHB-minus-CHA differential acquisition-path delay, including Pico channel skew and any residual skew in the fixed channel-assigned equal patch leads. A positive `C_scope` means the measurement system records CHB late.
- `S_21 = delay(splitter output 2) - delay(splitter output 1)`. A positive `S_21` means splitter output 2 is later.

### Step 0c — exact installed Step 7 splitter geometry

**Purpose:** measure the splitter together with the unequal, temporary branch leads that will actually be installed during Step 7.

- Splitter input: unchanged T660-2 CHA test pulse.
- Disconnect the final Q-switch cable from T660-1 CHB and from Nd:YAG DB9 pin 6. Connect splitter output 1 -> the source end of that final Q-switch cable -> the same approved pin-6/`E_A` measurement assembly used during the Step 0 scope-path characterization -> PicoScope CHA.
- Splitter output 2 -> the exact Step 7 monitor adapter/lead -> cable `E_B` -> PicoScope CHB.
- The Q-switch cable is disconnected from Nd:YAG; no laser-driving output is enabled.
- Operator confirmation: verify the final Q-switch cable and exact monitor lead are installed, the reviewed load-equivalence method/source ID matches the frozen plan, and no test pulse can produce laser emission.

The output-1 load in Step 0c must be electrically equivalent, over the edge bandwidth used for timing, to the actual Nd:YAG pin-6 input load present in Step 7. A PicoScope input is not assumed equivalent merely because both inputs are described as high impedance. Before approval, choose and document one of these methods:

- Use a characterized dummy termination/network whose impedance and connector geometry reproduce the Nd:YAG Q-switch input, and probe the pin-6 reference plane with an approved high-impedance timing probe; or
- Use an approved DB9 breakout that leaves the real pin-6 load connected while the laser is positively inhibited from emission, and observe the reference plane with a probe whose added loading is demonstrated negligible; or
- Provide authoritative impedance/bandwidth data showing that the Step 0c Pico/adapter substitution is equivalent within a stated timing uncertainty.

Record the selected method, Nd:YAG input-load source, nominal impedance/capacitance, Pico/probe input impedance, adapter and cable identifiers, setup photograph or connection record, and the assigned load-equivalence timing uncertainty. If equivalence is not demonstrated, `S_installed` is provisional and Step 7 must not be reported as a corrected Q-switch-pin-6-to-optical delay.

Record the raw CHB-minus-CHA mean as `M_0c`. Define the installed branch geometry

```text
S_installed = M_0c - C_scope
```

where `S_installed` is delay(splitter output 2 plus the Step 7 monitor lead) minus delay(splitter output 1 plus the final Q-switch cable to the DB9 pin-6 reference plane), under the documented load-equivalent condition. This run-local measurement replaces any visual cable-length assumption. Keep `S_21` as the separately reported bare-splitter diagnostic required to identify whether the splitter itself or the unequal installed leads dominate the temporary geometry.

For a direct two-channel measurement with no splitter in either measured route, apply

```text
d_corrected = d_raw - C_scope
```

The final route cables are part of the desired physical route and are not subtracted. Only characterized measurement-only adapters/leads are corrections.

If a future measurement sends splitter output 1 to CHA and output 2 to CHB, its splitter contribution is `+S_21` in `d_raw` and the general correction is

```text
d_corrected = d_raw - C_scope - S_21
```

Reverse the sign of the splitter term if the two splitter branches are reversed. Step 7 has a different geometry and therefore uses the explicit Step 7 formula in Section 7.

## 5. Direct T660-2 electrical routes

Apply safe idle before each connection change. For Steps 1–3, use 100 Hz and the complete six-point sweep. T660-1 remains stopped with all outputs disabled.

### Step 1 — HF2LI EXT REF to HF2LI DAQ relative timing

**Category:** relative route offset.

- PicoScope CHA: destination end of the final T660-2 CHA -> HF2LI DIO0 EXT REF cable.
- PicoScope CHB: destination end of the final T660-2 CHC -> HF2LI DIO1 DAQ-trigger cable.
- Remains connected to actual devices: T660-2 CHB final cable remains at MIRcat TRIG IN and T660-2 CHD final cable remains at T660-1 TRIG IN; both channels are explicitly disabled. All T660-1 outputs remain disabled.
- Disconnected: both measured destination ends are disconnected from the HF2LI for this step.
- Enabled: T660-2 CHA at programmed delay 0 and T660-2 CHC at the swept delay.
- Operator confirmation: identify both HF2LI cable labels and confirm that neither scope lead is connected to an HF2LI output or Arduino MUX route.

Report this as a corrected relative arrival mismatch. Do not label it an absolute DAQ-route delay.

### Step 2 — HF2LI EXT REF to MIRcat TRIG IN relative timing

**Category:** relative route offset.

- PicoScope CHA: destination end of the final T660-2 CHA -> HF2LI DIO0 EXT REF cable.
- PicoScope CHB: destination end of the final T660-2 CHB -> MIRcat TRIG IN cable.
- Remains connected to actual devices: T660-2 CHC final cable remains at HF2LI DIO1 DAQ and T660-2 CHD final cable remains at T660-1 TRIG IN; both outputs are explicitly disabled. All T660-1 outputs remain disabled.
- Disconnected: the measured CHA cable end is disconnected from HF2LI DIO0; the measured CHB cable end is disconnected from MIRcat TRIG IN.
- Enabled: T660-2 CHA at programmed delay 0 and T660-2 CHB at the swept delay.
- Operator confirmation: confirm MIRcat TRIG IN is physically disconnected from the measured cable and no MIRcat DB9 control line is enabled.

Report this as `HF2LI EXT REF arrival -> MIRcat TRIG IN arrival`, not a generic QCL delay.

### Step 3 — HF2LI EXT REF to T660-1 TRIG IN relative timing

**Category:** relative route offset.

- PicoScope CHA: destination end of the final T660-2 CHA -> HF2LI DIO0 EXT REF cable.
- PicoScope CHB: destination end of the final T660-2 CHD -> T660-1 TRIG IN cable.
- Remains connected to actual devices: T660-2 CHB final cable remains at MIRcat TRIG IN and T660-2 CHC final cable remains at HF2LI DIO1 DAQ; both outputs are explicitly disabled.
- Disconnected: the measured CHA cable end is disconnected from HF2LI DIO0 and the measured CHB cable end is disconnected from T660-1 TRIG IN. T660-1 therefore receives no trigger.
- Enabled: T660-2 CHA at programmed delay 0 and T660-2 CHD at the swept delay.
- Operator confirmation: confirm T660-1 TRIG IN is empty and every T660-1 output is disabled.

This is a final-cable relative route measurement, not merely a bare T660-2 channel-skew diagnostic.

## 6. T660-1 electrical-chain measurements

Steps 4, 5, 6, 8, and 9 are electrical-only measurements. Use 10 Hz and the complete six-point sweep. The Nd:YAG must be incapable of firing: its FIRE and Q-switch destination connections are removed whenever those lines are measured or could otherwise be energized. MIRcat DB9 destination lines under measurement are likewise removed from the MIRcat. A disabled-channel readback alone does not replace the required physical disconnection of a laser-driving destination during these electrical-only steps.

Use the proven operational active-negative 10 us polarity/width for Nd:YAG FIRE and Q-switch outputs and analyze their falling edges. Use positive diagnostic pulses for the MIRcat DB9 process-control outputs unless the approved final MIRcat recipe specifies another polarity; record the selected polarity in every readback. This keeps the measured Nd:YAG electrical paths representative of the actual laser recipe without connecting them to the laser during Steps 4–6, 8, and 9.

### Step 4 — HF2LI EXT REF to Nd:YAG FIRE electrical arrival

**Category:** cross-device timing-chain latency.

- PicoScope CHA: destination end of the final T660-2 CHA -> HF2LI DIO0 EXT REF cable.
- PicoScope CHB: destination end/approved breakout for the final T660-1 CHA -> Nd:YAG FIRE DB9 pin 7 line.
- Remains connected to actual devices: T660-2 CHD final cable remains connected to T660-1 TRIG IN.
- Disconnected: T660-2 CHA destination is removed from HF2LI DIO0; FIRE is removed from Nd:YAG DB9 pin 7 and routed to Pico CHB. Q-switch pin 6 is disconnected/capped. T660-1 CHC and CHD device-end connections are disconnected/capped for the electrical-only setup.
- Enabled: T660-2 CHA at programmed delay 0, T660-2 CHD as the 10 Hz T660-1 trigger, and T660-1 CHA at the swept delay. Every other output is disabled.
- Operator confirmation: verify 10 Hz, the CHD trigger-chain connection, FIRE pin 7 identity, Q-switch physical disconnection, and Nd:YAG non-emitting state.

This is the corrected physical delay from EXT REF final-cable arrival to FIRE pin-7-line arrival. Keep its cross-device classification distinct from Step 3's relative input-route offset.

### Step 5 — Nd:YAG FIRE to Q-switch electrical arrival

**Category:** FIRE-to-Q-switch electrical timing.

- PicoScope CHA: destination end/approved breakout for T660-1 CHA -> Nd:YAG FIRE DB9 pin 7.
- PicoScope CHB: destination end/approved breakout for T660-1 CHB -> Nd:YAG Q-switch DB9 pin 6.
- Remains connected to actual devices: T660-2 CHD final cable remains connected to T660-1 TRIG IN.
- Disconnected: FIRE pin 7 and Q-switch pin 6 are both disconnected from the Nd:YAG and routed to the PicoScope. T660-1 CHC and CHD device-end lines remain disconnected/capped.
- Enabled: T660-2 CHD at 10 Hz, T660-1 CHA at programmed delay 0, and T660-1 CHB at the swept delay. All other outputs are disabled.
- Operator confirmation: independently identify DB9 pins 7 and 6 and confirm that neither line reaches the Nd:YAG during this electrical sweep.

The corrected intercept is the fixed FIRE-to-Q-switch electrical timing term. The fitted ppm term remains a delay-scale diagnostic, not a cable delay.

### Step 6 — HF2LI EXT REF to Q-switch electrical arrival validation

**Category:** derived-chain validation.

- PicoScope CHA: destination end of the final T660-2 CHA -> HF2LI DIO0 EXT REF cable.
- PicoScope CHB: destination end/approved breakout for T660-1 CHB -> Nd:YAG Q-switch DB9 pin 6.
- Remains connected to actual devices: T660-2 CHD final cable remains connected to T660-1 TRIG IN.
- Disconnected: T660-2 CHA destination is removed from HF2LI DIO0; Q-switch pin 6 and FIRE pin 7 are disconnected from the Nd:YAG. T660-1 CHC and CHD device-end lines remain disconnected/capped.
- Enabled: T660-2 CHA at programmed delay 0, T660-2 CHD as the 10 Hz T660-1 trigger, and T660-1 CHB at the swept delay. T660-1 CHA, CHC, and CHD are disabled.
- Operator confirmation: verify 10 Hz, Q-switch pin 6 identity, FIRE disconnection, and that only the listed outputs are enabled.

Compare this direct corrected result with Step 4 plus Step 5; do not silently replace either result if the closure test fails.

## 7. Step 7 — Q-switch electrical arrival to optical OPO pulse at the sample

**Category:** optical pump-arrival delay connecting electrical timing to `t_chem = 0`.

This is the only step in this procedure that intentionally drives the Nd:YAG/OPO optical system. It requires a separate, immediate laser-safety confirmation after the cables are installed and before any laser-driving output is enabled.

### 7.1 Exact connection arrangement

- T660-2 CHD final cable remains connected to T660-1 TRIG IN.
- T660-1 CHA FIRE final cable remains connected to Nd:YAG FIRE DB9 pin 7.
- Insert the characterized splitter in the Q-switch path:
  - T660-1 CHB -> splitter input.
  - Splitter output 1 -> the final Q-switch cable -> Nd:YAG Q-switch DB9 pin 6. This branch remains connected to and drives the actual device.
  - Splitter output 2 -> any characterized extra adapter/lead -> the channel-assigned Step 0 cable `E_A` -> PicoScope CHA.
- Place the photodetector at the sample position or a documented sample-equivalent optical path length.
- Photodetector output -> its characterized detector cable/adapter -> the channel-assigned Step 0 cable `E_B` -> PicoScope CHB.
- T660-1 CHC and CHD are disabled; their MIRcat DB9 destination lines remain disconnected/capped.
- T660-2 CHA, CHB, and CHC are disabled unless an approved optical operating SOP explicitly requires an additional non-emitting reference. Any exception must be listed in the run plan and reviewed before execution.
- Use the approved operating FIRE/Q-switch widths and separation, not the generic 150 ns electrical-test pulse settings. During Step 7, each T660-2 remote shot sends one CHD trigger to T660-1; the controller enforces an effective rate of 10 Hz or lower.

The splitter is measurement apparatus and is not part of final wiring. Its installed branch skew must be removed algebraically; it must not be folded into the reported optical delay.

### 7.2 Mandatory laser-safety confirmation

Before enabling T660-1 CHA or CHB, the workflow must stop and require the operator to confirm and record all of the following:

- The operator is authorized under the applicable Nd:YAG/OPO laser SOP.
- Required eyewear, beam enclosures, interlocks, warning indicators, beam dumps, and controlled-area procedures are in place.
- The photodetector is rated for the OPO wavelength being measured (rated range: 200–1100 nm).
- The beam is strongly attenuated before the detector, the detector is at the sample/sample-equivalent plane, and no uncontained beam can leave the intended path.
- PicoScope input range, detector polarity, trigger threshold, and detector bias/power are correct.
- The frozen attenuation and detector settings are suitable for a bounded one-shot preview. No claim of an unsaturated preview is made before that preview is actually acquired under Section 7.3.
- The splitter orientation is output 1 to Q-switch pin 6 and output 2 to Pico CHA, matching the recorded correction sign.
- MIRcat laser-driving/process-control outputs remain disabled.

This first confirmation authorizes only the bounded beam-blocked control and preview sequence, not the 100-shot measurement set. It must be step-specific and timestamped, for example `LASER SAFETY READY STEP 7`, and recorded in the run manifest. If any item is not confirmed, apply safe idle and block the step.

### 7.3 Bounded REM control, preview, and measurement sequence

Step 7 must not run the optical recipe as a free-running 10 Hz train. Configure T660-2 in remote-trigger (`REM`) mode, T660-1 in external-trigger mode, and retain the approved operating FIRE/Q-switch delay. The controller may issue exactly one T660-2 remote trigger only after a PicoScope block is armed. Enforce at least 0.1 s between every pair of remote triggers with one shared monotonic deadline that survives the control/preview/measurement controller reopen boundaries.

Perform the following phases in order:

1. **Pre-emission safety gate.** Apply/verify safe idle, install the Step 7 wiring, place the beam block/dump in the reviewed control position, and record `LASER SAFETY READY STEP 7`. Configure the fully specified optical recipe in `REM`; all unused T660 channels remain explicitly off.
2. **Beam-blocked control: one emitted shot.** Reset/read the T660 elapsed-shot counters, arm one PicoScope block, issue exactly one remote trigger, and read the counters again. Preserve the trace as a control, separate from measurement statistics. The CHB waveform must establish the electrical-pickup/background envelope in the optical search window. If it crosses the proposed optical threshold or resembles the claimed optical edge, apply safe idle and block the run; do not relabel that edge as optical or automatically fire another shot.
3. **Transition to preview.** Apply and verify safe idle before moving the beam block. Put the strongly attenuated optical path into the reviewed sample/sample-equivalent configuration and obtain a second operator confirmation that the block position, attenuation, detector, and beam dump now match the preview setup.
4. **Real optical preview: one emitted shot.** Reconfigure the recipe in `REM`, arm one Pico block, issue one remote trigger, and verify both T660 shot counters. The preview must pass the saturation limit, signal-to-noise requirement, configured edge/polarity, optical search-window rule, and comparison against the beam-blocked control. Preserve the preview trace separately.
5. **Preview acceptance gate.** Apply and verify safe idle. Print the blocked-control and preview peak, baseline noise, threshold margin, edge time, and saturation metrics. Require a second explicit phrase such as `OPTICAL PREVIEW ACCEPTED STEP 7` before measurement acquisition. A failed or rejected preview ends Step 7 without an automatic replacement shot.
6. **Measurement set.** Reconfigure `REM`. For each planned measurement trace, arm the Pico block first, issue one and only one remote trigger, enforce the 0.1 s minimum interval, validate the trace, and audit the before/after T660 counters. Do not fire merely to fill time and do not retry beyond a separately reviewed retry allowance.
7. **Budget closure.** Apply and verify final safe idle. Compare both T660 counter deltas and the number of saved raw optical traces with the frozen budget. With the default plan the maximum is `1 blocked + 1 preview + 100 measurement = 102` emitted shots. Any mismatch, extra trigger, missing trace, rejected measurement shot, or safe-idle failure blocks the optical result and is reported in the manifest.

The beam-blocked control demonstrates whether the first CHB threshold edge could be Q-switch pickup rather than light. The optical edge finder must use the reviewed search window/control comparison; selecting the first edge after Q-switch without that control is insufficient evidence for `t_chem = 0`.

### 7.4 Step 7 correction

Step 0c determines the installed splitter/lead geometry `S_installed` using the exact output-1 Q-switch cable and output-2 monitor lead. The fixed downstream `E_A`/`E_B` acquisition paths are isolated by `C_scope`. Do not replace `S_installed` with the bare splitter skew `S_21`; the unequal installed leads are part of the temporary measurement geometry and must also be removed.

Define `C_PD` as the positive delay from optical pulse arrival at the detector plane to the electrical event presented at the calibrated `E_B` reference plane, including photodetector response latency and any measurement-only detector cable/adapter upstream of `E_B`. The downstream `E_B`/CHB acquisition path is already handled by `C_scope`. Then

```text
d_Q_to_optical = d_raw - C_scope - C_PD + S_installed
```

The `+S_installed` sign is intentional: CHA observes splitter output 2, while the desired reference is the Q-switch arrival on output 1 at DB9 pin 6. If output 2 arrives later than output 1, CHA is a late proxy and that lateness must be added back after the scope correction.

`C_PD`, its standard uncertainty, detector/cable identifiers, characterization source, and characterization date are mandatory frozen inputs. If any is unavailable, the complete workflow remains blocked before opening hardware; it must not acquire an optical run or emit a `t_chem` correction.

## 8. MIRcat DB9 process-control measurements

Return to safe idle after Step 7 and remove the splitter and optical detector setup. Steps 8 and 9 return to an electrical-only, non-emitting configuration, use 10 Hz, and use the complete six-point sweep.

### Step 8 — T660-1 FIRE to MIRcat Process Trigger electrical arrival

**Category:** MIRcat DB9 process-control timing.

- PicoScope CHA: destination end/approved breakout for T660-1 CHA -> Nd:YAG FIRE DB9 pin 7.
- PicoScope CHB: destination end/approved breakout for T660-1 CHC -> MIRcat Process Trigger DB9 pin 4.
- Remains connected to actual devices: T660-2 CHD final cable remains connected to T660-1 TRIG IN.
- Disconnected: FIRE pin 7 is disconnected from the Nd:YAG; MIRcat Process Trigger pin 4 is disconnected from MIRcat. Q-switch pin 6 and MIRcat Laser On/Off pin 5 remain disconnected/capped.
- Enabled: T660-2 CHD at 10 Hz, T660-1 CHA at programmed delay 0, and T660-1 CHC at the swept delay. All other outputs are disabled.
- Operator confirmation: verify FIRE pin 7 and Process Trigger pin 4, both destination disconnections, and MIRcat non-emitting state.

Use the corrected FIRE-to-CHC intercept in the process-control recipe when CHC gates or marks MIRcat process timing. Derive an HF2LI-EXT-REF-arrival-relative value only through the combination in Section 10; a true `t_master` value additionally needs the separately known programming-origin-to-EXT-REF-arrival term.

### Step 9 — T660-1 FIRE to MIRcat Laser On/Off electrical arrival

**Category:** MIRcat DB9 process-control timing.

- PicoScope CHA: destination end/approved breakout for T660-1 CHA -> Nd:YAG FIRE DB9 pin 7.
- PicoScope CHB: destination end/approved breakout for T660-1 CHD -> MIRcat Laser On/Off DB9 pin 5.
- Remains connected to actual devices: T660-2 CHD final cable remains connected to T660-1 TRIG IN.
- Disconnected: FIRE pin 7 is disconnected from the Nd:YAG; MIRcat Laser On/Off pin 5 is disconnected from MIRcat. Q-switch pin 6 and MIRcat Process Trigger pin 4 remain disconnected/capped.
- Enabled: T660-2 CHD at 10 Hz, T660-1 CHA at programmed delay 0, and T660-1 CHD at the swept delay. All other outputs are disabled.
- Operator confirmation: verify FIRE pin 7 and Laser On/Off pin 5, both destination disconnections, and MIRcat non-emitting state.

Use the corrected FIRE-to-CHD intercept only when the Laser On/Off route participates in the experimental recipe.

## 9. Per-shot processing and fitted results

For every accepted shot:

1. Preserve the raw trace in the unique run directory.
2. Record the programmed delays, measured sample interval, trigger mode/rate, thresholds, edge polarity, PicoScope settings, T660 readback path, cable setup ID, frozen-plan/revision ID, and applicable operator-confirmation timestamps. If a field is only available at run or setup level, reference that immutable record rather than duplicating an invented per-shot value.
3. Find the configured CHA and CHB edges with interpolation and retain edge-selection diagnostics.
4. Reject missing, ambiguous, clipped, saturated, control-like, or out-of-window edges with an explicit reason. Electrical-only rejected traces do not authorize silent replacement; Step 7 obeys the emitted-shot budget in Section 7.3.
5. Apply the applicable constant measurement-system corrections with the signs in Sections 4 and 7.

For each electrical sweep, let `x` be the programmed target-minus-reference delay and let `y` be the corrected measured target-minus-reference delay. Fit

```text
y = a + b*x
```

or, equivalently,

```text
residual = y - x = a + k*x
b = 1 + k
```

Report:

- Fixed offset/intercept: `a`, in ns.
- Delay-scale slope error: `(b - 1) * 1e6 = k * 1e6`, in ppm.
- Shot-to-shot jitter at each programmed delay and a clearly defined pooled/summary jitter.
- Fit uncertainty for `a` and `b`, sample/interpolation contribution, Step 0 correction uncertainty, and every supplied step-specific cable/detector term.
- Separately listed PicoScope timebase specification, T660 programmed-delay/readback specification, threshold sensitivity, connector/load equivalence, cable-reconnection repeatability, detector calibration, and sample-equivalent path-placement contributions. Each must cite its source and state whether it is included numerically, bounded separately, or not evaluated.

For the configured PicoScope 5244D, include the initial ±2 ppm timebase-accuracy term from `docs/PicoScope/PicoScope 5000D Series Data Sheet.pdf`, page 17, as a fixed-scale standard-uncertainty contribution. The same page lists ±1 ppm/year drift; record the instrument calibration/age status and include an additional drift term only when that reviewed record requires it. The six-point route fits empirically expose T660 delay-scale error as slope ppm; do not invent a separate absolute T660-delay uncertainty without a cited specification.

Do not use the residual at 1 ms as the fixed cable or route delay. A long-delay residual contains the fitted scale error. Do not include `abs(a)` as an uncertainty merely because the offset is nonzero.

Threshold sensitivity is not created automatically by naming a threshold. If the frozen plan does not include an approved re-analysis band or repeated-threshold method, report threshold sensitivity as `not evaluated` and do not claim it is inside `combined_standard_uncertainty_ns`. The same rule applies to any manufacturer specification or path-placement term not supplied before the run.

Step 7 has no delay-scale fit. Report its corrected mean optical delay, shot-to-shot jitter, detector/splitter/cable systematic terms, supplied sample-equivalent path-placement uncertainty, the blocked-control and preview results, planned versus actual shot-counter deltas, and accepted/rejected measurement-shot counts. A blocked optical run may preserve these diagnostics but must not emit a publishable `t_chem` correction.

## 10. Derived timing-chain and recipe calculations

For each swept electrical route, write the corrected fit as `y_i(x) = a_i + b_i*x`, where `a_i` is the fixed intercept and `b_i = 1 + slope_ppm_i/10^6`. Let the corrected fixed terms be:

```text
a1 = EXT REF arrival -> HF2LI DAQ arrival              (Step 1)
a2 = EXT REF arrival -> MIRcat TRIG IN arrival         (Step 2)
a3 = EXT REF arrival -> T660-1 TRIG IN arrival         (Step 3)
a4 = EXT REF arrival -> Nd:YAG FIRE pin 7 arrival      (Step 4)
a5 = FIRE pin 7 arrival -> Q-switch pin 6 arrival      (Step 5)
a6 = EXT REF arrival -> Q-switch pin 6 arrival, direct (Step 6)
d7 = Q-switch pin 6 arrival -> optical sample arrival  (Step 7)
a8 = FIRE reference -> MIRcat Process pin 4 arrival    (Step 8)
a9 = FIRE reference -> MIRcat Laser On/Off pin 5       (Step 9)
```

First calculate the following zero-programmed diagnostics, without hiding the directly measured terms:

```text
EXT REF -> Q-switch, derived = a4 + a5
Q-switch chain closure       = a6 - (a4 + a5)

EXT REF -> optical sample, via derived Q = a4 + a5 + d7
EXT REF -> optical sample, via direct Q  = a6 + d7

EXT REF -> MIRcat Process pin 4          = a4 + a8
EXT REF -> MIRcat Laser On/Off pin 5     = a4 + a9
```

These intercept-only combinations are diagnostics at zero programmed delay. They are not the operational optical anchor when the selected laser recipe programs nonzero FIRE and Q-switch delays.

Let `F` be the frozen T660-1 FIRE delay and `Q` the frozen T660-1 Q-switch delay from the reviewed Step 7 recipe. The operational electrical-reference-to-chemical-zero anchor is evaluated at that exact program:

```text
EXT REF -> FIRE at selected recipe       = a4 + b4*F
FIRE -> Q-switch at selected recipe      = a5 + b5*(Q - F)

EXT REF -> optical sample, component path
    = (a4 + b4*F) + (a5 + b5*(Q - F)) + d7

EXT REF -> optical sample, direct validation path
    = (a6 + b6*Q) + d7

selected-program closure
    = (a6 + b6*Q) - [(a4 + b4*F) + (a5 + b5*(Q - F))]
```

The consolidated output must print `F`, `Q`, and `Q-F`, both selected-program derivations, and their closure. The component path is the recipe anchor; the direct path is a validation and must not be silently averaged with it.

Propagate uncertainty with covariance where measurements share Step 0 corrections or other common terms. Root-sum-square propagation is valid only for independent terms. A failed Q-switch closure is a diagnostic to investigate, not a value to average away automatically.

For a single fitted route `y = a + b*x`, the exact programmed delay needed for a desired physical separation `D` is

```text
x_recipe = (D - a) / b
```

If the recipe system intentionally applies fixed correction only, the correction added to the nominal programmed delay is

```text
fixed_recipe_correction = -a
```

Thus a positive intercept means the target arrives late and its programmed event must move earlier. The ppm term remains separately reported; it must not be disguised as a fixed route delay.

To schedule a target event a chemical delay `tau` after the optical pump, let `P` be the corrected EXT-REF-arrival-to-optical-sample delay and let the target route have fit `y_target = a_target + b_target*x`. Then

```text
x_target_recipe = (tau + P - a_target) / b_target
```

This equation connects recipe time to `t_chem = 0`. It does not redefine `t_master`. Values expressed relative to the T660-2 programming origin must also state the programmed master-reference event and any separately known origin-to-cable-arrival term. Without that term, retain the physically accurate `EXT REF arrival -> ...` label.

## 11. Consolidated outputs and provenance

Each hardware execution must create a unique directory such as

```text
runs/YYYYMMDDTHHMMSSffffffZ_timing_calibration_<unique-id>/
```

using exclusive creation. If the path exists, abort; never reuse or overwrite it. Raw traces remain under this ignored `runs/` tree. An arbitrary output directory outside the ignored run root is not permitted for raw acquisition.

The run-local outputs must include:

- Frozen measurement plan and cable instructions used for that run.
- Run manifest with operator, timestamps, configuration/source/recipe/document hashes, parsed frozen settings, correction revision, confirmation log references, and step completion/safe-state status.
- Raw PicoScope traces and per-shot analysis rows.
- T660 recipe/readback and PicoScope settings/readback for every programmed delay.
- Per-delay statistical summary and fit diagnostics.
- Measurement-system correction file containing `M_0a`, `M_0b`, `M_0c`, `C_scope`, `S_21`, `S_installed`, uncertainties, cable/adapter/probe/load IDs, and the Step 0c load-equivalence evidence/source.
- Step 7 exposure audit containing the frozen emitted-shot budget, beam-blocked control, real preview, measurement-shot records, both T660 counter deltas, accepted/rejected counts, and every safe-idle result.
- One consolidated human-readable CSV and YAML/JSON table.
- Derived recipe-correction and chain-closure report.

The consolidated table must contain at least these columns:

- Category
- Measurement ID
- Reference event
- Target event
- Physical connection summary
- Uses final wiring? yes/no
- Splitter used? yes/no
- Splitter/scope correction applied
- Programmed delay range
- Fixed offset/intercept in ns
- Slope in ppm
- Jitter/uncertainty
- Uncertainty terms included; unresolved/not-evaluated terms and provenance
- Use in timing recipe? yes/no
- Signed recipe correction or explicit recipe formula (distinct from the positive physical latency)
- RSI/thesis reporting label
- Notes

Include three measurement-system correction rows derived from Steps 0a/0b/0c (`C_scope`, bare splitter skew, and installed Step 7 geometry), all nine requested system measurements in Steps 1–9, the Step 6 chain-closure result, both EXT-REF-to-optical derivations, and recipe corrections derived from them. The categories must make relative route offsets, measurement-system corrections, cross-device electrical latency, FIRE-to-Q-switch timing, MIRcat DB9 process-control timing, optical delay, validation, and derived recipe corrections visibly distinct.

The `fixed offset/intercept` field always reports the fitted or derived physical arrival term with the CHB-minus-CHA sign. It is not itself the signed recipe command. A row categorized as a derived recipe correction must show the actual command-side sign/formula in the separate recipe-correction field; for example, a positive fixed intercept generally produces a negative zero-arrival correction. Steps 8 and 9 must say `conditional` rather than unconditional `yes` when their DB9 controls are not enabled in the selected experimental recipe.

Acquisition must not rewrite shared `calibration/timing_calibration.csv`, `calibration/timing_offsets.yaml`, an earlier run directory, or an RSI/thesis directory. Promotion of an approved run into shared calibration and later RSI/thesis reporting is a separate, explicit review action.

Only a run with a verified final safe-idle readback may have status `PASS`. If final safe idle fails, preserve the partial artifacts, mark the run `BLOCKED_UNSAFE_STATE_UNVERIFIED`, omit publishable recipe corrections, and require manual output-state verification. A later successful manual check may be appended as a signed recovery record; it must not rewrite the original failure status or acquisition data.

## 12. Prehardware approval checklist

Hardware execution remains blocked until reviewers approve all of the following:

- [ ] T660 serial identities, channel maps, and the final wiring topology in Section 1.
- [ ] Nd:YAG DB9 pins 7 and 6 and MIRcat DB9 pins 4 and 5 against authoritative device documentation and the physical breakout.
- [ ] PicoScope input ranges, coupling, termination/loading, grounding, and safe connection to each TTL/DB9 route.
- [ ] Explicit 100 Hz recipes for Steps 0–3 and explicit 10 Hz recipes for every T660-1 step.
- [ ] Complete six-point electrical sweeps and the documented Step 0/Step 7 exceptions.
- [ ] Per-step safe-idle, cable prompt, operator confirmation, output enable list, and readback behavior.
- [ ] Step 0 swap protocol and correction signs verified with a synthetic or known-delay test.
- [ ] Step 0c load equivalence to the actual Nd:YAG pin-6 input demonstrated and its impedance/probe/cable provenance frozen.
- [ ] PicoScope, optical, safe-idle, and timing-calibration recipe paths, SHA-256 digests, and parsed safety-critical settings frozen in the reviewed plan.
- [ ] Step 7 splitter orientation, installed lead-delay correction, detector latency correction/provenance, reviewed minimum/maximum edge-search window, blocked-control amplitude comparison, attenuation, saturation rejection, and approved laser SOP.
- [ ] Step 7 `REM` one-shot controller, beam-blocked control, real preview, two-stage operator gate, cross-phase minimum shot interval, T660 counter audit, and total emitted-shot budget verified with fake hardware before laser use.
- [ ] Automatic PicoScope windows validated for the 1 ms point without a separate run.
- [ ] Fit implementation verified to separate intercept from ppm slope; uncertainty inputs are identified as included, separately bounded, or not evaluated without overclaiming a combined value.
- [ ] Unique, exclusive run-directory creation and no-overwrite behavior.
- [ ] Every transition prompt independently states what to disconnect, restore, park/cap, and leave connected after safe idle.
- [ ] Any safe-idle application/readback failure blocks PASS and triggers manual safe-state intervention.
- [ ] Consolidated table schema, derived-chain equations, correction signs, and `t_master`/`t_chem` labels.
- [ ] Confirmation that review/plan generation performs no hardware I/O and no RSI/thesis draft update.

Only after this checklist is approved should the workflow implementation be authorized for mocked-device verification and then one reviewed complete hardware run. The complete run remains electrical/non-emitting through Step 6; Step 7 has its own bounded one-shot optical gates; Steps 8–9 return to a physically disconnected electrical-only state. If a staged electrical-only commissioning run is desired, it requires a separately reviewed workflow mode rather than silently skipping Step 7 in this command.

## 13. Two-invocation review and execution gate

Generate a new review package without opening hardware. Supply every detector, path, load-equivalence, assembly, recipe, sweep, and shot-count value intended for execution so those values are frozen in the package:

```text
python tests/hardware_checks/check_day8_timing_calibration.py --operator "Operator Name" \
  --photodetector-response-delay-ns <value> \
  --photodetector-response-uncertainty-ns <value> \
  --photodetector-response-source <record> \
  --photodetector-identifier <id> \
  --photodetector-cable-identifier <id> \
  --photodetector-characterization-date <YYYY-MM-DD> \
  --photodetector-path-description <description> \
  --photodetector-maximum-latency-ns <reviewed-upper-bound> \
  --sample-path-standard-uncertainty-ns <value> \
  --step7-load-match-method <description> \
  --step7-load-match-standard-uncertainty-ns <value> \
  --measurement-assembly-record <identifiers>
```

This first invocation exclusively creates a timestamp-and-UUID run directory under `runs/`, writes the Markdown/JSON plan and a `hardware_opened: false` status, lists unresolved detector/cable/load inputs as prehardware blockers, and exits without applying a recipe. An invocation containing `--execute` but no prior `--reviewed-plan-dir` also only creates a new blocked plan; it cannot open hardware.

After the checklist and both plan files have been reviewed, execute that unchanged directory in a second invocation:

```text
python tests/hardware_checks/check_day8_timing_calibration.py --operator "Operator Name" \
  --execute --reviewed-plan-dir runs/<reviewed-plan-directory> \
  --confirm-real-hardware --confirm-plan-reviewed \
  --confirm-safe-electrical-routing \
  <repeat every frozen option from the plan-only invocation exactly>
```

The second invocation rebuilds the requested plan, verifies it against the prior JSON and human-reviewed Markdown, verifies the prior `hardware_opened: false` status, and refuses to proceed if any frozen value, source file hash, effective T660 setting, or plan text differs. It loads the reviewed PicoScope, safe-idle, optical, and hardware settings into immutable in-memory snapshots before access; later file edits cannot alter a running calibration. `workflow_status.json` changes from plan-only to execution-start/open-attempt/opened and finally `PASS`, `BLOCKED`, or `BLOCKED_UNSAFE_STATE_UNVERIFIED`. An operator interrupt still runs final safe-idle/cleanup, records the final status and manifest, and returns exit code 130; an interrupt during STOP/readback is treated as an unverified unsafe state. The reviewed plan files themselves are never rewritten. Exact per-step cable, electrical-safety, and laser-safety phrases remain mandatory after this gate. Use `--help` to see every frozen input.
