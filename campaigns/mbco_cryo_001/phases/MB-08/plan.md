# MB-08 — optional MbCO mechanistic extension

Campaign: `mbco-cryo-001`  
Domain: `experiment`  
Registry status: `optional`  
Required dependencies: `MB-07`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
the campaign `../../requirements.md`.

## Phase-specific procedure and deliverables

This phase inherits the campaign-wide scientific, safety, acquisition, analysis, and data-contract requirements in `../../requirements.md`.

| **MB-08 optional mechanistic extension** | MVP accepted; IRF/SNR/model simulation supports extension | Add dense geminate schedule, A₀/A₃ kinetics, concentration series or qualified 532 nm comparison | Extension-specific preregistration, data, model comparison, sensitivity analysis | Keep this phase outside the MVP; stop if validity, sample, or identifiability fails. |

Any extension is condition- and architecture-specific. The room-temperature and 77 K
branches require separate slow-scan anchors, IRFs, native coverage, reset/dose rules,
temperature/geometry envelopes, and identifiability simulations. A new wavelength or
pump path requires its own qualification; a model is not expanded beyond what remains
identifiable after measured acquisition-kernel convolution.

Any denser room-temperature single-scan phase-delay extension retains the promoted
Phase-Scan marker-alignment, dual-detector pulse-coverage, retry, aligned-bin merge,
and provenance rules without relaxation. Extension scans remain separate attempts at
their acquired delays; deficient regions are not filled across different phase delays
or biological states. A retry-exhausted result remains
`INCOMPLETE_MISSING_PULSE_COVERAGE`, diagnostic only, visibly incomplete in every
table and plot, and ineligible for mechanistic or publication claims.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
