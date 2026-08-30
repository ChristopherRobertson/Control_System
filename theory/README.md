# Theory and scientific models

The canonical theoretical notebook remains outside this repository at its recorded
location. This directory is reserved for versioned exports, executable derivatives,
parameter schemas, and validation fixtures under `notebooks/`. Saved notebook output is not measurement
evidence and cannot substitute for a promoted instrument result.

## Deferred Mathematica notebook integration

`notebooks/Theoretical_Calculations.nb` is retained for cross-reference, but its
campaign integration is incomplete and will be addressed later. The notebook
currently contains 128 explicit `Missing["ValueRequired"]` entries across 12 input
associations, including 13 unset CSV paths. Several entries repeat the same
scientific quantity for HRP, MbCO, scalar calculations, and uncertainty
distributions.

The principal missing calibration and characterization products are the
polystyrene and Mylar FTIR/QCL datasets and calibration-peak table; accepted QCL
linewidth, scan-axis, tuning, and warm-up values; FTIR acquisition metadata;
polymer geometry and reference properties; final HF2LI and scan settings;
sample-plane power, wavelength, beam geometry, and pump-probe overlap; detector
gain, response, latency, noise, and saturation results; wavelength-dependent
dual-detector normalization and covariance; complete optical timing/IRF results;
baseline/SNR data; and the corresponding uncertainty distributions. These inputs
remain owned by the applicable planned or incomplete campaign phases. No value is
made valid merely by entering a placeholder, plan value, manufacturer nominal, or
unpromoted provisional result in the notebook.

Biological spectra, transients, sample conditions, concentrations, path lengths,
band parameters, quantum yields, kinetic parameters, and fit initialization values
are future HRP/MbCO experiment inputs rather than instrument-calibration outputs.
They also remain unset.

The following notebook-to-campaign interface issues are explicitly deferred:

1. The notebook requests `PumpPulseEnergy_J` as a measured quantity. The current
   campaign has no energy meter and permits only a derived mean pulse energy from
   measured average power divided by verified repetition rate, with propagated
   uncertainty and an explicit limitation. The notebook input semantics must be
   reconciled with that rule unless new approved energy metrology is introduced.
2. The dual-detector calculation does not expose explicit inputs for the DET-04
   wavelength-dependent optical, detector/electronics, and system balance tables,
   their covariance, drift limits, and validity envelope. A stable imbalance may
   cancel in the sample/background ratio-of-ratios, but its residual uncertainty
   and configuration dependence must still be represented.
3. The lock-in distortion calculation primarily represents stepped-QCL dwell
   behavior. Continuous-sweep use must incorporate the AR-01 scan speed and
   direction, marker-derived corrected wavenumber axis, native spacing, and
   measured filter/settling kernel rather than treating a commanded step as the
   acquisition model.

Until these inputs and interfaces are resolved, notebook outputs are theoretical
or diagnostic only. They cannot establish campaign completion, authorize hardware,
replace retained evidence, or supply a promoted control-application bundle.
