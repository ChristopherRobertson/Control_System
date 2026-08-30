# OV-01 — pump-probe overlap and placement repeatability

Campaign: `instrument-readiness-001`  
Domain: `characterization`  
Registry status: `planned`  
Required dependencies: `OG-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### OV-01 — pump-probe overlap and placement repeatability

Establish spatial overlap at the sample or sample-equivalent plane without
using the desired biological response as the only indicator. Quantify overlap
fraction, relative centroids, crossing angle, overlap area/volume as applicable,
placement repeatability, and sensitivity to routine realignment.

Retain the permanent-iris OPO 540 nm with HRP and MbCO probe geometries at each
retained room-temperature and 77 K condition. Cryogenic windows, matrix, refraction,
thermal contraction, and focus create separate placement configurations. For each pair perform three
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

## `EXPERIMENTS.md` allocation and decision contract

OV-01 implements the spatial-overlap and placement portions of `EXP-CHAR-05`,
`EXP-CHAR-11` and `EXP-OPT-03`. Acceptance requires an independent
overlap measurement with uncertainty and reproducible fiducials for every retained
condition. Optic/cell/cryostat movement, thermal cycle, source profile, iris, probe
region, alignment, or failed placement checkpoint triggers revalidation. Consumers are
IR-01, PF-01, RP-01, E2E-CH, and biological dose/overlap pilots. It does not establish
temporal overlap, chemical time zero, reversible biological dose, or kinetics.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
