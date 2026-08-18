# Experimental campaigns

This directory is reserved for thesis experiments. Define the scientific
questions, claims, controls, sample conditions, wavelengths, power ranges,
delays, and required observables before freezing the remaining calibration and
characterization scope. This requirements-level design determines the minimum
instrument work and prevents unused characterization.

Experimental advancement is dependency- and gate-driven. No calendar deadline
may bypass preparation, safety, calibration, characterization, controls,
acceptance, retention, or restoration requirements.

Planned campaign families:

- horseradish-peroxidase spectroscopy and kinetics, defined at requirements
  level in `horseradish_peroxidase_requirement_brief.md`;
- myoglobin-CO spectroscopy and kinetics, defined at requirements level in
  `myoglobin_co_requirement_brief.md`.

No legacy recipe is active here. Numeric settings and executable recipes are
finalized only after the required calibration and characterization results are
available. Each future campaign imports the promoted bundle IDs, uses the
validated operating envelope, and obtains phase-specific approvals.
Polystyrene and Mylar remain in characterization SV-02 and are not biological
experiment campaigns.

The three verified briefs and their minimal calibration/characterization
mapping are recorded in `docs/experiment_requirement_campaign_crosswalk.md`.
Actual prepared-protein FTIR and UV-visible state checks remain experiment
work; they are not added to SV-01 or SV-02 and cannot revise instrument
corrections.

The current lab has a power meter but no energy meter. Experimental claims
must therefore be designed around measured average power unless an energy
meter is later borrowed. Mean pulse energy may be derived from average power
and verified repetition rate with an explicit limitation; direct pulse-energy
distributions, pulse-to-pulse energy jitter, and calibrated peak power are not
available from the current metrology.
