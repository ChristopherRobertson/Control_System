# Pre-restructure checkpoint and evidence inventory

Checkpoint branch: `codex/pre-unified-layout-20260827`  
Checkpoint commit: `654f896`  
Restructure branch: `codex/unified-campaign-layout`

The checkpoint includes the intended 2026-08-26 campaign reconstruction and excludes
the pre-existing untracked `tmp/` directory. Baseline verification before layout
changes:

- 67 tests passed, 3 skipped, and 24 subtests passed;
- the Qt GUI instantiated offscreen with a blocked no-hardware handler;
- window title was `IR Spectroscope Control System`; and
- all six tabs were present.

Indexed evidence baseline:

| Record | Files | Data rows | Bytes |
|---|---:|---:|---:|
| acquisition indexes | 7 | 675 | 271009 |
| artifact indexes | 7 | 1380 | 417545 |
| calibration links | 7 | 43 | 13083 |
| conditions | 7 | 882 | 138518 |
| exclusions | 7 | 53 | 17715 |
| measurements | 7 | 138 | 38018 |
| phase manifests | 7 | — | 18410 |
| final reports | 10 | — | 32622 |
| restoration confirmations | 11 | — | 9270 |

No completed evidence is moved by the unified hierarchy. Post-restructure audits
must reproduce these counts and byte totals exactly and report, rather than alter,
pre-existing unresolved artifact paths.
