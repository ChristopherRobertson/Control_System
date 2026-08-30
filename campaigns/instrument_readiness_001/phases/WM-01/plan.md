# WM-01 — visible and near-IR wavelength-metrology readiness

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `in_progress`  
Required dependencies: `OM-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### 10. WM-01 — visible/near-IR wavelength-metrology readiness

Execution status: **STARTED 2026-08-21; INSTALLED WAVEMASTER OPTICAL
QUALIFICATION FAILED; OPEN / DEFERRED PENDING REPLACEMENT SPECTROMETER**.

WM-01 resumes with a suitable replacement wavelength spectrometer and qualifies only
the installed replacement as a campaign-local wavelength working reference over the
source conditions it actually supports. The rejected Coherent WaveMaster, catalog
number 33-2650, and all native failure evidence remain preserved and indexed; they are
not overwritten, normalized into a pass, or treated as evidence for the replacement.
The replacement's identity, interfaces, wavelength range, units, modes, status
semantics, uncertainty, and reference plane must be established from its own records.
WM-01 does not qualify optical power, spectral-power fractions, absence of additional
wavelengths, or any wavelength outside the accepted replacement validity envelope.

Before resumed acquisition, create a replacement-device entry with observed identity,
firmware/software, connection, driver, interface, supported-range, and native-query
records. Existing `devices.wavemaster.*` entries and `wm01_preflight.py` output describe
only the rejected installation and cannot serve as the replacement entry gate. A
replacement-specific preflight must verify its documented communication and safety
requirements. Separate user approval is still required before phase work, optical
placement, or laser emission.

The resumed phase identifies and photographs the replacement label, front panel,
sampling optic/fibre, mount, pickoff, dump, and retained reference plane. It verifies
the replacement's documented connection, self-test, query/set/readback behavior,
exclusive ownership where applicable, loss/reconnect behavior, malformed or stale
response rejection, local-control restoration, and safe cleanup. Device-specific
commands, serial settings, acceptance controls, and status values are recorded from
observed native behavior and documentation rather than inherited from the WaveMaster.

Optical qualification freezes the replacement's wavelength medium/units, acquisition
mode, calibration state, sampling geometry and acceptance controls, input-status
interpretation, and retained reference plane. Quantitative records follow the
replacement manufacturer's warm-up and stability guidance. At every retained visible
or near-IR campaign wavelength within its supported envelope, acquire blocked/no-signal
controls, native wavelength/status records with time tags, repeated windows, and a
later revisit. Capture naturally observed multi-line, low-signal, or saturation states
without coercion or deliberate overload. An applicable independent wavelength
reference may support an agreement check; otherwise the result is a
manufacturer-specification-based installed working reference and does not claim
accredited traceability.

Mandatory closeout deliverables:

- Installed-device, cable, adapter/driver, sampling optic, mount, reference-plane,
  and software configuration manifests with native replacement identities and applicable
  photographs; rear-panel, cable, and adapter photographs are not mandatory
  when the installed connections are otherwise identified.
- Raw native communication transcript; self-test/calibration results; settings/readbacks;
  disconnect/reconnect, exclusive-ownership, invalid-response, local-control,
  and restoration evidence; offline-test results; and accepted/rejected index.
- Native wavelength/status/time-tag records, blocked control, thermal-stability
  classification, repeatability/revisit analysis, any reference comparison,
  response-state handling, uncertainty budget, and explicit unsupported-wavelength and
  spectral-power-fraction exclusions. The rejected WaveMaster evidence remains a
  separately indexed rejected stratum.
- `wavelength_metrology_bundle.json` with a stable bundle ID, validity envelope,
  permitted units/modes/sampling geometry, replacement identity, revalidation triggers, and machine-
  readable quantity IDs consumable by ATT-01, PB-02, OG-01, PF-01, RP-01,
  RPT-01, and the characterization campaign.

WM-01 must pass and close before ATT-01 can be authorized. The 2026-08-25
dependency amendment allows only independent wavelength-metrology phases to proceed;
it is not a bypass. The rejected WaveMaster installation cannot support independent
wavelength identity, residual-color interpretation, or quantitative
notebook-prediction claims.

## `EXPERIMENTS.md` allocation and decision contract

This phase supplies independent OPO wavelength/status working-reference evidence for
`EXP-CAL-15` and the applicable pump-identity portion of `EXP-CHAR-05`; it does not
replace the separate MIRcat mapping phases. Native replacement
records, calibration/status readbacks, controls, repeats, rejected records, uncertainty,
and validity limits must be retained. Acceptance is wavelength- and configuration-
specific. A device change, sampling-path change, calibration expiry, unsupported status,
out-of-envelope wavelength, or failed revisit triggers rejection or revalidation.
Consumers are ATT-01, PB-02, OG-01, PF-01, RP-01, RPT-01, and both biological
campaigns. This phase does not establish optical power, beam overlap, spectral purity,
chemical time zero, detector linearity, or kinetic claims.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
