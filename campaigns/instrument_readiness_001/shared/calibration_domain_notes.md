# Calibration domain notes

The unified phase authority is `campaigns/phase_registry.yaml`. This file
preserves cross-phase calibration rules and background only. Detailed procedures
live in the corresponding `../phases/<phase-id>/plan.md`; completed evidence stays
under its registered `evidence/calibration/` root. There is no independent
calibration directory hierarchy or execution order.

Each calibration campaign has one canonical campaign definition under `campaigns/`
and one evidence root under `evidence/calibration/<campaign-id>/`. Each phase root
is the complete evidence unit for provenance, readbacks, raw acquisitions,
analysis, figures, tables, troubleshooting, bypass records, photographs,
restoration, final report, and procedural writeup.

Canonical promoted `timing_calibration.csv` and `timing_offsets.yaml` outputs are
absent to preserve the clean-slate state. The legacy versions are preserved outside
the repository at
`C:\Users\Chris\Documents\GitHub\Control_System_Archives\archive\20260723_legacy_timing_measurements`
and are comparison evidence only. They must not be copied back as active
calibration inputs. New measurements remain in their registered phase evidence
packages. A control-system input may be created only in an explicitly versioned
bundle under `instrument/promoted_bundles/` after the comprehensive campaign
dependencies and closure tests pass, uncertainties are reviewed, and the user
explicitly approves the registered promotion phase.


Operational UI runs that are not calibration evidence continue to use `evidence/experiments/runs/`.

New phase records follow `docs/data_contract/measurement_campaign_data_contract.md`, which
uses stable human-readable identifiers, paths, sizes, timestamps, versions,
settings records, and artifact indexes allowed by the repository-level
provenance rules. Completed evidence is indexed in place and is not reacquired
merely to change format.

Every phase also follows `docs/data_contract/procedural_writeup_standard.md`.
`procedural_writeup.md` must explain WHY the phase was required, HOW it was
actually executed step by step, WHAT it found, and the resulting implications,
caveats, limitations, and bounded claims. It is separate from `final_report.md`
and must be indexed, manifest-linked, and reviewer-accepted before closeout.

Instrument-performance work downstream of calibration belongs in the
characterization domain of the unified campaign and in a separate
`evidence/characterization/<campaign-id>/` evidence unit. The active
`system_characterization_001` campaign imports promoted calibration bundles;
quantitative dual-detector work depends on ATT-01, DET-02, and DET-04 rather
than assuming a 50/50 sample/reference split.

## Calibration orchestration

Calibration campaigns are conducted as Codex-guided operator sessions. The
technical procedure remains authoritative, but it is not executed as one
monolithic command.

For each approved phase, Codex reads the applicable procedure, presents one
physical action at a time, waits for the operator's actual observation, and
uses small utilities only for direct ownership, readback, acquisition, or
analysis. Evidence is accumulated under the canonical registered phase root in
`evidence/calibration/<campaign-id>/phases/<phase>/`. Unavailable information is
recorded as `USER_INPUT_REQUIRED`, and Codex stops at the approved phase
boundary after guiding restoration.

The retired monolithic complete-calibration runner is archived outside the active
repository. Campaign phases use only the approved phase-local plan and focused
utilities.
