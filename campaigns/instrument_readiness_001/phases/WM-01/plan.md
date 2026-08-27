# WM-01 — visible and near-IR wavelength-metrology readiness

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `in_progress`  
Required dependencies: `OM-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../shared/phase_execution_requirements.md`.

## Phase-specific procedure and deliverables

The detailed phase text below was materialized from the former combined procedure catalog. Git commit `75b138a` preserves that pre-split source.

### 10. WM-01 — visible/near-IR wavelength-metrology readiness

Execution status: **STARTED 2026-08-21; INSTALLED WAVEMASTER OPTICAL
QUALIFICATION FAILED; OPEN / DEFERRED PENDING REPLACEMENT SPECTROMETER**.

WM-01 qualifies the installed Coherent WaveMaster, catalog number 33-2650, as
a campaign-local wavelength working reference over only the source conditions
used by the retained campaign. It does not qualify optical power, spectral-
power fractions, absence of additional wavelengths, or the 355 nm OPO drive,
which is outside the instrument's 380-1095 nm specified range.

Before WM-01 may start, every `devices.wavemaster.phase_entry_required_fields`
entry in `hardware_configuration.yaml` must contain an observed value. The
2026-08-20 query-only connection intake resolved and recorded the electronic
serial, complete `*IDN?` response, firmware revision, COM port, adapter
VID/PID, adapter/interface serials, adapter model, installed driver, and native
query responses. The operator confirms that the connected instrument works
safely. All phase-entry fields are resolved.

`python software/tools/wm01_preflight.py` enforces this entry gate and now reports
`READY_FOR_PHASE_APPROVAL`. Separate user approval is still required before
phase work, optical placement, or laser emission. A null-modem cable or missing
RTS/CTS conductors blocks the phase.

The phase first identifies and photographs the label, front panel, sampling
probe/fibre and acceptance switch, mount, pickoff, and dump. Cable, USB adapter,
and rear-panel photographs are optional when the installed RS-232 and power
connections are otherwise identified in the cable/adapter, driver, device
configuration, and live communication evidence. It then verifies
straight-through RS-232 operation at
9600 baud, 8-N-1 with hardware RTS/CTS, exclusive port ownership, `*IDN?`,
`*TST?`, local/remote restoration, documented query/set/readback behavior,
communication loss/reconnect, malformed/stale-response rejection, and safe
cleanup. Electronic identity is compared with the reported `WO 339` label
without normalizing an ambiguous character by assumption.

Optical qualification freezes air-nanometre units, pulsed mode for OPO work,
autocalibration enabled, sampling-probe geometry/acceptance setting, input-
status interpretation, and the retained reference plane. Quantitative records
use the manufacturer guidance for best thermal stability after approximately
four hours. At 540 nm, and at 532 nm only where useful as a visible source-
health/reference point, acquire blocked/no-signal controls, native `VAL$`
records with time tags, repeated windows and a later revisit. Capture naturally
observed `Multi-Line` or saturation states without coercion or deliberate
overload. An applicable independent wavelength reference may support an
agreement check; when none is available, the result remains a manufacturer-
specification-based installed working reference and does not claim accredited
traceability.

Mandatory closeout deliverables:

- Installed-device, cable, adapter/driver, probe, mount, reference-plane,
  and software configuration manifests with native identities and applicable
  photographs; rear-panel, cable, and adapter photographs are not mandatory
  when the installed connections are otherwise identified.
- Raw serial transcript; self-test/autocalibration results; settings/readbacks;
  disconnect/reconnect, exclusive-ownership, invalid-response, local-control,
  and restoration evidence; offline-test results; and accepted/rejected index.
- Native wavelength/status/time-tag records, blocked control, thermal-stability
  classification, repeatability/revisit analysis, any reference comparison,
  response-state handling, uncertainty budget, and explicit 355 nm and
  spectral-power-fraction exclusions.
- `wavelength_metrology_bundle.json` with a stable bundle ID, validity envelope,
  permitted units/modes/probe geometry, revalidation triggers, and machine-
  readable quantity IDs consumable by ATT-01, PB-02, OG-01, PF-01, RP-01,
  RPT-01, and the characterization campaign.

WM-01 must pass and close before ATT-01 can be authorized. The 2026-08-25
dependency amendment allows only independent non-WaveMaster phases to proceed;
it is not a bypass. A bypass cannot
support independent 540 nm wavelength identity, residual-color interpretation,
or quantitative notebook-prediction claims.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
