# SV-02B — blind Mylar independent validation

Campaign: `instrument-readiness-001`  
Domain: `validation`  
Registry status: `planned`  
Required dependencies: `SV-02A`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### SV-02B — blind Mylar independent validation

After the SV-02A unlock, apply every frozen choice to specimen-matched Mylar FTIR
comparison. Acquire forward and reverse scans and assess peak position, FWHM,
normalized line shape, hysteresis, repeatability, baseline behavior, SNR, and total
uncertainty. Mylar cannot fit, tune, select, or revise calibration, acquisition,
analysis, windows, or acceptance rules. Failure opens a cause-coded investigation or
narrows the claim and never automatically refits. The minimum is three accepted
Mylar scans per direction.

This blind validation closes the nonbiological spectral-axis evidence for `EXP-CAL-05`
and `EXP-OPT-06` without refitting. Native records, rejection causes,
uncertainty, direction dependence, and the frozen correction/version are retained.
Failure narrows the validated envelope or opens a new investigation; it cannot be cured
by tuning to Mylar. The result is a prerequisite for all four initial slow scans but
does not supply their sample-specific centers, widths, areas, or baselines.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
