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

| **MB-05 pump/dose/overlap pilot** | Accepted steady sample; WM/ATT/PB/OG/OV imports and iris/wavelength validity are current | Verify the unchanged promoted iris mount and 540 nm command/readback, WaveMaster configuration/native status, post-iris sample-plane beam/power and aperture margin; begin lowest dose/0.5 Hz; run blank/deoxy/no-pump controls, dose series, downstream overlap scan, and post-integrity | Iris/WaveMaster/configuration ledger; post-iris dose-response/overlap maps; derived mean-energy calculation; photolysis estimate; damage ceiling | Abort on wavelength/status failure, iris mismatch or communication loss, mount/centroid/profile invalidity, residual pump artifact, nonlinearity at lowest useful dose, temperature/integrity failure, or overlap instability. Do not optimize the iris on biological response. |

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
