# OM-01 — optical metrology readiness and transfer standards

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `historical_complete`  
Required dependencies: `TR-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../shared/phase_execution_requirements.md`.

## Phase-specific procedure and deliverables

The detailed phase text below was materialized from the former combined procedure catalog. Git commit `75b138a` preserves that pre-split source.

### 9. OM-01 — optical metrology readiness and transfer standards

Execution status: **PASS - COMPLETE, QUALIFIED BOUNDED** in the stable
`evidence/calibration/system_recalibration_001/phases/OM-01/` record. Newport 1918-R serial `15879` with 919P-010-16
sensor serial `161791` has passed query-only USB identity/configuration
communication and the completed installed checks are retained in
`optical_metrology_bundle.json`. This status does not authorize WM-01, ATT-01,
or any later phase and performs no canonical promotion.

Qualify only the available instruments selected after downstream experiment
requirements define the needed pump/probe power, wavelength, beam-size,
polarization, attenuation, and observational ambient records. No energy meter
is currently available, so this phase does not require direct pulse-energy
measurement. It does not characterize the pump or probe beams themselves.

The minimum wavelength grid is the union frozen in CH-00: direct 532 nm pump,
355 nm only as the OPO drive, 540 nm OPO output, one Mylar-carbonyl probe
anchor, and the merged HRP/MbCO probe anchors and off-band control points.
Shared points are measured once. No other wavelength or range is qualified
unless the frozen claim grid requires it.

At each retained wavelength family and meter range required by the
experiment-derived expected reading envelope, record zeroing, background,
sensor head, wavelength correction, sampling mode, warm-up, bounded
low/high meter-behavior evidence, three repeat readings, one revisit,
saturation limits, spatial-scale calibration, and the applicable manufacturer
specification or available comparison. Exact laser delay, current, pulse/duty,
and delivered-power operating points are selected and characterized later in
ATT-01/PB-02/PB-01/QB-01; they are not OM-01 inputs. Add a midpoint only when the
meter-behavior residual rule fails. Do not add a new meter or certificate task
unless an approved experimental claim requires it.

Mandatory closeout deliverables:

- Optical-metrology configuration manifest and permitted range/wavelength
  table for every meter/sensor.
- Raw zero/background/check data, applicable specification or comparison
  links, correction tables, interpolation rules, saturation rules, and
  uncertainty budgets.
- Beam-profiler spatial calibration or documented alternative beam-diameter
  method; environmental observation method and uncertainty classification.
- `optical_metrology_bundle.json` assigning a stable bundle ID consumable by
  DET-02, DET-03, DET-04, OP-01, and `system_characterization_001`.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
