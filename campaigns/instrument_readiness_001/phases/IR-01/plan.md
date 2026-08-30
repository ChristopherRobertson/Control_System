# IR-01 — system temporal instrument response

Campaign: `instrument-readiness-001`  
Domain: `characterization`  
Registry status: `planned`  
Required dependencies: `SV-02B, CL-01, DET-03, AR-01, OV-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### IR-01 — system temporal instrument response

Measure the complete instrument temporal response at a sample-equivalent plane
using the OP-01/CL-01 optically observed time origin and each applicable
experiment-specific detector/acquisition setting. Cover all CH-00.1-retained
room-temperature/77 K HRP and MbCO architectures; do not transfer lock-in filter delay,
scan-history response, digitizer aperture, optical envelopes, or attenuation between
them without an explicit equivalence record.
Characterize the combined effects of pump duration, probe gate, residual
jitter, detector response, and lock-in filtering without repeating electrical
path calibration.

Use separate configurations for every non-equivalent pump/probe region, temperature,
time scale, acquisition method, and normal-versus-temporary timing topology. Merge
HRP/MbCO probe settings only where the combined
probe/detector response is demonstrably equivalent. The repeat count is selected
prospectively from the IRF-width/bias precision target and capped by the frozen
exposure budget. Mylar adds no temporal-response condition.

The OPO-540 configuration uses the static qualified iris. Its command/readback
and configuration ID are retained with each block, but iris communication
latency is not convolved into the per-shot IRF because the aperture is not
commanded during an emitted sequence.

Mandatory deliverables:

- Raw synchronized optical/electrical/DIO traces, configuration and calibration
  links, reference-plane definition, blocked controls, exposure ledger, and
  detector placement.
- True-versus-observed response model, impulse/step response as appropriate,
  FWHM or other resolution metric, delay bias, operating-condition dependence,
  uncertainty, residuals, and supported temporal window.
- Exact chemical-time-zero handoff convention for later biological campaigns.

## `EXPERIMENTS.md` allocation and decision contract

IR-01 implements `EXP-CAL-18`, `EXP-CHAR-08`, `EXP-CHAR-13`, `EXP-OPT-04`,
`EXP-OPT-07`, and `EXP-VAL-07`. The retained record must compose pump and probe optical
envelopes, relative jitter, separate detector/branch responses, digitizer aperture,
HF2LI filter/demodulation effects, and scan history. Acceptance requires native traces,
controls, residuals, supported window/resolution, uncertainty, and a stable
configuration-specific IRF ID. Any constituent, temperature/geometry, topology,
timing/filter/rate, scan history, or algorithm change triggers revalidation. It does not
establish biological model complexity, lifetime, fraction, recovery, or dose response.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
