# Calibration experiments

Each calibration campaign lives in one uniquely named `calibration/<campaign-id>/` directory. The directory is the complete archival unit for its plan, provenance, readbacks, raw acquisitions, analysis, figures, tables, troubleshooting, bypass records, photographs, and final report.

Canonical `timing_calibration.csv` and `timing_offsets.yaml` outputs are absent
to preserve the clean-slate state. The legacy versions are preserved outside
the repository at
`C:\Users\Chris\Documents\GitHub\Control_System_Archives\archive\20260723_legacy_timing_measurements`
and are comparison evidence only. They must not be copied back as active
calibration inputs. New canonical files may be created at the root of this
directory only after the comprehensive campaign dependencies and closure tests
pass, uncertainties are reviewed, and the user explicitly approves promotion
with `APPROVE CALIBRATION PROMOTION`.

Git tracks campaign plans, manifests, analyses, tables, reports, and directory structure. Large `raw_pico_traces`, `raw_hf2li`, and `raw_mircat` contents remain ignored for local storage and later archival; raw-data indexes and hashes remain trackable.

Operational UI runs that are not calibration evidence continue to use `runs/`.
