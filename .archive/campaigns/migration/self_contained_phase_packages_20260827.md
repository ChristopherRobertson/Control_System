# Self-contained phase-package consolidation

Date: `2026-08-27`
Branch: `codex/physical-unified-layout`
Source-layout commit: `704193d`

## Final invariant

Each registered phase has exactly one canonical directory:

```text
campaigns/<campaign-directory>/phases/<phase-id>/
```

That directory contains the prospective plan and metadata and, once work occurs,
all generated phase material: contemporaneous overview, readbacks, raw/native
acquisitions, command/operator records, manifests and indexes, analysis source and
results, figures, tables, troubleshooting, deviations, reports, restoration, and
procedural writeup. There is no second calibration or characterization evidence
tree.

The top-level `evidence/` directory remains only for generic GUI/operational runs
and cross-campaign catalogs that are not registered phase packages.

## Physical relocation

The following package contents were moved directly into the matching
`campaigns/instrument_readiness_001/phases/<phase-id>/` directory:

| Phase | Files moved | Bytes moved |
| --- | ---: | ---: |
| `P0` | 8 | 53,961 |
| `S0` | 9 | 180,945 |
| `MS-01` | 233 | 289,330,627 |
| `MS-02` | 226 | 286,810,604 |
| `T2-01` | 1,898 | 940,518,191 |
| `T1-01` | 3,056 | 1,975,959,951 |
| `PT-01` | 657 | 1,372,654,544 |
| `MC-01` | 108 | 4,127,925 |
| `TR-01` | 17 | 37,431 |
| `OM-01` | 46 | 174,947 |
| `HF-01` | 561 | 2,682,968,186 |
| `WM-01` | 40 | 90,492 |
| `CH-00` | 22 | 36,532 |
| **Total** | **6,881** | **7,552,944,336** |

Before each source directory was removed, every file was verified at its target by
relative path and byte size. The current 13 phase directories contain 6,934 files:
the 6,881 relocated files plus the 53 plan/metadata files already present in those
canonical homes. Of the relocated content, 6,184 files are below `raw/` directories
and remain present locally under the updated ignore policy.

Eleven source packages contained an evidence `README.md` that would have collided
with the canonical phase `README.md`. Each source file was preserved as
`run_record.md`; its bytes and content were not overwritten. P0 and CH-00 did not
have this collision. The cross-phase photograph
`op01_bnc_barrel_adapter.jpg` was assigned to `OP-01/photos/`.

## Removed intermediate containers

After verification, the empty intermediate paths were removed:

- `evidence/calibration/`
- `evidence/characterization/`

Their tracked history is recoverable from Git. Ignored raw data is preserved in the
new phase directories and in the operator's pre-restructure external backup.

## Path metadata

The evidence-location registry and every `phase.yaml` now identify the phase
directory itself as `evidence_path`. Current plans, procedures, recipes, manuals,
tests, and audit tools use the self-contained paths. Relative cross-repository
entries in OM-01 and WM-01 `artifacts.csv` were adjusted by one directory level so
they continue to resolve to the identical referenced files.

Historical manifest dirty-file/source-path strings remain unchanged where they
record the repository state observed during execution. They are provenance, not
active alternate locations.

## Preservation and behavioral checks

- Stable phase-file counts meet or exceed every pre-move minimum.
- Scientific phase statuses are unchanged.
- Artifact indexes have no unresolved paths.
- Acquisition, artifact, and exclusion stable IDs have no duplicates.
- `evidence/calibration/` and `evidence/characterization/` are absent.
- The phase registry validates all 68 phases and their dependency order.
- The focused layout/GUI suite passes 13 tests.
- The complete software suite passes 80 tests and 24 subtests, with 3 expected
  skips.
- The physical preservation audit covers all 13 retained phase packages with no
  missing or unresolved artifacts.
- Reconstruction resolves 675 acquisition IDs, 1,380 artifact IDs, and 3
  exclusion IDs with no duplicates or unresolved artifact paths.
- Repository checks use counts, sizes, paths, IDs, and statuses; hash matching is
  not an operational gate.
