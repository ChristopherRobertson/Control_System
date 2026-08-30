# DET-03 — detector temporal response and latency correction

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `DET-02, HF-01, MS-02.1`
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
response to produce configuration-specific room-temperature/77 K HRP-C-CO and MbCO
latency/attenuation corrections for every retained acquisition path. Confirm
composition across another configuration only if the
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

## `EXPERIMENTS.md` allocation and decision contract

DET-03 implements the detector/electronics temporal-response terms of `EXP-CAL-10`,
`EXP-CAL-11`, `EXP-CAL-18`, `EXP-CHAR-06`, `EXP-CHAR-08`, and `EXP-OPT-04`. The normal
dual-channel topology and any temporary timing/IRF topology are distinct configuration
records. Acceptance requires a traceable response model, residual check, uncertainty,
and latency sign convention for every non-equivalent path. Detector/amplifier/cable,
branch topology, signal level, wavelength, HF2LI/Pico settings, trigger, or analysis
changes trigger revalidation. This phase does not establish optical pump arrival,
chemical time zero, or a complete system IRF.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
