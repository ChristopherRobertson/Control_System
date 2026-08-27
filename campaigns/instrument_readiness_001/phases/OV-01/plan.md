# OV-01 — pump-probe overlap and placement repeatability

Campaign: `instrument-readiness-001`  
Domain: `characterization`  
Registry status: `planned`  
Required dependencies: `OG-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../shared/phase_execution_requirements.md`.

## Phase-specific procedure and deliverables

The detailed phase text below was materialized from the former combined procedure catalog. Git commit `75b138a` preserves that pre-split source.

### OV-01 — pump-probe overlap and placement repeatability

Establish spatial overlap at the sample or sample-equivalent plane without
using the desired biological response as the only indicator. Quantify overlap
fraction, relative centroids, crossing angle, overlap area/volume as applicable,
placement repeatability, and sensitivity to routine realignment.

Retain only two pump/probe pairs: permanent-iris OPO 540 nm with the HRP probe
geometry and that same pump with the MbCO A1 probe geometry. For each pair perform three
independent placements and one controlled realignment. Mylar is pump-off and
adds no overlap condition. Add a second probe wavenumber only if OG-01 shows a
material geometry change across the corresponding biological window.

All OPO-540 placements retain the same ATT-01/PB-02 iris mount and diameter.
The controlled realignment tests routine downstream placement and does not
authorize an iris adjustment. If overlap cannot pass without changing the
iris, stop and investigate the upstream configuration rather than fitting the
aperture to a biological or desired-response result.

Mandatory deliverables:

- Independent overlap method, blocked/single-beam controls, native images or
  scans, coordinate transforms, profile fits, and overlap calculation source.
- Overlap fraction/area/volume with uncertainty, alignment tolerances,
  reinstallation/realignment repeatability, and explicit validity for each
  pump/probe condition.
- Final fiducial/alignment procedure and sample-position record suitable for
  later biological campaigns.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
