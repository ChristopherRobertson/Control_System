# Dual-Detector Phase Scan tab

This tab reuses the Phase Scan controls, continuous execution and reconstruction
views. Sample and matched-buffer reference are recorded simultaneously. It does
not require a separate buffer-blank acquisition. The original **Phase Scan** tab
and its saved single-detector runs remain available.

## App-only operation

1. Open **Dual-Detector Phase Scan**, choose the save location, and load the sample.
   Keep the matched buffer blank in the reference path. Set the same acquisition
   parameters used by Phase Scan. Review the automatically resolved **Sample**,
   **Reference**, timing and combined resolution settings in the existing summary.
   The connected-device check verifies both optical streams and the timing stream;
   cached choices alone do not authorize acquisition. **Advanced HF2LI overrides**
   provides separate supported-value dropdowns for each detector. A manual request
   is either accepted explicitly or reported as incompatible, never silently lowered.
2. Select **2 · Acquire preliminary sample/reference (pump OFF)** and confirm the
   probe acquisition. Inspect **Preliminary spectral review**, then check
   **I reviewed the preliminary sample/reference spectrum**. This separately saved
   unpumped acquisition supplies Q₀. Changing an incompatible setting clears approval;
   review must be confirmed again after compatibility is restored.
3. Select **3 · Start pumped phase scan** and explicitly confirm. Both detector
   channels, measured wavelength markers and electrical pump sync are retained for
   the complete continuous sequence. FIRE precedes Q-switch by exactly 250 µs.
   LabOne data retrieval occurs after the sequence, with no automatic run splitting
   or emission restart between phases.
4. Inspect **ΔAbsorbance** or **Sample/reference ratio** using the existing display
   selector. The linked sliders and numeric fields select the nearest reconstructed
   coordinate: time has three decimal places in ms and wavenumber two in cm⁻¹.
   Missing data remain gaps. Toolbar Home resets the view; toolbar Save saves an
   image; **Mouse selection** exits pan/zoom. **Export quantitative data…** retains
   the displayed quantities and missing-data reasons. **Load phase-scan run…**
   opens a saved dual run. Single-detector datasets and plans are rejected here.
5. **New run** clears the current preliminary baseline, review and displayed data.
   It preserves entered settings and saved files. **Save plan…** and **Load plan…**
   use distinct dual-detector metadata and preferences.

**Abort acquisition** retains available native and partial data and attempts safe
idle and restoration. Wait for the completion or failure message before another
instrument action. A failed restoration is recorded and is not a completed run.

**Sequence duration** covers scanning only. Timing-table programming and instrument
preparation happen first and can take several minutes for large sequences; data
retrieval, restoration and saving follow. Watch the status line for the current
stage and progress. Both detectors share the same sequence, so simultaneous
reference acquisition does not double its duration. A stopped run may retain
partial native data without a complete reconstruction.

## Signal assignments and calculations

The maintained [wiring map](../../instrument/wiring_map.yaml),
[default wiring](../../instrument/default_wiring_state.md), HF2LI presets and
retained readbacks establish these assignments:

| Role | Physical input | API demodulator | Signal |
| --- | --- | --- | --- |
| Sample | Signal 1 (+), ADC 0 | 0 | Magnitude R |
| Reference through matched buffer | Signal 2 (+), ADC 1 | 3 | Magnitude R |
| Timing/markers/electrical pump sync | DIO carrier | 2 | Recorded digital timing |

Q(ν,t) = S(ν,t)/R(ν,t). The separately retained preliminary baseline is Q₀(ν),
and ΔAbsorbance = −log₁₀[Q(ν,t)/Q₀(ν)]. The calculation aligns detector timestamps
using each recorded filter group delay and matches measured wavenumber coverage.
It does not treat equal array positions as equal wavelengths. Recorded filter
delay corrections are engineering estimates, not deconvolution or an optical
arrival calibration. Time labels refer to electrical pump sync.

Absolute absorbance additionally requires an applicable, validated, explicitly
promoted channel/path-balance bundle B(ν): Absorbance = −log₁₀[Q/B]. Q₀ is never
substituted for B. The maintained promoted-bundle registry currently contains no
such bundle, so the available measured quantities are reference-normalized
ΔAbsorbance and sample/reference ratio. The ratio is not labeled absolute
transmission or absolute absorbance. If an applicable promoted correction is
available, the absolute-absorbance display uses it and retains its provenance.
No routine calibration blank step is added.

Nonfinite, nonpositive, absent and unsupported measurements retain missing values
and reasons. No smoothing, extrapolation, gap filling or further normalization is
applied. Saved records retain the two raw detector streams, timestamps, markers,
pump sync, requested/selected/actual configurations, separate baseline, matching
definition and any applied calibration for reproducibility. Compatibility includes
both detector roles/configurations, trajectory, cadence/triggering and calibration.

## Limits and validation

The HF2LI rate menu reflects discovery with optical demodulators 0 and 3 and timing
demodulator 2 enabled. The historical memory budget remains advisory; actual
available memory, supported settings, timing-table capacity and reconstruction
allocation limits are checked. The app does not split runs to bypass a limit.
The response estimate accounts for both filters and both sample intervals; phase
spacing alone is not effective resolution. See the official
[HF2LI specifications](https://docs.zhinst.com/hf2_user_manual/specifications.html)
and [filter documentation](https://docs.zhinst.com/hf2_user_manual/signal_processing_basics.html).

Implementation verification uses simulated instruments and retained records only.
No new laser, pump or optical acquisition was used to validate this tab. Live
three-stream throughput, physical path stability and simultaneous detector timing
remain hardware-validation limitations. Creating or saving a plan changes no
campaign readiness status and promotes no calibration bundle.
