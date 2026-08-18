# PT-01 deviations

## DEV-PT01-001 — inherited status metadata label

The retained T1-01 focused acquisition engine was reused without modifying
immutable completed T1-01 code. Its generated Setup 1 `status.json` contains
`"phase": "T1-01"`, although the same file identifies Step 8 and measurement
`TC-08` and resides under the stable PT-01 directory. The original file is
preserved unchanged. This manifest, acquisition index, artifact index,
analysis, and report carry the authoritative `PT-01` phase ID. No measurement
content, settings, raw trace, or acceptance result is affected.
