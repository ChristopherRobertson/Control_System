# HRP–CO and MbCO benchmark experiment table

Status: **non-canonical cross-campaign evidence summary; not an executable recipe**

This document summarizes the six HRP–CO and MbCO benchmark measurements selected
to demonstrate that the MIRcat/HF2LI platform can resolve spectral states and
time-dependent changes following photolysis. The intended thesis use is platform
validation before exploratory measurements of shorter-lived intermediates in a
hydrogenase catalytic cycle.

The governing experimental requirements remain in
[`EXPERIMENTS.md`](../../../EXPERIMENTS.md). Campaign order, dependencies, status,
and promotion authority remain in the
[`master_sequence.md`](../../../campaigns/master_sequence.md) and
[`phase_registry.yaml`](../../../campaigns/phase_registry.yaml). This table does
not authorize hardware operation, assign final device settings, change a phase
status, or promote calibration or characterization evidence.

## Interpretation rules

- Every protein/temperature condition begins with an accepted **slow steady-state
  scan** that determines the actual sample-specific band centers, widths, areas,
  and off-band regions.
- Literature band positions and lifetimes are planning anchors, not programmed
  values or fit constraints.
- Geminate and non-geminate recombination can repopulate the same bound-CO bands.
  They are differentiated primarily by temporal behavior, temperature and
  concentration dependence, not by a unique “geminate band.”
- At 70–77 K, bulk-solvent escape and return are strongly suppressed. Slow
  cryogenic recovery is initially classified as geminate/intrapocket recovery,
  not non-geminate recovery.
- The liquid-nitrogen experiment is nominally near 77 K. Published 70 K results
  are literature anchors; the illuminated sample temperature and uncertainty
  must be measured.
- The HF2LI is the primary spectral recorder. The PicoScope supplies timing,
  pulse-shape, detector-response, branch-skew, saturation, and IRF evidence
  within its characterized configurations.

## Full six-condition experiment table

| Temperature and protein | Recombination class | Literature timeframe and measurement coverage | MIRcat-visible bands | Assigned experiments | How the experiments establish platform efficacy |
|---|---|---|---|---|---|
| **Room-temperature HRP–CO** | **Geminate/intrapocket** | Heme bond formation was reported in **<100 ns**. The measurement must include negative delay, the complete IRF support, the earliest accessible ns region, and bridge points through approximately the first microsecond or longer when required by the measured response. | Local ranges around the fitted HRP–CO populations expected near **1905 and 1934 cm⁻¹**, plus an off-band control. Both peak locations are sample-, pH-, isoenzyme-, and temperature-dependent. | **Initial slow scan**; **nanosecond stroboscopic reconstruction**; **fixed-wavenumber kinetic traces** at the two fitted centers and an off-band point/window. | The slow scan demonstrates static resolution of the two HRP–CO populations. Fixed-wavenumber traces establish the prompt bleach, SNR, artifacts, and reset burden. Nanosecond stroboscopy tests whether a local spectrum can be reconstructed across the prompt recovery. A lifetime is claimed only if it is identifiable after IRF convolution; otherwise the valid benchmark is a reproducible prompt component or bound on an unresolved component. |
| **Room-temperature HRP–CO** | **Non-geminate/solvent recovery** | Published solvent recombination is of order **1 s⁻¹** at 300 K and 1 atm CO, corresponding to a characteristic time near 1 s. Acquisition continues for several characteristic times and until the actual pre-pump recovery criterion passes. | Recovery of the same fitted HRP–CO bands expected near **1905 and 1934 cm⁻¹**, with off-band baseline on both sides where the calibrated range permits. | **Initial slow scan**; **repeated rapid-scan phase-delay reconstruction**; **fixed-wavenumber continuous recovery traces** at both bands. | One rare pump event is followed by many consecutive rapid scans, producing a spectral movie rather than discarding all but one scan. A small set of pump-to-scan phases interleaves the wavelength/time trajectories. Fixed-wavenumber traces provide an independent high-SNR recovery and cadence check. Agreement in spectral location, bleach sign, seconds-scale recovery, and repeatability validates the slow time-resolved scanning architecture without requiring a new microscopic HRP mechanism. |
| **Room-temperature MbCO** | **Geminate/intrapocket** | Historical result: approximately **4% geminate amplitude** with an approximately **180 ns** relaxation time. The experiment covers negative delay, the complete IRF, the early ns response through roughly five planning lifetimes, and bridge points into the µs region. The 4% and 180 ns values are not fixed during fitting. | **A₃: approximately 1932–1937 cm⁻¹; A₁: approximately 1943–1945 cm⁻¹; A₀: approximately 1965–1967 cm⁻¹**, using the fitted centers and local windows from the actual sample. A₁ is normally the strongest primary band. | **Initial slow scan**; **A₁ fixed-wavenumber discovery trace**; **nanosecond stroboscopic reconstruction** around A₁; optional A₃ and A₀ stroboscopic windows after they pass quantification criteria. | The slow scan resolves the bound A-state spectrum. The A₁ trace establishes the initial bleach and whether the early response exceeds the detection limit. Nanosecond stroboscopy measures the small early reduction in bleach magnitude across a local spectrum. Reproducing an instrument-resolved early component in the expected temporal regime validates ns equivalent-time capability. Exact reproduction of 4% or 180 ns is an optional mechanistic result, not the minimum system-efficacy claim. |
| **Room-temperature MbCO** | **Non-geminate/recovery candidate** | Published A₁ recovery contains phenomenological components near **185 µs and 1.0 ms**. Coverage begins before the earliest resolvable response, spans the µs–ms interval, and continues through verified recovery, commonly requiring coverage to at least several milliseconds. Mechanism is not assigned from a biexponential alone. | Primarily **A₁ near 1943–1945 cm⁻¹**; A₃ and A₀ are included when their fitted areas and pump-induced amplitudes are quantifiable. All centers and windows come from the initial slow scan. | **Initial slow scan**; **fixed-wavenumber A₁ recovery trace**; **microsecond stroboscopic reconstruction**; **single-scan phase-delay reconstruction** as broader spectral support. | The fixed-wavenumber trace supplies the highest-SNR recovery and repetition-rate evidence. Microsecond stroboscopy is the primary quantitative local kinetic measurement. Single-scan phase-delay reconstruction interleaves one deliberately phased spectral scan per recovered pump event to determine whether A₀, A₁, and A₃ evolve differently. Literature-consistent band recovery in the expected µs–ms regime validates the intermediate-timescale platform even if individual exponentials cannot be assigned uniquely to solvent pathways. |
| **70–77 K HRP–CO** | **Geminate/intrapocket only unless escape is independently demonstrated** | Low-temperature HRP–CO has an exponential internal \(I^*\) process and two distributed, non-exponential \(I\) processes. There is no single universal lifetime. The design spans the accessible ns/µs response and continues through seconds or kiloseconds where the sample remains informative. | Cryogenic, sample-fitted versions of the two HRP–CO populations expected near **1905 and 1934 cm⁻¹**, with matrix/cryostat off-band controls. Cooling can shift centers, widths, and populations; room-temperature centers are not reused. | **Cryogenic initial slow scan**; **nanosecond stroboscopic reconstruction** for a fast branch; **single-pump rapid-scan reconstruction** for the early slow branch; **logarithmic scan-burst reconstruction** for long recovery; **single-scan phase-delay reconstruction only after equivalent-state reset is demonstrated**. | The cryogenic slow scan establishes the new spectral state after cooling. Nanosecond stroboscopy tests fast internal recovery only when each delay begins from an equivalent state. A single pump followed by rapid early scans and later scan bursts captures distributed slow recovery without assuming repeated reset. Resolving different cryogenic spectral populations and their distinct recovery envelopes validates multi-timescale state tracking; reproducing the exact number or rates of historical HRP processes is not required. |
| **70–77 K MbCO** | **Geminate/intrapocket only unless escape is independently demonstrated** | Recovery is non-exponential and A-state specific. Literature gives the ordering **A₀ fastest, A₁ intermediate, A₃ slowest**. At 70 K, a band near 1945 cm⁻¹ recovered during an approximately **20 min** observation while a band near 1926 cm⁻¹ showed no detectable recovery. Coverage therefore extends from the accessible fast regime through at least tens of minutes when needed. | Cryogenic centers expected approximately at **A₃: 1926–1929 cm⁻¹; A₁: 1945–1947 cm⁻¹; A₀: about 1967 cm⁻¹**, using fitted centers from the 70–77 K slow scan. | **Cryogenic initial slow scan**; **nanosecond/microsecond stroboscopic reconstruction** for resolvable fast A-state recovery; **single-pump rapid-scan reconstruction**; **logarithmic scan-burst reconstruction** through minutes or longer; **slow-timescale phase-delay reconstruction only after equivalent-state reset is demonstrated**. | The slow scan resolves the cryogenic A-state populations. Fast stroboscopy tests whether early A₀/A₁/A₃ behavior can be separated. One-pump scan bursts follow slow, non-exponential recovery without cumulative repumping. Demonstrating the expected spectral ordering and strongly different A-state recovery behavior validates the system’s ability to follow multiple transient states over a very wide time range, even when the slowest population remains unrecovered. |

## How each experiment works

### 1. Initial slow steady-state scan

The MIRcat traverses a spectral interval slowly enough that detector, HF2LI,
wavelength, and optical settling errors remain inside the accepted spectral
uncertainty. The final scan speed, direction, wavelength increment, probe pulse
settings, HF2LI filter, dwell, and averaging are measured or optimized; they are
not assigned by this summary.

The slow scan is performed separately for:

1. room-temperature HRP–CO;
2. room-temperature MbCO;
3. 70–77 K HRP–CO;
4. 70–77 K MbCO.

It determines:

- exact peak centers and calibrated uncertainty;
- peak widths, shoulders, overlap, and integrated areas;
- local baselines and usable off-band controls;
- cryogenic peak shifts and population changes;
- the local windows required for later stroboscopic measurements;
- the spectral reference used to detect post-exposure damage or incomplete
  recovery.

The slow scan proves that the platform can resolve the established bound-CO
states before it attempts to resolve their dynamics.

### 2. Fixed-wavenumber kinetic or recombination trace

The MIRcat remains at one fitted band center while the HF2LI records the sample
and reference response before, during, and after an observed pump event. The
measurement gives a direct kinetic trace with maximum available averaging at
that wavenumber.

It is used to determine:

- the sign and magnitude of the prompt bound-band bleach;
- whether recovery is detectable above noise and artifacts;
- the approximate recovery envelope and required record length;
- the repetition interval needed to restore the initial state;
- the number of averages justified before drift dominates;
- which bands merit a full local spectral reconstruction.

A fixed-wavenumber trace does not provide a spectrum. It is a discovery,
optimization, and validation measurement that complements the spectral
reconstructions.

### 3. Nanosecond stroboscopic reconstruction

The MIRcat is held at one wavenumber in a local band window. Equivalent
pump–probe events are repeated with the probe positioned at different delays
relative to the optically observed pump. After completing the delay schedule at
that wavenumber, the MIRcat advances to the next accepted wavenumber and repeats
the schedule.

Combining the measurements produces:

\[
\Delta A(\tilde\nu,t),
\]

without requiring the MIRcat to tune during the nanosecond reaction. Wavelength
tuning occurs between completed delay blocks and therefore does not set the
temporal resolution.

Temporal resolution is instead determined by the measured convolution of:

- pump pulse envelope;
- probe pulse envelope;
- relative jitter;
- sample-plane optical path timing;
- detector response;
- acquisition aperture;
- HF2LI response and supporting fast-path evidence.

Negative delays establish baseline and coherent artifacts. Dense delays around
time zero sample the earliest response. Later bridge delays determine how much
bleach remains after the proposed geminate phase. If the expected lifetime is
not identifiable after IRF convolution, the result is reported as a prompt or
unresolved component rather than an invented lifetime.

### 4. Microsecond stroboscopic reconstruction

This uses the same wavelength-by-wavelength logic as nanosecond stroboscopy but
uses a delay schedule optimized for the µs–ms recovery region. It is especially
appropriate for the reported room-temperature MbCO A₁ recovery.

At every selected wavenumber, the experiment includes:

- pre-pump and negative-delay baseline;
- pump-on and matched pump-blocked events;
- early bridge points after the IRF;
- denser points where recovery curvature is high;
- later points through verified return to the pre-pump state;
- repeated events selected from measured noise and drift.

The result is a local time-resolved spectral map with higher kinetic efficiency
than attempting to reconstruct a full nanosecond spectrum through thousands of
scan phases.

### 5. Repeated rapid-scan phase-delay reconstruction

This is the primary room-temperature HRP–CO solvent-recovery architecture.
The MIRcat scans continuously through the two fitted HRP–CO bands. After a
stable pre-pump scan train, one rare pump event occurs at a controlled phase.
Scanning continues through the entire seconds-scale recovery.

For phase \(j\), scan \(n\), and wavenumber \(\tilde\nu\), the observation time
is represented as

\[
t_{j,n}(\tilde\nu)=\phi_j+nT_{scan}+\tau_{scan}(\tilde\nu),
\]

where \(\phi_j\) is the observed pump-to-scan phase and
\(\tau_{scan}(\tilde\nu)\) is the calibrated time at which the scan reaches that
wavenumber. Every detector sample therefore retains both its actual wavenumber
and pump-relative time.

Many consecutive scans are obtained after one pump event. The experiment is
repeated at a small number of phase offsets only after complete sample recovery.
The different diagonal wavelength/time trajectories interleave to produce a
denser spectral movie. A single scan is never treated as an instantaneous
spectrum unless its duration is demonstrably negligible relative to the local
kinetics.

### 6. Single-scan phase-delay reconstruction

One spectral scan is acquired at a controlled phase relative to each pump event.
After the sample returns to an equivalent initial state, the experiment is
repeated at another phase. The collection of phase-shifted diagonal trajectories
reconstructs the spectral response.

This architecture supports room-temperature MbCO µs–ms measurements because a
full spectral scan may last longer than the fastest recovery component. The
phase offsets allow different wavenumbers to be observed at different parts of
the reaction during repeated equivalent events.

The method requires:

- a calibrated wavelength-versus-time scan trajectory;
- measured scan direction and turnaround behavior;
- an optimized phase increment;
- IRF- and HF2LI-filter-aware reconstruction;
- complete recovery before the next pump event;
- pump-blocked and direction-matched controls;
- publication of native \((\tilde\nu,t)\) coverage so unsupported interpolation
  is not mistaken for data.

At 70–77 K this method is conditional because the sample may not reset between
pump events. It is permitted only after full recovery, fresh-position
equivalence, or a validated thermal reset has been demonstrated.

### 7. Single-pump rapid-scan and logarithmic scan-burst reconstruction

This is the default slow cryogenic architecture. It avoids assuming that a
frozen photoproduct recovers before another pump pulse.

The sequence is:

1. acquire stable pre-pump spectra and temperature history;
2. deliver one independently observed, accepted pump event;
3. acquire the fastest useful continuous scan train during the earliest interval;
4. reduce probe duty by acquiring later scan bursts at increasing elapsed times;
5. continue until each measurable band recovers, plateaus, or reaches the
   planned observation limit;
6. retain any unrecovered fraction as an experimental result.

“Slow” describes the chemical observation window, not necessarily the scan
speed. Individual scans should remain short relative to the local kinetic change
or be analyzed using their full wavelength/time trajectory. Later scans are
spaced logarithmically or placed where pilot data show the most kinetic
curvature or model uncertainty.

## How geminate and non-geminate contributions are distinguished

At a bound-CO band, photolysis produces a negative difference-absorbance bleach.
Both geminate and non-geminate rebinding move that bleach back toward zero.
Consequently, a single spectrum cannot identify the pathway.

The distinction is made from converging evidence:

| Evidence | Geminate/intrapocket expectation | Non-geminate/solvent expectation |
|---|---|---|
| Time dependence at room temperature | Earliest resolvable recovery | Later recovery after ligand escape |
| Bulk CO concentration | Ideally weak dependence on bulk CO because the ligand remains in the protein | Rate or recovery shape can depend on free CO concentration and mass balance |
| Temperature | Persists in a frozen matrix, potentially with distributed slow kinetics | Strongly suppressed when bulk diffusion and protein entry are frozen |
| Spectral bands | Repopulates the same bound HRP–CO or MbCO bands | Repopulates the same bound HRP–CO or MbCO bands |
| Direct dissociated-CO bands | Could support an intrapocket assignment | Free-CO features could support escape and return |
| Present MIRcat limitation | Bound-band bleach/recovery is visible | Reported dissociated/free-CO features above approximately 2119 cm⁻¹ are outside the installed MIRcat range |

If the fast and slow terms have indistinguishable spectral shapes, separation
comes from their time dependence and experimental perturbations. If the data do
not statistically distinguish them, the correct result is an apparent recovery
envelope rather than forced molecular assignments.

## Thesis-efficacy claim and acceptance logic

The HRP–CO and MbCO experiments are benchmark validations of the platform. The
minimum thesis claim is not that these experiments rediscover every molecular
mechanism. It is that the calibrated system can resolve known spectral states,
detect their pump-induced perturbation, and follow recovery over the temporal
regime supported by the measured IRF and sensitivity.

A defensible system-efficacy result requires:

| Validation dimension | Evidence required |
|---|---|
| Spectral accuracy | Expected bands occur within combined spectral-axis, fitting, and sample-condition uncertainty |
| State resolution | More than one established spectral population, local line shape, or condition-dependent state is distinguished where the literature predicts it and SNR permits |
| Photolysis response | A reproducible negative bound-CO bleach occurs at the relevant bands and not in matched artifact controls |
| Temporal response | Recovery occurs in the expected order-of-magnitude regime and is measured using an architecture whose IRF supports that conclusion |
| Dynamic spectral reconstruction | The method produces physically coherent \(\Delta A(\tilde\nu,t)\) from supported native coverage |
| Reproducibility | The response recurs across independent preparations or days within the reported uncertainty |
| Artifact rejection | Pump-blocked, off-band, blank, timing, detector, thermal, and reconstruction controls cannot explain the accepted signal |
| Traceability | Spectral axis, timing, IRF, normalization, sensitivity, scan/tune behavior, temperature, and reconstruction bias are measured and linked to the result |
| Hydrogenase relevance | The demonstrated spectral range, time response, and detection limit overlap the planned hydrogenase intermediate measurement requirements |

Exact reproduction of every published lifetime, fraction, or component amplitude
is not required because protein source, isoenzyme, pH, matrix, temperature, cell,
excitation, and detection method can change the observed values. Agreement must
instead be evaluated against prospectively defined combined uncertainty and
order-of-magnitude temporal expectations.

A suitable thesis-level conclusion, if the applicable acceptance tests pass, is:

> The calibrated MIRcat/HF2LI platform resolved established bound-CO spectral
> populations and pump-induced recovery dynamics in HRP–CO and MbCO. Observed
> band positions, response signs, state-dependent behavior, and characteristic
> temporal regimes were consistent with the benchmark literature within the
> stated experimental and condition-dependent uncertainty. These results
> validate the platform for exploratory time-resolved studies of transient
> vibrational states in hydrogenase, without asserting that every hydrogenase
> intermediate will necessarily be detectable.

## Sources

1. W. Doster et al., “Recombination of Carbon Monoxide to Ferrous Horseradish
   Peroxidase Types A and C,” *Journal of Molecular Biology* 194, 299–312
   (1987). [DOI](https://doi.org/10.1016/0022-2836(87)90377-9) ·
   [PubMed](https://pubmed.ncbi.nlm.nih.gov/3612808/).
2. I. E. Holzbaur, A. M. English, and A. A. Ismail, “Infrared Spectra of
   Carbonyl Horseradish Peroxidase and Its Substrate Complexes,” *Journal of the
   American Chemical Society* 118, 3354–3359 (1996).
   [DOI](https://doi.org/10.1021/ja953715o).
3. E. R. Henry et al., “Geminate Recombination of Carbon Monoxide to
   Myoglobin,” *Journal of Molecular Biology* 166, 443–451 (1983).
   [DOI](https://doi.org/10.1016/S0022-2836(83)80094-1) ·
   [PubMed](https://pubmed.ncbi.nlm.nih.gov/6854651/).
4. M. Schleeger et al., “Time-Resolved Flow-Flash FT-IR Difference
   Spectroscopy: The Kinetics of CO Photodissociation from Myoglobin Revisited,”
   *Analytical and Bioanalytical Chemistry* 394, 1869–1877 (2009).
   [DOI/full text](https://doi.org/10.1007/s00216-009-2871-0).
5. J. B. Johnson et al., “Ligand Binding to Heme Proteins. VI. Interconversion
   of Taxonomic Substates in Carbonmonoxymyoglobin,” *Biophysical Journal* 71,
   1563–1573 (1996).
   [DOI](https://doi.org/10.1016/S0006-3495(96)79359-1) ·
   [Full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC1233623/).
6. M. R. Chance et al., “Myoglobin Recombination at Low Temperature. Two Phases
   Revealed by Fourier Transform Infrared Spectroscopy,” *Journal of Biological
   Chemistry* 262, 6959–6961 (1987).
   [PubMed](https://pubmed.ncbi.nlm.nih.gov/3584103/).
7. B.-J. Schultz et al., “Protein Dynamics Observed by Tunable Mid-IR Quantum
   Cascade Lasers across the Time Range from 10 ns to 1 s,” *Spectrochimica Acta
   Part A* 188, 666–674 (2018).
   [DOI](https://doi.org/10.1016/j.saa.2017.01.010) ·
   [PubMed](https://pubmed.ncbi.nlm.nih.gov/28110813/).
8. G. M. Greetham et al., “A 100 kHz Time-Resolved Multiple-Probe Femtosecond to
   Second Infrared Absorption Spectrometer,” *Applied Spectroscopy* 70, 645–653
   (2016). [DOI](https://doi.org/10.1177/0003702816631302).

Relevant repository authorities:

- [`EXPERIMENTS.md`](../../../EXPERIMENTS.md)
- [`time_resolved_acquisition_modes.md`](../../../campaigns/methods/time_resolved_acquisition_modes.md)
- [`HRP requirements`](../../../campaigns/hrp_001/requirements.md)
- [`MbCO requirements`](../../../campaigns/mbco_cryo_001/requirements.md)
- [`MIRcat manual`](../../../references/manuals/MIRcat/Daylight%20Solutions%20MIRcat%20Manual.pdf)
- [`MIRcat process-trigger correspondence`](../../../references/manuals/MIRcat/daylight_db9_process_trigger_correspondence.md)
