# MIRcat/HF2LI DIO mapping — side-experiment confirmation

Campaign: `20260722_complete_system_recalibration_001`
Recorded: `2026-07-29` (`America/Los_Angeles`)
Operator/source: `Christopher Robertson`
Evidence class: **operator-confirmed side experiment**
Repository base commit: `f09db335e9dce66ef0b3df77867f3eb5ef3f275a`
Updated recipe: `recipes/mircat_sweep_scan.yaml`
Updated recipe SHA-256:
`807603b07fc673a447e6023d2fff6cf108bfbeef8e14a03d910db794e2cd36a9`

## Accepted mapping

| MIRcat DB9 signal | HF2LI complete captured-word bit |
|---|---:|
| Pin 1 — Scan Direction | `20` |
| Pin 2 — Tuned / Sweep Active | `21` |
| Pin 3 — Wavelength Trigger | `22` |

Christopher Robertson confirmed that this mapping was established in a
side experiment. The mapping may therefore be used in documentation,
calibration planning, and software configuration instead of being represented
as unknown.

This campaign-local record supersedes older statements that the captured-word
bit positions were unverified. Historical P0 provenance and recipe-hash
snapshots remain unchanged as dated evidence; they must not be rewritten.

## Evidence boundary

The side-experiment confirmation establishes only the three bit assignments.
The campaign has not yet acquired or archived its own MD-01 dataset. The
side-experiment date, exact setup, command log, raw HF2LI stream, MIRcat log,
scan settings, repetitions, direction sequence, and artifact hashes were not
supplied to this campaign record and remain unavailable here.

Accordingly, this record does **not** complete MD-01 and does not establish:

- bit polarity or high/low state semantics under every scan state;
- repeated forward/reverse direction behavior;
- wavelength-trigger pulse counts, spacing, width, or jitter;
- Sweep Active segment/gap timing or channel-transition behavior;
- timestamp alignment between MIRcat and HF2LI records;
- dropped-sample behavior, repeatability, or uncertainty;
- trigger-derived wavelength-axis accuracy or end-to-end scan validity.

Those measurements remain required under MD-01, MSW-01, and HF-02. Their
future run-local evidence must not be replaced by this mapping-only record.
