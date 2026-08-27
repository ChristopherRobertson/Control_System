# HF-01 retention audit

Audit status: **PASS**

The final read-only audit confirmed:

- 42 unique attempted acquisitions are indexed;
- 22 acquisitions are accepted and 20 are rejected, partial, diagnostic-only,
  or superseded with explicit disposition codes;
- every top-level raw acquisition ID has an `acquisition_index.csv` row and a
  stable raw-primary artifact link;
- every retained phase file has a unique artifact ID, existing relative path,
  byte size, timestamp, producer, role, and immutability disposition;
- 533 retained files are represented in `artifacts.csv`;
- canonical headers are present for all six required contract tables;
- 197 condition rows, 88 measurement rows, and 25 exclusion rows are retained;
- measurement numeric fields are numeric and correction states are explicit;
- selected configuration, uncertainty/acceptance, calibration-link, final
  report, and revalidation-trigger records exist;
- `restoration_confirmation.json` and
  `HF01-FINAL-RESTORATION-STATE-R1-001` establish physical restoration and the
  final electronic safe state; and
- `promotion_performed` is false.

The audit uses stable identifiers, relative paths, byte sizes, UTC timestamps,
versions, and source records. It does not use content-hash matching as an
operational gate. The mutable indexes remain the aggregation authorities; a
later packaging or commit operation may change their timestamps without
invalidating the retained measurement evidence.
