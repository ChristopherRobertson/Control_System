# DET-03 — detector temporal response and latency correction

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `DET-02, HF-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### 18. DET-03 — detector temporal-response and latency correction

Measure or authoritatively bound the response delay and temporal bandwidth of
the exact detector/amplifier/cable/acquisition path used by OP-01. This is a
new missing correction term; it does not repeat MS-01/MS-02 or T1-01.
Test each installed detector/amplifier/cable path at the fastest required
acquisition configuration and at the low/high accepted signal levels. Import
the HF-01 measured complex filter transfers and compose them with this detector
response to produce HRP-C-CO and MbCO latency/attenuation corrections. Confirm
that composition once under the other biological configuration only if the
paths cannot be shown linear and time invariant, the propagated result lies in
an acceptance guard band, or the confirmation residual fails. Use one anchor
in each disjoint Mylar and biological probe window; add another wavelength only
if the manufacturer model or measured residuals show material wavelength
dependence. Do not repeat the HF-01 AWG filter grid.

Mandatory closeout deliverables: stimulus/reference planes, detector placement
and cable IDs, raw response data or authoritative model record, amplitude-
dependence and threshold checks, detector-only response plus HF-01-composed
HRP/MbCO latency and attenuation estimates, composition residual or stated
escalation result, sign convention, standard uncertainty, validity envelope,
and a stable correction ID accepted for OP-01.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
