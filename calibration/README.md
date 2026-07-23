# Calibration experiments

Each calibration campaign lives in one uniquely named `calibration/<campaign-id>/` directory. The directory is the complete archival unit for its plan, provenance, readbacks, raw acquisitions, analysis, figures, tables, troubleshooting, bypass records, photographs, and final report.

Canonical `timing_calibration.csv` and `timing_offsets.yaml` outputs are currently absent to preserve the clean-slate state. They may be created at the root of this directory only after the comprehensive campaign dependencies and closure tests pass, uncertainties are reviewed, and the user explicitly approves promotion.

Git tracks campaign plans, manifests, analyses, tables, reports, and directory structure. Large `raw_pico_traces`, `raw_hf2li`, and `raw_mircat` contents remain ignored for local storage and later archival; raw-data indexes and hashes remain trackable.

Operational UI runs that are not calibration evidence continue to use `runs/`.
