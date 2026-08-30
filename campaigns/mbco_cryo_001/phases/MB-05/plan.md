# MB-05 — MbCO pump dose and overlap pilot

Campaign: `mbco-cryo-001`  
Domain: `experiment`  
Registry status: `optional`  
Required dependencies: `MB-04`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
the campaign `../../requirements.md`.

## Phase-specific procedure and deliverables

This phase inherits the campaign-wide scientific, safety, acquisition, analysis, and data-contract requirements in `../../requirements.md`.

| **MB-05 pump/dose/overlap pilot** | Accepted condition-specific steady sample; WM/ATT/PB/OG/OV imports and iris/wavelength validity are current | For each retained temperature, verify the unchanged promoted iris mount and 540 nm command/readback, WM-01 replacement configuration/native status, post-iris sample-plane beam/power and aperture margin; start at the lowest qualified dose/cadence; run blank/deoxy/no-pump controls, dose series, downstream overlap scan, recovery/reset/fresh-position checks, and post-integrity | Iris/wavelength/configuration ledger; condition-specific post-iris dose-response/overlap/recovery maps; derived mean-energy calculation; photolysis estimate; reversible envelope and damage ceiling | Abort on wavelength/status failure, iris mismatch or communication loss, mount/centroid/profile invalidity, residual pump artifact, nonlinearity at lowest useful dose, incomplete reset/recovery, temperature/integrity failure, or overlap instability. Do not optimize the iris on biological response. |

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
