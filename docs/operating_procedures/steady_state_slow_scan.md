# Steady-state slow scans

The **Slow Scan** and **DD Slow Scan** tabs acquire unpumped static
sample spectra and keep pump FIRE and Q-switch outputs OFF. Single and dual tabs
have independent settings, controls and results.

## Operation

1. Select the top-bar save location and the **Start** and **End** wavenumbers within
   the connected QCL 1 limits. Start must be higher than End; the defaults are
   **2050 → 1650 cm⁻¹** at **40 cm⁻¹/s**. Set **Scan speed** from 0.1 to 10,000 cm⁻¹/s,
   and **Number of Scans** (default **1**) for the total number of descending
   Start-to-End scans. Acquisition uses only this direction.
   **MIRcat Settings** offers **Pulsed** (default) or **Continuous Wave**.
   Selecting a mode resets **Current** to **1000 mA** for Pulsed or **750 mA** for CW.
   The current remains editable and is checked against that mode's connected QCL limits.
   Repetition rate and **Pulse width** are editable only in Pulsed mode, defaulting
   to **2 MHz** and **150 ns**. These program the MIRcat's internal pulse generator;
   the independent T660 clock schedules scan Process Triggers. Repetition rate in Hz
   multiplied by pulse width in seconds must not exceed the smaller of 0.30
   and the connected controller's
   duty limit. The defaults give exactly **30%**. CW has no pulse duty limit;
   dormant pulse settings are retained but do not determine CW output.
   Connected frequency and pulse-width limits also apply in Pulsed mode.
   **Sampling rate (Sa/s)** in **HF2LI Settings**
   accepts a supported detector sampling rate or **Auto**. Dual mode has independent
   sample and reference sampling-rate controls.
2. In single mode, load the background when a blank is wanted and acquire
   **Blank**. Then load the sample and acquire **Sample**. Detector dark data
   are acquired automatically
   when no compatible dark is available. A blank is optional for raw sample data;
   in dual mode sample and reference are recorded together.
3. Inspect each recorded scan. Select raw signals,
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

After configuration and immediately before emission, the T660 timing clock and
MIRcat mode, temperature setpoint, pulse, current and limit readbacks are checked
and retained. CW additionally requires the controller to report CW support for QCL 1.
Cleanup restores the prior laser mode, current, pulse parameters and temperature
setpoint, as well as HF2LI settings, and verifies independent readbacks.

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

HF2LI is the spectral recorder. Individual scans remain separate. Stored
records retain their original directions and repeats.
New runs use DC-coupled HF2LI signal inputs and oscillator index 1 at zero frequency
with harmonic 1, phase 0 and sinc filtering disabled. Oscillator index 0 remains
locked to the independent T660 timing reference. The internal MIRcat pulse mode
allows the requested 2 MHz / 150 ns setting without an external-trigger headroom
requirement. T660-1 B, formerly the laser pulse trigger, stays OFF.

The plotted detector signal is the HF2LI zero-frequency demodulator magnitude,
not a calibrated optical power or validated mean intensity. Signed X/Y readings
are preserved in the native streams. The detector/preamp DC response remains
unqualified: the retained VIGO datasheet lists AC and DC amplifier variants, and
operation with a CW laser alone does not identify the installed coupling. An
AC-coupled detector chain cannot provide steady CW intensity this way. Both
mode and recording method are included in control compatibility, so older
carrier-demodulated controls and Pulsed/CW controls cannot be mixed silently.
The manual detector oscillator is restored and checked on completion or abort;
frequencies controlled by a restored external PLL remain observations.
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
readable, including their optional metadata annotations and saved fit results.
Stored resolution, linewidth, segment and fit settings are preserved as
metadata; they do not select a new acquisition's range, speed or peak model.

Selection exports use the host's standalone version-1 `SampleSpectralSelection`
format. Its `accepted` disposition records the operator's export action;
it does not certify physical sample state, instrument readiness or temperature.
The record identifies raw/relative/calibrated quantities, uncertainty limitations,
quality flags and the retained source. Missing actual sample identities are marked
as unavailable; run-local identifiers do not invent material identity. An export
does not promote an instrument bundle.

Hardware-free verification is available with:

```powershell
python -m pytest software/tests/measurement_modules/steady_state_slow_scan -q
```

Verification exercises the installed adapters through injected transports in both
detector and laser modes, including mode-specific current limits, the inclusive
30% pulse-duty boundary, one descending scan by default, Blank/Sample reuse, delayed PLL lock, cancellation,
device failures and restoration. No physical measurements were taken during
development.
