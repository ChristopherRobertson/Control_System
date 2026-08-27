# OG-01 — sample-plane optical transfer and beam geometry

Campaign: `instrument-readiness-001`  
Domain: `characterization`  
Registry status: `planned`  
Required dependencies: `QB-01, PB-02, SC-01, OM-01, ATT-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../shared/phase_execution_requirements.md`.

## Phase-specific procedure and deliverables

The detailed phase text below was materialized from the former combined procedure catalog. Git commit `75b138a` preserves that pre-split source.

### OG-01 — sample-plane optical transfer and beam geometry

Using the final optical path and SC-01 cell/mount, characterize exactly three
optical conditions: probe-only Mylar validation, permanent-iris OPO-540/HRP
probing, and the same OPO-540 pump with MbCO probing. For the QCL, profile one Mylar anchor and the lower/upper
biological anchors; add an intermediate point only if the endpoint comparison
fails the wavelength-dependence criterion. Measure pump and probe spot size
using a stated diameter convention, spatial profile, incidence angle,
polarization, path length, transfer efficiency, average power, derived mean
pulse energy where allowed, fluence/irradiance inputs, and positioning
uncertainty.

For OPO-540, the final path begins at the qualified post-iris plane. OG-01
independently verifies that the accepted aperture does not clip the useful core
at the sample plane and measures the delivered post-iris power used to derive
mean pulse energy and theoretical pump dose. Pre-iris OM-01 mixed-output power
is not substituted for this quantity.

Mandatory deliverables:

- Reference-plane and optical-layout diagrams/photos with stable optic,
  attenuator, meter-pickoff, electronic-iris device/configuration/readback,
  aperture, window, and mount IDs.
- Native profiles/images/readings; background and scale calibration; beam-
  diameter calculations; transfer/fluence/irradiance tables with full
  uncertainty propagation.
- Alignment coordinates or reproducible fiducials, acceptance bounds, damage/
  saturation margins, and restoration/reinstallation record.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
