# Steady-state slow scans

The **Slow Scan** and **DD Slow Scan** tabs acquire unpumped static
sample spectra and keep pump FIRE and Q-switch outputs OFF. Single and dual tabs
have independent settings, controls and results.

## Operation

1. Select the top-bar save location and the **Start** and **End** wavenumbers within
   the connected QCL 1 limits. Set **Scan speed** from 0.1 to 10,000 cm⁻¹/s,
   **Current** in mA, repetition rate, **Pulse width** in ns and **Number of Scans**
   for each direction. Pulse width
   programs the MIRcat laser pulse duration; the T660 electrical trigger width
   is selected automatically and remains separate. Repetition rate in Hz
   multiplied by pulse width in seconds must not exceed the smaller of 0.30
   and the connected controller's
   duty limit. The configured MIRcat internal pulse duty uses the same bound.
   Connected current, frequency and pulse-width limits also apply. Overrides remain visible;
   each can be changed independently. **Sampling rate (Sa/s)** in Advanced overrides
   accepts a supported detector sampling rate or **Auto**. Dual mode has independent
   sample and reference sampling-rate controls.
2. In single mode, load the background when a blank is wanted and acquire
   **Blank**. Then load the sample and acquire **Sample**. Detector dark data
   are acquired automatically
   when no compatible dark is available. A blank is optional for raw sample data;
   in dual mode sample and reference are recorded together.
3. Inspect the spectra by direction and repeat. Select raw signals,
   reference-normalized ratio or available absorbance. Numeric coordinates
   select actual observations. Acquisition does not assume a peak model or fit
   peaks automatically. Existing fits in loaded records remain available.
4. Use Save/Load Plan, saved-run loading, Export data or Export selection as needed.
   Export selection records the operator's chosen windows directly. Names and
   sample annotations are optional; no review or acceptance checkbox is required.
   New run clears this tab's current controls and results without deleting files.

HF2LI input range requests use the actual MIRcat current readback and follow the
specified operating rule below: proportional to current below 500 mA, linear
between the listed higher-current points, with a 1 mV floor and a 2 V cap.
Both detector inputs use this rule. It is an operating rule, not an instrument
calibration.

| Current (mA) | Requested range (V) |
| --- | --- |
| 0 | 0.001 |
| 500 | 1 |
| 750 | 1.75 |
| 1000 | 2 |

The requested voltage is sent to HF2LI. The instrument may select a different
supported range. Both requested and actual values are retained, and control
compatibility uses the actual readback.

After configuration and immediately before emission, actual T660 repetition
rate and MIRcat pulse, current and limit readbacks are checked and retained.

Protein, sample, temperature and preparation annotations do not choose an
acquisition recipe or prevent an operation. No promoted qualification profile is
required for ordinary raw or relative spectra. Applicable optional calibrations
can improve the reported physical quantities; missing calibration remains visible
as a limitation of the result.

**Stop** stops only this tab's operation. Native observations and partial results
are preserved while the software attempts restoration and verifies outputs OFF.
A normal stop is reported as **Acquisition stopped**; actual device, cleanup and
storage errors remain visible. Physical instrument access, including discovery,
is exclusive through the host until cleanup and preservation finish.

## Quantities and interpretation

HF2LI is the spectral recorder. Individual directions and repeats remain separate.
Missing intervals are not filled automatically. Original detector streams,
integer timestamps, controller markers and axes remain available alongside
processed values and any applied corrections.

The dual-detector quantity is the reference-normalized ratio \(Q=S/R\). With a
compatible unpumped reference \(Q_0\), the additional comparison is
\(\Delta A=-\log_{10}(Q/Q_0)\). Absolute dual absorbance requires an applicable
measured path-balance factor \(B\): \(A=-\log_{10}(Q/B)\). Without B the result
remains a ratio. Single-detector absorbance uses the sample divided by its
compatible sequential blank. Without that blank the sample signal remains raw.

Available sample/reference variances and covariance are propagated through the
ratio. Unknown uncertainty remains unknown. Loaded analyses retain their
original models, residuals, covariance and model alternatives. Their fitted
uncertainty is conditional on those models and noise inputs; unavailable axis
calibration cannot establish calibrated peak centers. Unsupported corrections
are omitted while raw and relative results remain usable.

## Saved data

Each operation freezes its output root and saves under
`<root>/measurements/steady_state_slow_scan/<single|dual>/<run_id>/`.
`run.json`, `native.npz` and incremental `native_chunks/` preserve native values,
readbacks, individual sweeps, analysis and restoration records. Reanalysis and
exports create separate records. Existing version-1 plans and runs remain
readable, including their optional legacy annotations and saved fit results.
Historical resolution, linewidth, segment and fit settings are preserved as
metadata; they do not select a new acquisition's range, speed or peak model.

Selection exports use the host's standalone version-1 `SampleSpectralSelection`
format. Its legacy accepted disposition records the operator's export action;
it does not certify physical sample state, instrument readiness or temperature.
The record identifies raw/relative/calibrated quantities, uncertainty limitations,
quality flags and the retained source. Missing actual sample identities are marked
as unavailable; run-local identifiers do not invent material identity. An export
neither promotes an instrument bundle nor accepts a campaign phase.

Hardware-free verification is available with:

```powershell
python -m pytest software/tests/measurement_modules/steady_state_slow_scan -q
```

Verification exercises the installed adapters through injected transports in both
detector modes, including Blank/Sample reuse, delayed PLL lock, cancellation,
device failures and restoration. No physical measurements were taken during
development.
