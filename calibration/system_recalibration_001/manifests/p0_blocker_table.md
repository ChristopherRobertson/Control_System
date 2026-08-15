# P0 blocker and deferred-item table

Campaign: `system_recalibration_001`
Assessment date: 2026-07-24 (America/Los_Angeles)  
Operator: `Christopher Robertson`

This is the preserved dated P0 assessment. Current keep/narrow/discard choices
are controlled by `p0_requirement_decisions.md`; this historical table does not
independently keep a requirement active after a recorded decision.

| ID | Missing item or unresolved condition | Affected future phase | Execution blocker or claim limitation | Permitted resolution | Safely deferrable? |
|---|---|---|---|---|---|
| P0-B01 | **RESOLVED:** the reviewed P0 candidate working tree was clean. | S0 and every later phase | No remaining execution blocker from repository-state provenance. | Preserve this closure record. | Resolved. |
| P0-B02 | **RESOLVED:** MS-01/MS-02 leave every fixed 12-inch SMB-to-BNC bulkhead assembly installed, move only the explicitly identified downstream BNC connection, and require exact restoration of `CLOCK-SPLITTER-01` before clock-dependent recipes. | MS-01, MS-02, dependent timing and OP-01 | No remaining connection-instruction blocker after validation and inclusion in the clean baseline commit. | Preserve the corrected procedure and wiring record in the controlled history. | Resolved. |
| P0-B03 | Replacement reference detector is still in shipment; SIP and detector serial numbers are unknown. | DET-01/DET-02, SP-02, OP-01, E2E-01 | **Execution blocker for reference-detector-dependent work.** | Inspect and record the replacement physical labels after arrival; update configuration/manifest and associated certificate mapping. | Yes through S0 and independent electrical phases. |
| P0-B04 | Calibration certificates are reported available for PicoScope, T660s, MIRcat, HF2LI, Nd:YAG/OPO, and detector equipment, but certificate identifiers, issuers, dates, recalibration dates, uncertainties, and exact equipment associations are unavailable. | Measurement uncertainty budgets, RPT-01, PROM-01; equipment-specific claims | Does not block S0; **limits traceability and may block final uncertainty/traceability claims**. | Retrieve each certificate and transcribe the required metadata without claiming traceability until association is verified. | Yes, but not beyond the associated final claim gate. |
| P0-B05 | **RESOLVED:** S0 read back both T660 identities after ownership and disabled-output verification. T660-1 serial `00369` and T660-2 serial `00431` both reported firmware `28E660-1-1.7`. | S0, T2-01, T1-01, PT-01 | No remaining firmware-identity limitation for MS-01. | Preserve `readbacks/S0/t660_identity_firmware.json`. | Resolved. |
| P0-B06 | Polystyrene and Mylar references have no supplied certificates, authoritative peak lists, or stated spectral uncertainty; the polystyrene card has no path length and the Mylar thickness has no tolerance. | SP-01, SP-02, RPT-01, PROM-01 | Does not block relative comparison; **limits or prevents traceable absolute-wavenumber and quantitative path-length claims**. | Obtain authoritative manufacturer/literature feature values and uncertainties or use a certified reference. Otherwise report relative/non-traceable results only. | Yes, with explicit limitation of final claims. |
| P0-B07 | Freshliance TagPlus-TN has no calibration certificate or stated measurement uncertainty. | Environmental reporting and uncertainty budgets | Does not block execution; **limits traceable environmental claims**. | Obtain manufacturer accuracy specifications or use a calibrated environmental instrument. Otherwise retain readings as non-traceable observations. | Yes. |
| P0-B08 | `CLOCK-SPLITTER-01` is unmarked. Its reported 50-ohm impedance is from an undocumented prior measurement; bandwidth, insertion loss, branch symmetry, and uncertainties are unknown. | MS-02, OP-01 | Does not block MS-02 because that phase is intended to characterize it; **blocks using manufacturer-style specifications or unmeasured corrections**. | Measure branch skew, pulse fidelity, amplitude/loading, swap orientation, and reconnection repeatability with the actual splitter. | Yes until MS-02. |
| P0-B09 | Cable-length uncertainties and electrical propagation delays are unknown. | MS-01 onward, closure and uncertainty budgets | Physical lengths alone are not accepted as timing corrections; later direct measurements are required. | Measure actual route delays/skews and retain exact setup assignments and raw traces. | Yes; resolving these terms is the purpose of later electrical phases. |
| P0-B10 | Detector response delay/uncertainty and final sample-plane optical placement uncertainty are not established. OP-01 measures T660-1 CHB output-to-sample optical latency with the actual Q-switch cable and loaded Nd:YAG branch installed, then removes the MS-01 scope, MS-02 splitter, OP-01 adapter engineering correction, and detector-response contributions. | OP-01 | A corrected sample-arrival claim requires the detector correction and placement evidence. This does not prevent independent electrical phases. | Characterize the detector/electrical response and record the sample/sample-equivalent detector placement before reporting the corrected optical result. | Yes through earlier electrical phases. |

## Gate conclusion

`P0-B01`, `P0-B02`, and `P0-B05` are resolved. S0 is complete. No remaining
table entry prevents MS-01; later-phase missing information remains
`USER_INPUT_REQUIRED` and may not be silently assigned zero or represented as
measured.

## Current-scope addendum (updated 2026-08-15)

The table above is the preserved P0 assessment and is not rewritten to imply
that later phases existed at P0 closure. The current authoritative dependency
and status records are `analysis/calibration_matrix.csv`,
`analysis/expansion_gap_map.md`, `plans/campaign_sequence.md`, and
`manifests/p0_requirement_decisions.md`.

For current planning, replacement-detector identity and calibration metadata
in P0-B03 also affect DET-03, DET-04, characterization AR-01/SV-02/PF-01, and
later biological normalization. P0-B08 addresses only the electrical timing
splitter used in MS-01/MS-02/OP-01; it must not be confused with the installed
optical sample/reference splitter calibrated by ATT-01 and DET-04. Current
campaign records use stable IDs, paths, sizes, timestamps, and explicit
versions as defined by the repository-level provenance rules.

All P0 requirement decisions were completed on 2026-08-15. P0-D001 was
retained, so P0-B03 remains an execution blocker for replacement-reference-
detector-dependent phases only until the detector arrives and its SIP
model/serial and detector model/serial are recorded. Certificate association
is not required. This does not require repeating completed work.

P0-B04 is superseded for active planning: certificate retrieval for the
T660s, MIRcat, Nd:YAG/OPO, HF2LI, detectors, SIP electronics, and power
supplies was discarded. PicoScope evidence was narrowed to serial `10261`,
actual timebases/ranges used, and applicable manufacturer accuracy. P0-B06 was
narrowed to authoritative polystyrene features/uncertainty and authoritative
Mylar validation features/uncertainty; film thickness and quantitative etalon
claims were discarded. P0-B07 was discarded as a calibration requirement;
temperature and humidity remain observational conditions only.

Generic interface and adapter manufacturer-part research was also discarded.
Stable IDs, wiring authority, photographs, directly measured behavior, and
requalification after material replacement remain sufficient.
