# WM-01 evidence correction

At `2026-08-21T16:44:56Z`, the initial electronic capture utility was reused
for a recovery check after its output had already been indexed. That utility
used a fixed output filename and overwrote the indexed file. The two captures
were immediately separated:

- `raw/initial_electronic_snapshot.json` was restored verbatim from the
  already-retained command output for the `16:24:23Z` capture.
- `raw/post_settings_recovery_snapshot.json` retains the later `16:44:56Z`
  capture that had overwritten the fixed filename.

The correction is explicit; neither acquisition was repeated to change a
result. The fixed-name utility is not used again during this phase. Closeout
indexes both artifacts separately and classifies the restored initial JSON as
recovered-from-retained-session-output rather than an untouched native file.
