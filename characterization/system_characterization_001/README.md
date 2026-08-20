# Pump-probe system characterization run

Campaign: `system_characterization_001`

Status: **CH-00 COMPLETE; MINIMUM GRID FROZEN; NO PHASE APPROVED FOR HARDWARE EXECUTION**

This campaign characterizes the pump source, OPO, MIRcat probe, sample-plane
geometry, optical overlap, acquisition response, spectral performance,
temporal response, sensitivity, stability, and reproducibility needed for the
thesis and downstream experiments.

Campaign advancement is controlled by phase dependencies, mandatory
deliverables, acceptance decisions, and explicit authorization rather than a
calendar timeline. Recorded acquisition timestamps remain evidence; they are
not completion deadlines.

Before CH-00 freezes the characterization grid, requirements-level experiment
designs define the claims, wavelengths, powers, delays, controls, and
observables actually needed. Numeric experimental recipes still wait for
promoted calibration and characterization results. This ordering prevents
unused characterization work.

The verified minimum scope is one local Mylar/polystyrene carbonyl window, one
combined 1885-1980 cm^-1 HRP/MbCO probe region, 355 nm only as the drive for
the shared post-iris 540 nm OPO pump used by HRP first and MbCO second, and two acquisition topologies:
probe-only continuous sweep and finite rare-pump fixed-wavenumber/recovery.
The OPO-540 path is characterized only with the permanent ATT-01-qualified
USB/API electronic iris installed at its selected far-field plane and accepted
diameter. The setting is 540 nm-specific because wavelength-dependent X/Y beam
walk is not assumed negligible. No broad OPO/iris map is added; another OPO
wavelength requires separate iris/centroid qualification before use.
Center-wavelength/status records use the WM-01-qualified Coherent WaveMaster
configuration and retain its bundle, device/adapter/probe identity, units,
pulsed mode, autocalibration state, native time tag/value/status, and
uncertainty. The WaveMaster does not apportion optical power among simultaneous
wavelengths and does not cover the 355 nm OPO drive.
`SC-01` qualifies the minimum gas-tight cell/path and 293 K/298 K temperature
states without biological material or CO. The complete mapping and exclusions
are in `docs/experiment_requirement_campaign_crosswalk.md`.

The available optical metrology includes a power meter but no energy meter.
Characterization therefore measures average power. Mean pulse energy may be
derived from average power and verified repetition rate with an explicit
limitation; direct pulse-energy distributions and calibrated peak power are
outside the current plan.

It imports calibration results from `system_recalibration_001` by stable bundle
and artifact identifiers. It does not rerun S0, MS-01, MS-02, T2-01, T1-01, or
any later promoted calibration solely for convenience.

Quantitative dual-detector phases must import ATT-01, DET-02, and DET-04. The
installed sample/reference splitter is not assumed to be 50/50: DET-04 supplies
the wavelength-dependent optical balance, detector/electronics balance,
normalization correction, uncertainty, and revalidation triggers.
All OPO-540 phases also import ATT-01's iris-control, permanent-mount, halo-
rejection, core-margin, and post-iris transfer configuration. The iris remains
static within an emitted block and is never treated as a safety shutter or
finite-event limiter.
They also import WM-01 for wavelength identity and ATT-01/PB-02 for the
residual spectral-power bound; those two authorities are not interchangeable.

The authoritative plan is `plans/characterization_sequence.md`; the phase and
retention matrix is `analysis/characterization_matrix.csv`. No phase readback
directory is created until that phase is approved. Biological samples and
kinetic experiments are outside this campaign and begin only after the
characterization promotion gate.

SV-02 uses a declared polystyrene partition to define and freeze the final
wavenumber-alignment correction. Mylar is the independent validation standard.
Neither Mylar nor any biological spectrum may fit or revise the correction.
