# HF-01 deviations and retained failed attempts

## HF01-DEV-001 — photographs declined

The operator declined temporary-topology and restoration photographs. Physical
state is established by `HF01-OPCONF-003`, `HF01-OPCONF-004`, and the sequential
restoration confirmations through `HF01-OPCONF-014`. No photograph is
fabricated, inferred, or treated as present.

## Superseded and rejected acquisitions

All failed, partial, diagnostic, and superseded attempts are retained in
`acquisition_index.csv` and `exclusions.csv`. They include the timing-export and
poll-window corrections, v1 cross-clock response limitations, the exploratory
v2 paired pipeline, the first v3 slow settling failure, rejected lower-rate
neighbors, the failed analog-reference diagnostic, and the first final-
restoration readback blocked by COM3 contention.

Prospective v3 governing documents and new stable acquisition IDs were used for
acceptance. Earlier evidence was not rewritten to appear as though it had been
acquired under the final method.

## Documentation route correction

The final T660-2 channel-B destination is MIRcat `TRIG IN`. Two HF-01 checklist
references that called it an external-reference input were corrected before
restoration acceptance. The underlying default route was already documented in
the repository timing recipes and hardware reference.
