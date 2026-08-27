# Codex instructions for experimental campaigns

These instructions apply to biological experiment campaigns under `campaigns/`.

Requirements-level experimental design precedes final calibration and
characterization scope: define the intended claims and operating conditions
first. Numeric settings and executable experiment recipes remain downstream
of promoted calibration and characterization results and may not claim
readiness until required bundle IDs and validity envelopes are identified.

Design horseradish-peroxidase and myoglobin-CO campaigns from first principles
using the canonical theoretical notebook and promoted instrument results. Do
not reuse archived Day-based, publication-specific, or sample-specific recipes
as defaults. Biological data never define or revise instrument calibration.

Each campaign must define sample preparation and state verification, controls,
exposure and recovery limits, spectral windows, delay schedule, replicate
structure, acceptance criteria, uncertainty inputs, data retention, safe
restoration, and promotion independently.

Every biological phase must produce the thesis-quality `procedural_writeup.md`
defined by `../docs/data_contract/procedural_writeup_standard.md`. In addition to
the common WHY/HOW/WHAT/implications structure, document material identity and
preparation history, controls, randomization, independent preparations and
replicates, exposure, exclusions, pre/post integrity, sample disposition, and the
exact population to which each claim applies. A final report or notebook output
alone is insufficient for closeout.

Do not assume an energy meter is available. Use measured average power and a
verified repetition rate for any explicitly derived mean pulse energy, and do
not claim direct pulse-energy distributions or calibrated peak power without
new approved metrology.
