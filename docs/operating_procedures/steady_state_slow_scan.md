# Steady-state slow scans

The **Slow Scan** and **Dual-Detector Slow Scan** tabs acquire unpumped static
spectra. Both use the same Blank/Sample workflow and keep pump FIRE and Q-switch
outputs OFF. Single and dual tabs have independent settings, controls and results.

## Operation

1. Select the top-bar save location, spectral range, resolution and repeats.
   Normal acquisition reads the connected instruments and chooses QCL segments,
   scan speed and detector settings automatically. Independent manual overrides
   are available under **Advanced**; the other settings remain automatic.
2. Load the background when a blank is wanted and acquire **Blank**. Then load
   the sample and acquire **Sample**. Detector dark data are acquired automatically
   when no compatible dark is available. A blank is optional for raw sample data;
   in dual mode sample and reference are recorded together.
3. Inspect the spectra by segment, direction and repeat. Select raw signals,
   reference-normalized ratio or available absorbance, with fit overlays,
   residuals and the peak table. Numeric coordinates select actual observations.
4. Use Save/Load Plan, saved-run loading, Export data or Export selection as needed.
   Export selection records the operator's chosen windows directly. Names and
   sample annotations are optional; no review or acceptance checkbox is required.
   New run clears this tab's current controls and results without deleting files.

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
ratio. Unknown uncertainty remains unknown. Gaussian or Lorentzian peak fits use
free centers, widths and heights, with selectable polynomial and fringe baselines.
Residuals, overlap covariance and model alternatives are retained. Fitted
uncertainty is conditional on the model and noise inputs; unavailable axis
calibration cannot establish calibrated peak centers. Unsupported corrections
are omitted while raw and relative results remain usable.

## Saved data

Each operation freezes its output root and saves under
`<root>/measurements/steady_state_slow_scan/<single|dual>/<run_id>/`.
`run.json`, `native.npz` and incremental `native_chunks/` preserve native values,
readbacks, individual sweeps, analysis and restoration records. Reanalysis and
exports create separate records. Existing version-1 plans and runs remain
readable, including their optional legacy annotations.

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
