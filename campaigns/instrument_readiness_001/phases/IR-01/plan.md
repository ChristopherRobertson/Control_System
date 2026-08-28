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
using the OP-01/CL-01 time origin and the applicable experiment-specific
detector/acquisition settings. Apply the HRP configuration to both HRP bands
and the MbCO configuration to MbCO A1; do not transfer lock-in filter delay or
attenuation between them without the HF-01/AR-01 equivalence record.
Characterize the combined effects of pump duration, probe gate, residual
jitter, detector response, and lock-in filtering without repeating electrical
path calibration.

Use three retained configurations only: permanent-iris OPO 540 nm at the lower
HRP-C-CO band, the same pump at the upper HRP-C-CO band, and the same pump at
the MbCO A1 band. Merge HRP upper/MbCO probe settings only where the combined
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

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
