# FE-01 — finite emitted-pump-event control and reconciliation

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `OP-01, PT-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### 23. FE-01 — finite emitted-pump-event control and reconciliation

Qualify finite emitted-event control without a biological sample. T660-1 C
supplies the event clock to T660-2 TRIG IN; T660-2 executes a preloaded frame
schedule with per-frame enables/delays for FIRE, Q-switch, and Process Trigger
on A/B/C and a shared train count/spacing.
Test channel OFF entries, train count zero for no additional pulses, terminal
padding, exact logical/physical counts,
start/stop ordering, maximum delay bounds, and output completion after the frame
engine reports done. The predivider and cadence are selected for each experiment.
Both D outputs and DIO1 remain unwired.

Frame and shot counts establish electrical commands, not emitted sample events.
Independently verify that the selected FIRE/Q-switch schedule preserves the
qualified source cadence and optical stability while admitting only planned
post-iris OPO-540 events. If a particular experiment needs additional approved
optical gating to preserve lamp cadence, qualify it explicitly; the default
frame program does not imply an installed pulse picker. A T660 shot-counter
reset never limits exposure.

For the OPO-540 path, retain the ATT-01 iris configuration and verify its
command/readback before the independent event-count tests. Changing iris
diameter or mount state creates a different optical configuration and cannot be
used to admit or suppress individual pump events.

Mandatory closeout deliverables:

- Stable configuration and topology IDs for the retained 540 nm path,
  with command source, flashlamp cadence, optical gate/divider state, and an
  independent optical pump-event observation.
- A blocked zero-event control, a one-event test, and one finite multi-event
  block for the retained path; command-versus-observed event reconciliation;
  verification that the programmed limit stops further admitted events; and
  proof that unused pulses remain blocked from the sample-equivalent plane.
- No-emission fault tests for observation loss, command/observation mismatch,
  software exception, and operator stop, plus the normal-completion path. Each
  path must close the pump first, stop both T660s/MIRcat as applicable, apply
  safe idle, preserve partial evidence, and verify restoration.
- Latency/uncertainty, event-observation behavior, and maximum supported rare-
  event interval/record length under each retained room-temperature/77 K HRP and MbCO acquisition
  configuration. Dose, photolysis,
  and biological recovery are outside this calibration phase.

## `EXPERIMENTS.md` allocation and decision contract

FE-01 implements the emitted-event control portions of `EXP-CAL-08`,
`EXP-CHAR-05`, `EXP-CHAR-12`, `EXP-OPT-03`, and `EXP-OPT-09`. Qualify zero, one,
and finite-event behavior for every materially distinct repeated-event or single-pump
architecture while treating probe carrier rate independently of the pump-event limit.
Acceptance requires command-versus-independent-optical-event reconciliation, bounded
latency/uncertainty, finite stop, fault-safe behavior, and preserved partial evidence.
Gate/divider, cadence, route, observation detector, source/iris, orchestration, or
configuration changes trigger revalidation. This phase does not establish biological
recovery, equivalent state, photolysis fraction, damage threshold, or kinetics.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
