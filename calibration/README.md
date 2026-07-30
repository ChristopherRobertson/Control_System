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


Operational UI runs that are not calibration evidence continue to use `runs/`.

## Calibration orchestration

Calibration campaigns are conducted as Codex-guided operator sessions. The
technical procedure remains authoritative, but it is not executed as one
monolithic command.

For each approved phase, Codex reads the applicable procedure, presents one
physical action at a time, waits for the operator's actual observation, and
uses small utilities only for direct ownership, readback, acquisition, or
analysis. Evidence is accumulated under
`calibration/<campaign-id>/readbacks/<phase>/`. Unavailable information is
recorded as `USER_INPUT_REQUIRED`, and Codex stops at the approved phase
boundary after guiding restoration.

`tests/hardware_checks/check_complete_timing_calibration.py` is retained only
as legacy/internal implementation and test support. Codex must not invoke it
to conduct a campaign phase.
