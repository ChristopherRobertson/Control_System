# FE-01 — finite emitted-pump-event control and reconciliation

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `OP-01, PT-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../shared/phase_execution_requirements.md`.

## Phase-specific procedure and deliverables

The detailed phase text below was materialized from the former combined procedure catalog. Git commit `75b138a` preserves that pre-split source.

### 23. FE-01 — finite emitted-pump-event control and reconciliation

Qualify the finite-exposure mechanism shared by the biological experiments
without a biological sample. Preserve the manufacturer-qualified Nd:YAG/OPO
cadence while admitting only CH-00-approved rare post-iris OPO-540 pump events
to the sample-equivalent plane. The accepted implementation may be a
validated laser pulse-division mode, an interlocked optical pulse picker/
shutter, or another separately approved topology. A T660 shot-counter reset is
never an exposure limiter.

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
  event interval/record length under each retained HRP and MbCO acquisition
  configuration. Dose, photolysis,
  and biological recovery are outside this calibration phase.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
