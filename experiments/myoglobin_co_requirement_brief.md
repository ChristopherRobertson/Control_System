# Myoglobin–CO spectroscopy and photolysis/rebinding experiment: requirements brief

**Document status:** requirements-level design; **not an executable recipe and not authorization to energize hardware, handle CO, or prepare samples**
**Prepared:** 2026-08-15
**Planning basis:** dependency- and gate-driven minimum defensible thesis data package; no calendar deadline controls advancement
**Exclusive scope:** equine-heart carbonmonoxymyoglobin (MbCO) steady-state mid-IR spectroscopy and visible-pump/mid-IR-probe photolysis/rebinding on the installed platform

## 1. Executive determination

The experiment is scientifically feasible in principle, but a hardware recipe cannot yet be frozen. The current calibration campaign is incomplete and has no promoted calibration bundle; the characterization framework is defined but has no promoted characterization bundle. The replacement reference detector also lacks a recorded installed identity. Those facts are operational gates, not requests to substitute literature values for instrument quantities. In addition, the experiment-builder capability registry currently represents the MIRcat range as 900–1800 cm⁻¹, which excludes all three bound-MbCO bands even though the installed laser is documented over 1638.8–2077.3 cm⁻¹. That software-readiness defect must be corrected and verified before recipe authoring. [R03–R12]

The minimum thesis claim should therefore be:

> At controlled sample composition and temperature, the platform resolves the equine-heart MbCO A₁ C–O stretch near 1943–1945 cm⁻¹, observes its prompt negative photolysis difference signal, and measures recovery over the instrument-resolved microsecond-to-millisecond interval with traceable sample/reference normalization and stated uncertainty.

A quantitative geminate claim near the literature value of approximately 4% with a 180 ns lifetime is an **optional mechanistic extension**. It is allowed only if the promoted instrument-response function (IRF), detector latency, timing chain, and measured SNR make that component identifiable after convolution. [L02, L05, N01]

The recommended biological starting point is 4.0 mM equine-heart myoglobin in 25 mM phosphate buffer at pH 7.0, reduced with four molar equivalents of sodium dithionite and equilibrated with CO at atmospheric pressure. This exactly reproduces the most directly relevant aqueous time-resolved FTIR preparation (4.0 mM Mb, 16 mM dithionite, 25 mM phosphate, pH 7.0) and is a **development starting point**, not a frozen batch instruction. Final concentration and optical path are selected together from measured A₁ absorbance, water transmission, detector linearity, and sensitivity. [L01, L03]

The recommended pump candidate is 540 nm because an aqueous MbCO time-resolved IR study used a 10 ns, 540 nm OPO pulse absorbed by the heme β band. A 532 nm fallback may be qualified because 532 nm Nd:YAG excitation is established in Mb ligand photolysis and is the notebook's nominal wavelength, but it must demonstrate equivalent sample-plane stability, photolysis linearity, and absence of added damage. The chosen wavelength is not frozen until OPO characterization and sample-plane power/beam characterization are promoted. [L01, L10, N01, R08]

The primary probe is the A₁ band near 1943–1945 cm⁻¹; secondary steady-state probes near 1932–1937 cm⁻¹ (A₃) and 1965–1966 cm⁻¹ (A₀) diagnose conformational composition and pH/sample changes. The reported photodissociated-pocket bands near 2119–2131 cm⁻¹ are outside the documented installed MIRcat range and are excluded from this experiment's claims. [L04–L07, N01, R06]

## 2. Authority, provenance, and numerical-value policy

### 2.1 Authority order

This brief uses the following order:

1. Safety rules, institutional EHS approvals, installed-device manuals, installed identities, and promoted calibration/characterization bundles.
2. Current repository scope, campaign contracts, P0 decisions, current physical inventory, wiring records, and active campaign status.
3. The canonical theoretical notebook for equations, required inputs, candidate model structure, and uncertainty architecture—but not for unfilled placeholders.
4. Primary peer-reviewed MbCO studies for biological starting values and expected regimes.
5. Reviews, theses, and vendor literature only where they add context or expose a practical method not available in a primary source.

Archived Day-based, RSI-specific, generic-sample, and prior MbCO recipes are not authorities. `RSI_Manuscript.docx` is not an authority. A biological measurement may validate the experiment but may not revise an instrument calibration. File hashes and digests may be recorded diagnostically but never gate acquisition, analysis, promotion, acceptance, or closeout. [R01, R02, R03, R04, R05]

### 2.2 Dependency classes used below

| Class | Meaning | Freeze rule |
|---|---|---|
| **LIT** | Biological or physical starting value directly supported by literature | May enter a pilot design, but sample-specific verification still applies. |
| **MAN** | Installed-device constraint from a manufacturer document or direct correspondence | Must be checked against exact installed identity, firmware, wiring, and readback. |
| **CAL** | Calibration-campaign quantity | May enter a biological recipe only from a promoted, valid calibration bundle. |
| **CHAR** | Characterization-campaign quantity | May enter a biological recipe only from a promoted, valid characterization bundle. |
| **PILOT** | Biological feasibility/variance/damage result | May set the sample-specific operating envelope; must not recalibrate the instrument. |
| **DER** | Value calculated from cited or promoted inputs | Equation, units, input provenance, uncertainty, and limitations must accompany it. |
| **DESIGN** | Predeclared decision criterion in this brief | Must be justified here and tested before it becomes an operational setting. |

### 2.3 Current readiness snapshot

| Area | Current evidence | Consequence for this brief |
|---|---|---|
| Calibration | S0, MS-01, MS-02, T2-01, and T1-01 are complete; PT-01 is in progress; no canonical promotion exists. [R03, R07, R11] | Campaign-local timing results may inform risk analysis but cannot freeze biological delays. |
| Characterization | Matrix and sequence exist; no experimental-requirement freeze and no promoted bundle. [R08, R12] | Power, probe envelope, geometry, overlap, settling, IRF, sensitivity, and reproducibility remain dependencies. |
| Reference channel | Replacement reference chain identified as VIGO `SIP-DC-250M` serial `445161066` with `PVM-10.6-1x1` detector serial `21834`. [R06, R08] | Identity gate resolved; no final dual-detector normalization or latency correction until DET results are promoted. |
| MIRcat software readiness | Installed notebook range is 1638.8–2077.3 cm⁻¹; current builder registry says 900–1800 cm⁻¹. [R09] | Correct and verify the registry before authoring or validating a 1933–1966 cm⁻¹ recipe. |
| Energy metrology | Average-power meter is available; no energy meter is available. | Direct claims use average power. Mean pulse energy may only be derived as average power divided by verified repetition rate. No pulse-energy distribution or calibrated peak-power claim. |
| Sample hardware | No controlled-path, gas-tight aqueous IR cell or temperature stage is established in the current physical inventory. | Cell procurement/identity, measured path, seal compatibility, fill volume, and temperature-control evidence are entry gates. |

## 3. Scientific questions, hypotheses, observables, and claims

### 3.1 Questions and hypotheses

**Q1 — Steady-state identity.** Does a prepared equine-heart sample exhibit the expected neutral-pH MbCO C–O band pattern?

- **H1:** the dominant bound-CO band lies near 1943–1945 cm⁻¹ (A₁), with a lower-frequency A₃ contribution near 1932–1937 cm⁻¹ and a weaker A₀ contribution near 1965–1966 cm⁻¹ at neutral pH. A₀ should increase at lower pH, so the three-band pattern is also a sensitive sample-condition check. [L04–L07]

**Q2 — Photolysis response.** Does a visible pump produce a negative difference absorbance at the bound-CO band that scales with absorbed dose in a low-dose regime?

- **H2:** photolysis removes bound CO absorption essentially promptly compared with this platform's nanosecond/microsecond observation window; the A₁ difference signal is negative immediately after time zero. The nanosecond photolysis quantum efficiency is reported close to unity, but the sample-specific photolyzed fraction must be inferred from measured absorbance and response, not assumed. [L01, L09, L10]

**Q3 — Rebinding model.** Which kinetic description is supported after IRF convolution?

- **H3a, minimum model:** a single apparent recovery exponential plus offset adequately describes the resolvable recovery interval.
- **H3b, notebook mechanistic model:** a geminate component and a solvent-rebinding component are required. The notebook's initial geminate values (4%, 180 ns) come from Henry et al. and are priors/start values only. [L02, N01]
- **H3c, concentration-aware model:** if photolysis perturbs free CO enough that it is not constant, a coupled second-order or mass-balance model is required rather than interpreting a biexponential as two independent molecular species. A 4 mM MbCO flow-FTIR study reported phenomenological 185 µs and 1.0 ms components but found early concentration-dependent and later pseudo-first-order behavior. [L01]

**Q4 — Repetition and damage.** Does the sample return to the same pre-pump state between accepted pulses, and is cumulative exposure negligible over the accepted acquisition block?

- **H4:** recovery and integrity depend on pulse separation, refresh, absorbed dose, and illuminated-volume history. They must be demonstrated by repeated-pulse, dose-linearity, forward/reverse order, and post-exposure tests; recovery cannot be inferred from a fitted kinetic time alone. [L01, L09, N01]

### 3.2 Primary observables

1. Normalized transmission
   \[
   T(\tilde\nu,t)=
   \frac{[V_s(\tilde\nu,t)/V_r(\tilde\nu,t)]_{sample}}
        {[V_s(\tilde\nu)/V_r(\tilde\nu)]_{matched\ background}}
   \]
   and absorbance \(A=-\log_{10}T\). Covariance between sample and reference channels is retained. [N01]
2. Pump-induced difference absorbance \(\Delta A(\tilde\nu,t)=A_{pump\ on}-A_{pump\ off}\), with the A₁ bleach expected negative.
3. Peak center, integrated area, width, and A₀:A₁:A₃ component areas from the steady-state spectrum.
4. Normalized recovery/survival trace at A₁ and, if sensitivity allows, A₃ and A₀.
5. Sample/reference raw voltages, channel range/overload flags, normalization covariance, dark noise, drift, and pre-pump standard deviation.
6. Sample-plane average pump power, verified effective pump repetition rate, beam radii/profile, overlap map, temperature, cumulative accepted pump count, and cell position.

### 3.3 Intended and excluded thesis claims

**Allowed minimum claims** require the relevant promoted bundles and acceptance tests:

- MbCO band observation and assignment within stated wavenumber uncertainty.
- Sign and magnitude of A₁ photolysis difference absorbance within an explicitly defined normalization.
- Apparent recovery time/rate over the measured, IRF-resolved interval.
- Reproducibility across independent preparations/days and a stated uncertainty budget.
- Evidence that no accepted damage or incomplete recovery was detectable within the validation limits.

**Conditional claims:** geminate fraction/lifetime, distinct A-state kinetics, concentration-dependent second-order kinetics, or absolute photolyzed fraction require model identifiability, measured CO/sample mass balance, calibrated spectral response, promoted IRF, and sensitivity sufficient to distinguish the alternatives.

**Excluded claims:** direct single-pulse energy distributions, peak pump power, sub-pulse temporal structure, single-shot fluence distribution, docking-site B₁/B₂ kinetics outside the MIRcat range, universal physiological rate constants, causation from an unconstrained biexponential, absolute quantum yield without adequate photon/sample metrology, and any calibration update derived from MbCO.

## 4. Critical-parameter evidence and conflict resolution

| Parameter | Recommended starting value or range | Rationale and source comparison | Confidence | Class | Finalization rule |
|---|---|---|---|---|---|
| Myoglobin | Equine/horse-heart myoglobin; lot and supplier recorded | Direct aqueous TRIR and flash-photolysis preparations use horse-heart Mb. Species is held fixed because rates and structural relaxation can differ from sperm-whale Mb. [L01, L03] | High | LIT | Freeze supplier, catalog, lot, received form, and certificate in phase manifest; do not mix species/lots in a primary comparison. |
| Nominal purity | Reagent material at least comparable to the 90% material used successfully in flow-FTIR; prefer the highest documented purity available | The relevant flow-FTIR work used 90% material but performed clarification/filtration. Vendor percentage is not accepted as heme concentration. [L01] | Medium | LIT/PILOT | Accept only after UV–visible, IR, clarity, and concentration-basis checks; record impurities/lot information. |
| Mb concentration | 4.0 mM development start; reduce only if transmission/linearity requires | 4.0 mM is the closest aqueous TRIR precedent; a different ultrafast study used 10 mM with a 25 µm spacer, showing that higher concentration is possible but not necessary for the minimum claim. [L01, L09] | High for start; medium for optimum | LIT/PILOT | Select concentration jointly with measured path so A₁ is quantifiable, water transmission is adequate, and sample/reference detectors remain linear under DET/PF limits. |
| Concentration basis | Heme/MbCO spectrophotometric basis, not weighed powder alone | Horse-heart MbCO has established UV–visible maxima near 423, 540–542, and 577–579 nm; dilution and path must lie in the UV–visible instrument's verified linear range. [L03, L08] | High | LIT/PILOT | Report nominal mass basis and verified heme basis with absorptivity source, dilution, path, fit residual, and uncertainty. |
| Buffer | 25 mM phosphate, pH 7.0 | Exact aqueous flow-FTIR precedent. A separate work used 100 mM phosphate pH 7; stronger buffer is unnecessary until stability proves otherwise. [L01, L03] | High | LIT | Retain unless a matched-buffer spectral/stability pilot shows failure; any change creates a new condition/configuration. |
| pH | 7.00 target, measured after reduction and CO equilibration | At pH above 6, A₁/A₃ dominate; A₀ increases at low pH. The direct TRIR sample used pH 7.0. [L01, L05, L06] | High | LIT/PILOT | Freeze pH tolerance from calibrated pH-meter uncertainty and the observed A-state sensitivity; record temperature and pre/post pH. |
| Ionic strength | That produced by the declared 25 mM phosphate formulation; no added salt in the starting condition | Reproduces L01 and avoids introducing an unstudied ionic-strength variable. | Medium | DER/PILOT | Calculate from actual acid/base recipe; if salt is needed, validate as a distinct condition. |
| Temperature | 293 K starting setpoint | MbCO pump–probe work used 293 K; the flow-FTIR discussion reports about 1 mM dissolved CO at 293 K. [L01, L09] | Medium-high | LIT/CHAR | Freeze tolerance only after sample-stage control and spatial temperature variation are characterized; record actual temperature, not “room temperature.” |
| Reductant | Fresh sodium dithionite at four molar equivalents to Mb; 16 mM for 4 mM Mb | Both the direct TRIR procedure and an independent horse-heart preparation use approximately four equivalents. [L01, L03] | High | LIT/PILOT | Verify ferrous MbCO and pH; lower only if a titration establishes complete reduction, higher only with documented need and matched controls. |
| Oxygen exclusion | Anaerobic buffer, vessel, transfer, and cell; CO equilibration under controlled atmospheric-pressure CO | The direct method used five vacuum/argon cycles, then replaced argon with CO; other work used 1 atm CO. [L01, L09] | High | LIT/SAFETY | The approved EHS/sample SOP selects glovebox/Schlenk technique; accept only with pre/post state verification and no leak/bubble. |
| Free dissolved CO | Calculate from measured CO partial pressure and temperature; about 0.95–0.99 mM in water at 298.15 K and about 1 mM near 293 K is an expectation, not a measured sample value | NIST/IUPAC compilations and L01 agree in scale. Protein binding, salts, and headspace mass balance must be included. [L01, L11, L12] | High for scale; medium for actual sample | DER/PILOT | Report equation, gas purity, pressure, water-vapor correction, temperature, headspace/liquid volumes, and uncertainty; do not label it measured unless measured. |
| Cell windows | CaF₂, aqueous-compatible, gas-tight demountable cell | MbCO pump–probe precedent used 2 mm CaF₂ windows. [L09] | Medium-high | LIT/PILOT | Freeze exact window grade/thickness, seal, torque method, and compatibility after blank, leak, scatter, and pump-only tests. |
| Optical path | 10 µm primary start; 25 µm alternative | A 10 µm flow cell supported 4 mM aqueous MbCO TRIR; 25 µm CaF₂-spacer cells supported MbCO pump–probe. [L01, L09] | High for bracket | LIT/PILOT | Measure the assembled path independently; select 10 or 25 µm from water transmission, A₁ absorbance, fringe behavior, and detector linearity. No absolute concentration claim with an unverified path. |
| Pump wavelength | 540 nm primary candidate; 532 nm qualified fallback | 540 nm/10 ns OPO excitation is the closest time-resolved IR precedent. Aqueous horse-heart MbCO was readily photodissociated with 8 ns, 532 nm YAG pulses in an independent ligand-rebinding study. [L01, L10] | High for 540; medium for fallback | LIT/CHAR | PB-02 and OG-01 must show stable sample-plane output/geometry; a dose-response equivalence test selects the wavelength without added damage. |
| Pump duration | Literature expectation 5–10 ns; use measured promoted value | L01 used 10 ns; the Surelite manual identifies approximately 5–8 ns as a well-aligned oscillator pulse. [L01, M01] | High as expectation | MAN/CHAR | Freeze the measured optical duration from PB/IR evidence, not the manual nominal. |
| Pump repetition | 0.5 Hz effective pump-output starting candidate while preserving the flashlamp's optimized repetition; qualify higher rates only by recovery/damage testing | QCL MbCO work used 0.5 Hz and 20 repeats; flow-FTIR used 10 Hz with more than four illuminated-volume exchanges between pulses. Surelite pulse division permits lower optical output without changing lamp discharge rate. [L01, L04, M01] | Medium-high | LIT/MAN/PILOT | Preserve the installed optimized lamp rate; verify effective optical rate. Promote a higher pump rate only if pre-pump recovery, post-integrity, and cumulative-dose criteria pass. |
| Probe window | 1900–1980 cm⁻¹ core; 1850–2050 cm⁻¹ survey if throughput permits | Covers A₃, A₁, and A₀. QCL work reconstructed 1880–1960 cm⁻¹ in 2 cm⁻¹ steps; flow-FTIR filtered 1850–2300 cm⁻¹. [L01, L04–L07] | High | LIT/CAL/CHAR | SP-02 and QB-01 must validate wavenumber/readback/output over every used point; omit non-performing regions rather than extrapolate. |
| Steady spectral increment | 1 cm⁻¹ core; 2 cm⁻¹ survey | QCL protein study reported 1 cm⁻¹ spectral resolution and MbCO kinetics every 2 cm⁻¹. [L04] | High for start | LIT/CAL/CHAR | Refine only if measured linewidth and effective resolution show added information; final increment must not be finer than justified by SP-02/QB evidence. |
| Primary probe | A₁ peak/area near 1943–1945 cm⁻¹ | Most intense neutral-pH band; direct TRIR observable. [L01, L04, L07] | High | LIT/CAL | Center and integration bounds come from the sample's accepted steady-state fit and promoted axis uncertainty. |
| Secondary probes | A₃ near 1932–1937 cm⁻¹; A₀ near 1965–1966 cm⁻¹ | Diagnose substates, pH, and spectral heterogeneity. [L04–L07] | High for assignment; medium for detectable amplitude | LIT/CAL/PILOT | Include only if PF-01 sensitivity and sample spectrum support stable fits. |
| Geminate prior | Fraction about 0.04 and lifetime about 180 ns | Henry et al. reported ~4% geminate rebinding with a 180 ns relaxation time. These are priors, not constraints. [L02] | High as historical start; low as sample-specific truth | LIT/PILOT | Fit freely with uncertainty; claim only if IRF-convolved simulations and profile likelihood show identifiability. |
| Slow-regime expectation | Approximately 10² µs to 1 ms, with observation extended through complete recovery | Flow-FTIR yielded phenomenological 185 µs and 1.0 ms components; structural work reports 90 µs and 1.2 ms recovery components. [L01, L13] | Medium-high | LIT/PILOT | Discovery scan spans the full measured return; final boundary is based on pre-pump equivalence and model residuals. |
| Photolyzed fraction | Operate in the measured low-dose linear regime; do not exceed the 25% literature precedent during development | A visible/mid-IR pump–probe study broke 25% of Fe–CO bonds per shot while translating/rotating the sample. [L09] | Medium | LIT/PILOT/DER | Derive from absorbed photons/model and cross-check against bleach amplitude; select the lowest dose meeting PF-01 SNR and passing linearity/damage tests. |
| Lock-in dwell | No fixed value; at least the tuning/settling time plus the promoted 99% settling time and accepted averaging interval | For HF2 filters, 99% settling ranges from 4.6τ (first order) to 16.0τ (eighth order); fourth order is 10.0τ. [M04] | High | MAN/CHAR | AR-01/PF-01 choose order and τ; compute dwell from the manual table and verify with bidirectional/step tests. |
| Replication | Validation precision study normally uses 6–15 independent full-procedure replicates per material; staged thesis design may begin smaller only as a variance pilot | Eurachem states that reliable precision requires independent repetition of the entire procedure and typically 6–15 replicates per material. [Q01] | High | DESIGN/PILOT | Use pilot variance and thesis precision target to set final n before confirmatory acquisition; do not count technical averages as independent preparations. |

## 5. Sample and cell requirements

### 5.1 Material identity, storage, and handling

The sample manifest must record supplier, catalog, lot, stated species/tissue, chemical form on receipt (normally metmyoglobin/ferric unless independently shown otherwise), nominal purity, molecular mass basis, certificate/SDS revision, received date, storage history, and freeze–thaw history. Lyophilized-protein storage follows the lot-specific supplier instruction; no generic numeric storage temperature is imposed here because the purchased product has not been selected. Prepared MbCO is made for same-day use, protected from unintended illumination, and is not frozen for reuse; this follows immediate-preparation practice in horse-heart MbCO flash-photolysis work. [L03]

Protein concentration is not accepted from powder mass alone. Report both the gravimetric nominal concentration and a verified heme/MbCO concentration obtained from an accepted UV–visible spectrum using a cited horse-heart absorptivity, verified dilution and cuvette path, full spectrum rather than a single peak, and the spectrophotometer's linear range. Bowen reports horse-heart MbCO maxima near 423, 540, and 577 nm and provides extinction coefficients; newer summaries show small literature differences around 540–542 and 577–579 nm. Therefore acceptance uses a fitted/reference spectrum and uncertainty, not exact integer peak matching. [L08]

### 5.2 Preparation sequence requirement

The eventual controlled sample SOP shall implement this ordered chemistry logic; the exact vessel sizes, gas flows, pipetting volumes, and hardware actions remain outside this non-executable brief:

1. Prepare and document 25 mM phosphate buffer at pH 7.0 using calibrated volumetric and pH measurements. Deoxygenate the buffer by the approved EHS method.
2. Dissolve equine-heart myoglobin to a 4.0 mM nominal starting concentration. Clarify insoluble material. L01 used 1 h bath sonication, 21,900×g centrifugation, and 0.2 µm filtration; those values are a direct precedent, but sonication/centrifugation/filtration are retained only if a recovery and spectral-integrity pilot shows no concentration bias or damage. [L01]
3. Establish anaerobic conditions before reduction. Add freshly prepared dithionite to four equivalents (16 mM for 4 mM Mb), mix without introducing oxygen, and remeasure pH. [L01, L03]
4. Replace the inert atmosphere with certified CO at approximately atmospheric pressure and equilibrate. L01 stirred for 30 min after gas replacement; L03 used 20 min under CO before reductant and another 30 min after. This brief selects **reduction under anaerobic inert gas followed by 30 min CO equilibration** as the closest TRIR starting sequence. The time is accepted only after UV–visible stability has plateaued and the EHS gas procedure is approved. [L01, L03]
5. Determine the dissolved-free-CO estimate from temperature, partial pressure, and a headspace/liquid mass balance using the NIST/IUPAC Henry coefficient; do not simply enter “1 mM.” [L11, L12]
6. Obtain the pre-run UV–visible acceptance spectrum and, on a matched aliquot/cell where available, the steady IR spectrum. Transfer to the gas-tight IR cell without bubbles or air exposure.

Alternative order (CO exposure before dithionite) is documented in L03 but is not the primary route because L01 is the closer aqueous time-resolved IR precedent. If the primary route fails state-purity or stability acceptance, the alternative must be tested as a separate preparation condition rather than silently substituted.

### 5.3 Pre- and post-measurement state verification

An aliquot diluted into anaerobic, dithionite-containing matched buffer must show the horse-heart MbCO UV–visible pattern near 423, 540–542, and 577–579 nm, with no material metMb/deoxyMb residual beyond the validated spectral-deconvolution limit. The dilution factor is chosen so the complete spectrum lies within the UV–visible instrument's verified linear range. A single wavelength or color inspection is insufficient. [L01, L08]

The IR cell must show:

- a reproducible A₁ band near 1943–1945 cm⁻¹ after matched-buffer/reference normalization;
- physically plausible A₃/A₀ contributions rather than clipping, fringes, or a baseline feature fitted as protein;
- no detector overload, no unexplained atmospheric CO₂ structure, and no irreproducible forward/reverse hysteresis;
- path and concentration consistent with Beer–Lambert behavior within the uncertainty of a dilution/path pilot.

After every accepted exposure block, repeat the steady IR check at minimum and repeat the UV–visible spectrum on a representative aliquot. Pre/post spectra must be statistically equivalent within limits set by the dark/repeatability and method-validation pilots. Any new peak, persistent loss of MbCO area, baseline/fringe shift larger than method precision, visible precipitate, bubble, leak, or failure to recover rejects the affected block and invokes the documented exclusion—not silent correction.

### 5.4 Cell, fill, and thermal requirements

The minimum cell is a gas-tight demountable aqueous transmission cell with CaF₂ windows and a measured 10 µm path. A 25 µm spacer is the first alternative if transmission and detector linearity pass and additional signal is required. The exact cell body, spacer material, window grade, seal/elastomer, wet-material compatibility with phosphate/dithionite/CO, and pressure rating must be documented from manufacturer sources before procurement/use. [L01, L09]

The cell shall be filled bubble-free with no intentional gas headspace in the optical aperture. CO equilibration occurs before filling; any unavoidable reservoir headspace is recorded and included in the CO mass balance. The cell must never be pressurized as an improvised pressure vessel. A water/buffer leak test, window-background test, seal-compatibility review, and 293 K hold test precede protein use.

Fill volume and illuminated volume are **geometry-derived**, not guessed:

\[
V_{fill}=V_{aperture}+V_{ports}+V_{dead},\qquad
V_{illum}=\int_{cell} I_{pump}(x,y)I_{probe}(x,y)\,dV / I_{norm}.
\]

The cell drawing and measured spacer define \(V_{fill}\); OG-01/OV-01 beam maps define the overlap-weighted illuminated volume and overlap fraction. Prepare enough sample for the cell, verified transfer dead volume, required pre/post aliquots, and one complete repeat fill; the final numeric volume is withheld until the cell is selected.

The sample setpoint is 293 K. A measured cell-adjacent sensor and a characterized stage must establish stability and gradients; an ambient room reading is insufficient. The allowed tolerance is finalized from controller performance and the measured sensitivity of band position/kinetics to temperature. Pump-heating estimates are checked against time-resolved baseline and temperature evidence.

### 5.5 Refresh and replacement

Continuous flow is scientifically strongest when available: L01 exchanged the measurement volume more than four times between 10 Hz pump pulses. A static-cell minimum is acceptable for the minimum thesis scope only if one of these conditions is met:

- an approved translation/rotation stage presents unexposed sample as in L09; or
- effective pumping begins at 0.5 Hz as in L04, cumulative-dose blocks are short enough to pass pre/post integrity and repeated-pulse tests, and the cell/aliquot is replaced before the validated exposure limit.

The allowed shots per location, per fill, and per preparation are PILOT outputs. They are defined by the earliest detectable failure among dose linearity, complete pre-pump recovery, steady IR area/shape, UV–visible state purity, clarity, temperature, and baseline. A literature pulse count is not an exposure limit for this platform.

## 6. Control matrix and acceptance purpose

Every control is acquired with the same optical configuration, path, detector ranges, normalization definition, and analysis version as the sample unless the manifest explicitly states why not.

| Control | Minimum implementation | Purpose and acceptance logic |
|---|---|---|
| Dark/electronic | Both beams blocked or sources disabled in an approved state; both detector channels recorded | Establish offset, RMS noise, correlations, saturation/rail behavior, and drift. DET-01/PF-01 limits must pass. |
| Empty-cell/window | Assembled clean cell without liquid | Identify window fringes, etaloning, scatter, and pump-induced window response. Not substituted for buffer background. |
| Matched buffer/cell blank | Same cell/path, phosphate, dithionite, gas history, seals, and temperature but no Mb | Denominator for sample transmission and a pump-artifact control. A pump-correlated feature near the MbCO window rejects the optical configuration until explained. |
| No-pump | Accepted MbCO sample, probe on, pump physically blocked/shuttered | Measures probe-only baseline, QCL-induced drift/heating, and spontaneous state change. |
| Pump-only | Matched blank, pump enabled at the intended dose, probe/detector acquisition active | Detects scatter, window/solvent response, electronics pickup, and thermal artifacts. Polack et al. similarly tested buffer and deoxy-Mb controls. [L09] |
| Probe-only | Sample with probe sequence, no pump pulses | Detects probe photothermal or cumulative effects and scan-order drift. |
| Deoxy-Mb/alternate state | Anaerobic ferrous deoxy-Mb prepared and verified without CO, where EHS/sample stability permits | Confirms that the bound-CO A-band bleach requires MbCO and helps identify pump artifacts. It is a separate sample condition, never a spectral baseline fabricated from the MbCO data. [L09] |
| Time-zero surrogate | Nonbiological sample/device producing a prompt pump–probe response at the sample plane, chosen in OP-01/IR-01 | Establishes optical time zero and IRF without using MbCO as a timing calibrant. |
| Power/dose series | Same preparation/configuration at randomized accepted average-power levels, always including return to a low level | Establishes low-dose linearity, saturation, and irreversible drift. The first nonlinearity/damage defines a ceiling, not a data point to normalize away. |
| Repetition/recovery | Same dose per accepted pulse, varied pump pulse separation while flashlamp remains in its approved thermal state | Demonstrates complete pre-pump recovery and no accumulation; drives final effective pump rate. [N01, M01] |
| Preparation repeat | Independently weighed, reduced, ligated, verified batch | Captures chemistry variability. A re-fill from the same vial is not an independent preparation. |
| Cell/reload repeat | Independent clean/reassemble/fill or independent disposable cell | Captures path/sealing/loading variability. |
| Post-exposure integrity | Steady IR and UV–visible verification, plus visual cell inspection, immediately after an exposure block | Detects persistent photolysis, oxidation, precipitation, bubbles, leaks, heating, or window damage. |
| Scan-direction/order | Forward and reverse wavenumber scans; randomized pump doses/delays; repeated anchor point interleaved | Detects wavelength settling, drift, memory, and time-order bias. |

## 7. Steady-state mid-IR spectroscopy requirements

### 7.1 Objectives and regions

The survey scan spans 1850–2050 cm⁻¹ at a 2 cm⁻¹ starting increment if QB-01/SP-02 demonstrate usable output and axis validity. The core scan spans 1900–1980 cm⁻¹ at a 1 cm⁻¹ starting increment. These ranges include A₃, A₁, and A₀ while providing off-band baseline on both sides; the increments follow the QCL MbCO precedent. [L04]

The expected neutral-pH components are approximately:

- A₃: 1932–1937 cm⁻¹;
- A₁: 1943–1945 cm⁻¹ (primary);
- A₀: 1965–1966 cm⁻¹.

Exact peak positions are fitted results with SP-02 uncertainty, not acceptance by exact equality. [L04–L07]

### 7.2 Background, order, dwell, and averaging

1. Acquire dark/electronic records, then empty-cell/window and matched-buffer spectra before protein.
2. Acquire matched-buffer and sample in both scan directions. Randomize direction across preparations, and interleave an A₁ anchor measurement often enough that drift can be interpolated; the interval is finalized by RPT-CH drift evidence.
3. Each wavelength point must retain raw sample and reference voltages, detector ranges, overload flags, QCL set/readback, measured timing, temperature, and average-power/readback context.
4. Wavelength settling and dwell are not hard-coded. For HF2 filter order \(n\) and time constant \(\tau\), use the manufacturer 99% settling multiplier (4.6, 6.6, 8.4, 10.0, 11.6, 13.1, 14.6, or 16.0 times \(\tau\) for orders 1–8) after the last wavelength/power/configuration change, then collect the accepted averaging window. [M04]
5. AR-01 must measure MIRcat tuning/settling and any direction dependence. The frozen dwell is
   \[
   t_{dwell}\ge t_{tune,99}+m_{99}(n)\tau+t_{average}+t_{margin},
   \]
   with every term taken from promoted characterization or a declared design allowance. A nominal 1 ms/4th-order repository example is not authority.
6. Average only stationary, overload-free data after settling. Retain individual repeats so that technical variance is estimable. Do not average forward/reverse scans before testing their difference.

### 7.3 Normalization and baseline

Use promoted DET-04 optical/detector/system normalization. Never assume a 50/50 splitter. Correct sample/reference relative response and latency using the promoted splitter/detector bundle; propagate the correction uncertainty. Compute the matched-background double ratio and \(-\log_{10}\) only after dark handling and range checks. Preserve sample/reference covariance. [R04, R08, N01]

Baseline treatment is limited to a predeclared low-order model fitted only to off-band regions supported by the survey scan. No polynomial order, anchor interval, smoothing kernel, or fringe removal is selected by making the expected peaks look correct. Alternative baseline/fringe models are sensitivity analyses, and the native normalized spectrum is retained.

### 7.4 Steady-state fitting and acceptance

Fit the core spectrum with the fewest justified components: A₁ plus A₃ and/or A₀ only when residuals and uncertainty support them. Gaussian components are a starting phenomenology because prior MbCO work used Gaussian decomposition; integrated area, center, FWHM, covariance, and residuals must be reported. [L04, L09]

A steady-state sample is accepted only if all are true:

- UV–visible state verification passes;
- A₁ is detected with the PF-01-defined quantification criterion and the fitted center is consistent with 1943–1945 cm⁻¹ after axis uncertainty;
- detector response is within DET-02 linearity and no overload/invalid sample exists;
- matched-buffer transmission is adequate over the selected path;
- forward/reverse difference and repeated A₁ anchors lie within the RPT-CH drift/repeatability envelope;
- fit residuals show no structured feature that invalidates the selected baseline/component model;
- cell inspection shows no leak, bubble, precipitation, or window change.

Absence of a resolvable A₀ or A₃ component is reportable; it is not a reason to force a peak.

## 8. Time-resolved pump–probe design

### 8.1 Pump and probe geometry

The pump candidate is OPO output at 540 nm, verified at the sample plane. The OPO is pumped by the Surelite 355 nm third harmonic, but residual 355 nm and other OPO outputs must be blocked from the sample and detectors. The OPO manual requires wavelength calibration with a spectral device of 0.1 nm resolution; its `GoTo` value is not independent wavelength evidence. [M02]

PB-02 qualifies 540 nm output. If it fails output/stability/beam-quality criteria, 532 nm may be compared as a separate qualified condition. Pump wavelength, bandwidth, polarization, pulse duration, average power, effective repetition, beam radii/profile, pointing, and sample-plane transfer are recorded. The pump spot must cover the accepted probe-sensitive area with a measured, stable overlap; OV-01 supplies the overlap map and uncertainty. No overlap fraction of one is assumed.

The primary probe is the sample-specific A₁ fitted center or a small symmetric set of points sufficient to estimate peak area without converting drift into kinetics. A₃/A₀ kinetic probes are optional. An off-band point on each side is interleaved to monitor baseline/pump artifacts. Probe setpoints must lie within SP-02/QB-01 validity.

### 8.2 Dose quantities and the no-energy-meter limitation

Directly report measured sample-plane average power \(P_{avg}\) and its uncertainty. With verified accepted optical-pulse rate \(f_{pump}\), the only permitted pulse-energy quantity is

\[
\bar E_{pulse}=\frac{P_{avg}}{f_{pump}},\qquad
\left(\frac{u_E}{\bar E}\right)^2=
\left(\frac{u_P}{P_{avg}}\right)^2+
\left(\frac{u_f}{f_{pump}}\right)^2-2\frac{\operatorname{cov}(P,f)}{P f}.
\]

Label this **derived mean energy per accepted pulse**. It is not a direct energy measurement and provides no pulse-to-pulse distribution. Do not infer calibrated peak power from \(\bar E\) and a nominal pulse width.

If OG-01 supplies sample-plane 1/e² radii \(w_x,w_y\) and a measured spatial profile, calculate the stated profile-specific mean fluence. For an elliptical Gaussian, for example, peak fluence would require profile/model assumptions and is reported only as a model-derived quantity with uncertainty—not as a direct measurement. The primary dose record remains \(P_{avg}\), accepted pulse count, and illuminated geometry.

The notebook photon-balance estimate is retained with all inputs explicit:

\[
N_{abs}=\frac{\bar E_{pulse}}{hc/\lambda_{pump}}
          (1-10^{-A_{pump}}),
\]
\[
f_0=\min\left[1,
 \frac{\Phi\,N_{abs}\,f_{overlap}}
 {N_{MbCO,illum}}
\right],
\]

where pump absorbance, quantum yield \(\Phi\), overlap fraction, concentration/path/illuminated volume, and their covariance are either measured or literature priors. The quantum efficiency “close to unity” is a starting prior from L01, not a sample-specific measurement. The measured initial bleach is an independent cross-check. [L01, N01]

For an order-of-magnitude planning check, the L01 bound-CO extinction coefficient of 1,920 M⁻¹ cm⁻¹, the 4.0 mM starting concentration, and a 10 µm path predict a full bound-band absorbance contribution of

\[
A_{CO,pred}=\epsilon_{CO}cl
=(1{,}920)(0.0040)(0.0010)\approx 7.7\times10^{-3}.
\]

At the 25% photolysis level used as a literature ceiling in this brief, a perfectly isolated bound-CO bleach would therefore be about \(-1.9\times10^{-3}\) absorbance units before accounting for A-state population, finite spectral bandwidth, IRF convolution, overlap, and baseline effects. This is a **derived planning value**, not an acceptance target; the measured steady peak area and initial bleach replace it in the prediction-versus-measurement table. [L01, L09]

Operate at the lowest dose that passes PF-01 SNR/quantification. Map dose response through the linear region and stop before the 25% per-shot literature precedent unless a prior approved pilot explicitly justifies going higher; the preferred operating point is below the first statistically supported nonlinearity or integrity change. [L09]

Cumulative exposure per location is \(N_{accepted}\bar E_{pulse}\) and absorbed cumulative energy uses measured pump absorbance. A screening temperature-rise calculation is

\[
\Delta T_{adiabatic}=\frac{E_{abs}}{\rho C_p V_{therm}},
\]

with buffer properties, thermal volume, and cooling interval stated. It is a conservative model, not a thermometer. Time-resolved off-band signals, sample temperature, and pre/post spectra decide acceptance.

### 8.3 Delay sign, time zero, and IRF

Define corrected delay

\[
t = t_{probe,center\ at\ sample}-t_{pump,center\ at\ sample}.
\]

Thus \(t>0\) means the probe interrogates after pump arrival and \(t<0\) is pre-pump baseline. Commanded electronic delay is never presented as optical delay. OP-01 measures pump command-to-sample arrival, DET-03 measures channel latency, CL-01 establishes the full clock chain, and IR-01 measures the optical/system IRF using a nonbiological prompt response at the sample plane. [R08]

The promoted time-zero result must include reference plane, sign, fixed offsets, uncertainty, drift, configuration/adapter/cable IDs, and validity envelope. The current campaign-local T2/T1 values and MS-02 splitter/cable corrections are informative only; they are not biological settings because PROM-01 is incomplete.

The IRF model shall include, as applicable, measured pump duration, MIRcat optical pulse envelope, relative jitter, detector response, acquisition aperture/window, and HF2 filtering. The notebook represents the probe as a rectangular pulse and detector/lock-in as convolved responses; replace those shapes only when measurements justify a better model. [N01]

### 8.4 Adaptive delay schedule

The schedule is generated from promoted IR-01 and pilot data; a fixed archived list is prohibited. It must cover all four regions:

1. **Pre-pump baseline:** negative delays extending far enough that no IRF contribution is present, with spacing fine enough to test baseline stationarity. Bounds and spacing derive from the promoted IRF support and uncertainty.
2. **Prompt/geminate region:** from time zero through at least five times the literature 180 ns geminate prior (through approximately 0.9 µs as a literature-derived planning value). Point separation near the rise and 180 ns decay must be no coarser than one-half the promoted IRF FWHM, and the candidate grid is optimized by convolved-model simulation. [L02]
3. **Solvent-rebinding region:** logarithmic or information-optimal coverage from approximately 1 µs through at least 10 ms, spanning the reported 185 µs and 1.0–1.2 ms behavior and a demonstrably recovered baseline. The 10 ms planning boundary is a **DESIGN** extension to about 8.3 times the 1.2 ms literature component; the measured recovery test may extend it. [L01, L13]
4. **Recovery/repetition region:** additional pre-next-pulse observations or pulse-separation tests until the pre-pump value is statistically equivalent to the original baseline. For a single exponential, 99% mathematical recovery occurs at \(-\tau\ln(0.01)=4.605\tau\); the notebook uses this relationship, but the actual criterion includes offsets, slower components, and sample damage. [N01]

Delay density is chosen before confirmatory data by simulating both notebook models with the promoted IRF and PF-01 noise/covariance, then maximizing parameter information subject to acquisition time. A grid is acceptable only if simulated profile likelihoods recover each required parameter without a boundary solution and the model-comparison false-selection rate meets the predeclared analysis target. If the 180 ns component is not identifiable, remove the geminate claim and reallocate time to the microsecond–millisecond MVP; do not report an unconstrained lifetime.

Each delay block includes randomized delay order, interleaved negative/late-recovery anchors, accepted-power verification, and an off-band control. Chronological raw acquisition order is retained even when analysis displays sorted delay.

### 8.5 Repeated-pulse qualification

Keep the Surelite flashlamp at its installed optimized rate; its manual warns that changing lamp frequency changes YAG thermal lensing. Use the approved optical pulse-division/gating architecture to begin with 0.5 Hz effective pump output, reflecting L04, while verifying every accepted optical pulse. [L04, M01]

At fixed mean dose per accepted pulse, compare increasingly shorter pulse separations, always returning to the longest separation as a drift control. At each separation test:

- pre-pump A₁ absorbance must equal the original pre-pump distribution within the promoted method precision;
- initial bleach, fitted recovery, off-band response, and post-block steady spectrum must remain invariant within their uncertainty;
- cumulative accepted pulses and cell position are recorded;
- no trend with pulse index, block order, or cumulative absorbed dose may remain in residuals.

The highest passing rate is the biological rate ceiling. The recipe may choose a lower rate to protect sample integrity/acquisition independence. A 10 Hz precedent is relevant only when more than four illuminated volumes were refreshed between pulses; it does not authorize 10 Hz in a static cell. [L01]

## 9. Timing, routing, acquisition, and device requirements

### 9.1 Fixed physical routing identities

The current documented routing is the configuration to be verified, not silently redesigned: [R06, R08]

| Source | Channel | Destination | Intended role |
|---|---|---|---|
| T660-2 | A | HF2LI DIO0 / external reference | Probe/reference clock marker |
| T660-2 | B | MIRcat rear-panel `TRIG IN` | One externally triggered QCL optical pulse per accepted edge in External Trigger mode |
| T660-2 | C | HF2LI DIO1 | DAQ/acquisition trigger marker |
| T660-2 | D | T660-1 `TRIG IN` | Slow pump-sequence trigger |
| T660-1 | A | Surelite `FIRE`, DB9 pin 7 | Flashlamp fire command |
| T660-1 | B | Surelite Q-switch, DB9 pin 6 | External Q-switch command |
| T660-1 | C | MIRcat process trigger, DB9 pin 4 | Active-low sweep/process step |
| T660-1 | D | Disconnected | Must remain disabled/unwired |

MIRcat DB9 pin 5 remains reserved/disconnected and pins 6/8 remain unused/unwired. The Arduino multiplexer remains bypassed/disabled. Any change is a new configuration requiring the applicable calibration/characterization validity review.

### 9.2 Master clock and repetition architecture

The master reference, lock state, and frequency come from promoted CL-01/HF-01/MD-01 evidence. T660-2 supplies the fast probe/reference/DAQ sequence; its D output triggers T660-1 for the slow pump event. The effective pump rate is an integer division/pulse-picking relationship to the verified reference. Every acquisition records commanded and measured rates and missed/extra-trigger diagnostics.

T660 specifications provide 10 ps programmed resolution, nominal 21 ns insertion delay, and <35 ps typical jitter, but these are manufacturer constraints—not the installed end-to-end time solution. The installed timing correction and uncertainty come from promoted calibration. [M03]

### 9.3 Surelite and OPO timing

Surelite Direct Access Triggering Mode 2 requires two negative-going TTL commands, nominally 5 V to 0 V and 10 µs wide: FIRE precedes lasing by about 180 µs and Q-switch precedes lasing by about 170 ns. The FIRE-to-Q interval must be optimized for the installed laser/OPO condition and must preserve the lamp frequency at which the system was optimized. The manual describes approximately ±1 ns external Q-switch jitter. [M01]

Accordingly:

- T660-1 A and B polarity/width/level/termination must meet the installed Surelite receiver at the DB9, verified electrically with the laser inhibited before optical use.
- FIRE-to-Q delay is frozen only from PB-01/PB-02 plus OP-01/IR-01; the repository's nominal 179830 ns value is explicitly uncalibrated and is not authority.
- OPO wavelength motion finishes and a wavelength/readback/power stability gate passes before pump arming. The OPO's internal calibration tables and GUI position do not replace wavelength verification. [M02]
- Pump optical arrival is measured at the sample plane for the chosen wavelength/path; electrical FIRE/Q edges are retained as diagnostics.

### 9.4 MIRcat trigger and wavelength behavior

Use MIRcat **External Trigger mode**, which produces one optical pulse per `TRIG IN` rising edge with width set in laser parameters. Do not confuse it with External Pulse mode, where the incoming pulse width determines optical width. The process trigger on DB9 pin 4 is active low; direct manufacturer correspondence gives a 1–100 ms accepted low interval with 10 ms nominal. These are receiver requirements, not permission to reuse a generic preset. [M05, R06, R10]

MIRcat pulse width, trigger rate, current, wavelength, tuning dwell, and optical trigger latency are chosen by QB-01, MD-01, MSW-01, DET/IR, and manufacturer safety limits. The current generic 2 MHz/150 ns alignment example and 1850 cm⁻¹ preset are not biological authorities. Before emission, software must confirm installed identity, correct range including 1933–1966 cm⁻¹, interlocks, no error, parameter readbacks, and external-trigger mode.

### 9.5 T660 edges, widths, terminations, and interactions

No final numeric delay, pulse width, or termination can be frozen before CL-01/MD-01/OP-01. The configuration table below is the required selection rule:

| Channel | Polarity/receiver requirement | Width rule | Termination rule | Interaction rule |
|---|---|---|---|---|
| T660-2 A | Positive reference marker, exact HF2LI logic mapping verified in MD-01 | Long enough for reliable DIO edge capture; short enough not to overlap the next reference event | Choose 50 Ω source or low-Z only from measured receiver voltage and cable termination; never assume logic level | Must be phase-consistent with B and acquisition windows. |
| T660-2 B | Positive rising edge to MIRcat `TRIG IN` in External Trigger mode | Meet MIRcat trigger minimum and T660 busy/rate constraints; optical width remains MIRcat-set | Verify delivered high/low at receiver and absence of double termination | One accepted electrical edge must map to one optical pulse; missed/double pulses abort. |
| T660-2 C | Positive DAQ marker to HF2LI DIO1 | Meet DIO capture requirement | As measured in MD-01/HF-01 | Must precede/cover acquisition window without leaking into demodulated signal. |
| T660-2 D | Trigger edge to T660-1 | Meet T660-1 trigger amplitude/slew and rate constraints | Verify at receiver | Must not retrigger while a T660-1 shot is busy; rate errors abort. |
| T660-1 A | Negative-going Surelite FIRE command | 10 µs manufacturer nominal [M01] unless installed receiver verification requires a documented adjustment | Delivered 5-to-0 V logic must be verified; source/load pairing selected accordingly | FIRE-to-Q interval held at the promoted optical optimum; lamp rhythm preserved. |
| T660-1 B | Negative-going Surelite external Q-switch | 10 µs manufacturer nominal [M01] unless verified otherwise | Same delivered-level rule | Q event must never occur without an accepted FIRE sequence and safe optical state. |
| T660-1 C | Active-low MIRcat process trigger | 1–100 ms allowed; 10 ms nominal [M05] | Verify DB9 receiver level | Used only for an approved discrete step; cannot overlap unsafe tuning/emission transitions. |
| T660-1 D | Disabled | None | Disconnected | Any observed activity is a fault. |

T660 settings are first staged with all outputs disabled. Configuration readback, delivered waveforms, polarity, amplitude, and channel interactions are verified in a non-emitting state. Configuration changes may force end-of-delay and abort active shots, so changes occur only with triggering disabled and acquisition stopped. [M03]

### 9.6 Detector, splitter, and PicoScope requirements

The sample detector is the recorded VIGO PVM-10.6-1×1/SIP system; the PVM detector data sheet reports a 2–12 µm spectral range, typical 1.5 ns time constant for the uncooled 1×1 mm device, and the SIP family can extend to 250 MHz. Those are family/specification expectations. The exact installed amplifier bandwidth/gain, cable, detector identity, reference-detector identity, saturation, latency, and response are measured in DET-01 through DET-04. [M06, R06]

PicoScope 5244D serial 10261 is the timing/capture instrument. It supports 200 MHz nominal bandwidth, 1 GS/s in 8-bit mode, 500 MS/s in 12-bit mode, and 62.5 MS/s in 16-bit mode; quoted gain accuracy depends on mode and warm-up. [M07]

Final PicoScope setup obeys these requirements:

- enable only required channels and select the highest resolution that still samples the fastest required edge/IRF with sufficient bandwidth;
- set each range so accepted waveforms do not clip while using meaningful ADC span;
- trigger from the promoted DAQ/reference edge and record source, threshold, hysteresis, polarity, coupling, impedance, and delay;
- pretrigger duration must include an artifact-free baseline longer than the promoted IRF/time-zero uncertainty; posttrigger duration must cover the required waveform/latency diagnostic;
- sample interval must resolve the fastest rise/latency quantity used in the claim; record the API-returned actual interval, not only the request;
- record length follows pretrigger + IRF support + normalization windows + safety margin and is checked against memory/rate constraints;
- retain every native block/rapid-block segment, timebase/range, overflow flag, trigger count, and rejected segment; averaging is derived and never replaces raw captures;
- capture sequencing must prove one-to-one correspondence among T660 edge, QCL Trigger Out/optical response where available, detector response, pump timing marker, and acquisition index.

The prior MS timing capture (8 bit, 10 V range, timebase 1, 100000 samples, 1000 pretrigger) is campaign-local evidence, not the biological setup.

### 9.7 HF2LI configuration and dwell

HF2LI device `dev18500` uses the documented sample path on signal input 1/demodulator 0 and reference path on signal input 2/demodulator 3, subject to HF-01 confirmation. DIO0 is the external reference and DIO1 the acquisition marker. Final oscillator/reference mapping, harmonic, phase, input coupling/range, 50 Ω setting, demodulator order/time constant, sample rate, and enabled data streams must come from promoted HF-01/HF-02/PF-01. [R06, M04]

The HF2 manual distinguishes signal bandwidth from noise-equivalent power bandwidth (NEPBW). For filter orders 1–8,

\[
f_{NEPBW}=\{0.2500,0.1250,0.0937,0.0781,0.0684,0.0615,0.0564,0.0524\}/\tau.
\]

Use the correct factor in noise/SNR/NEA calculations. Select sample rate high enough to represent the settled demodulator output and prevent aliasing for the chosen bandwidth; save the actual stream rate/timestamps. Each wavelength/delay acquisition starts only after the manual's 99% settling multiplier for the selected order plus measured tuning/transport settling. [M04]

HF2 input ranges must never overload. A range change, filter change, reference relock, or phase change invalidates the prior settling interval and starts a new configuration/acquisition boundary. Measure and record reference lock/phase stability. Grounding follows the characterized star/differential strategy; the manual warns that ground loops introduce line-frequency artifacts. [M04]

## 10. Safe lifecycle: startup, arming, acquisition, fault, and restoration

This lifecycle defines required state transitions; it deliberately omits commands, IP addresses, and final numerical device settings.

### 10.1 Entry gate

Before any sample or emission activity, the operator shall confirm:

- approved laser, CO/compressed-gas, dithionite, sealed-cell, biological-material, waste, and emergency SOPs/training;
- current installed identities, firmware/software versions, wiring/configuration ID, and physical beam-path inspection;
- valid promoted calibration and characterization bundles covering every selected value and no active revalidation trigger;
- corrected/verified MIRcat capability range and replacement reference-detector identity;
- selected cell/path/seals and temperature stage have passed blank/leak/compatibility checks;
- all expected phase directories/manifests and a unique campaign/phase/run/acquisition namespace are ready under the data contract;
- safe-idle readback: pump blocked/shuttered, MIRcat emission off, T660 outputs disabled, Surelite Q-switch/pump output inhibited, and acquisition not armed.

Any failed item blocks the biological phase. A changed or missing file hash does not.

### 10.2 Controlled startup

1. Establish the laser-controlled area, CO monitor/ventilation, signage, beam enclosures/dumps, eyewear, authorized personnel, and emergency access.
2. Start passive electronics, computer control, HF2LI, PicoScope, detectors/amplifiers, temperature monitoring, and power meter; allow manual-specified warm-up where accuracy depends on it.
3. Connect to MIRcat in GUI-first mode with emission off. Verify identity, interlocks, range/readbacks, trigger mode capability, errors, and cooling/state.
4. Connect to both T660s with outputs disabled. Verify firmware, clock/reference status, routing, polarity/termination staging, forced-safe/EOD behavior, and no rate errors.
5. Start the Surelite only under its approved manufacturer/institutional procedure. The manual calls for 15–20 min thermal stabilization after flashlamp start, prevents shutter opening for the first 20 min after AC power, and calls for 5 min harmonic operation before optimization. The thermal lockout must not be overridden for routine use. [M01]
6. Verify OPO state, covers/interlocks, wavelength calibration validity, residual-beam blocks, and `GoTo`/readback with the pump still contained. [M02]
7. Perform only the nonbiological low-risk diagnostics already authorized by calibration/characterization. Alignment does not use the MbCO sample as a calibrant.

### 10.3 Sample installation and pre-arm confirmation

With pump and probe contained or emission off:

1. Confirm accepted pre-run sample spectra, cell identity/path/fill, absence of bubbles/leaks, sample temperature, cell position, and preparation ID.
2. Install the cell and close/enclose the beam path. Record geometry/configuration/position IDs.
3. Verify detector dark, range, reference lock, background, and sample/reference transmission at non-damaging probe conditions.
4. Stage the complete timing configuration while T660 outputs remain disabled. Compare readbacks with the approved requirements-derived configuration; confirm D remains off and reserved pins remain disconnected.
5. Obtain an explicit operator confirmation of cell, enclosure, personnel, CO monitor, beam dumps, shutters, emission gates, data destination, and abort controls.

### 10.4 Arming and acquisition order

The allowed sequence is:

1. Start/arm acquisition and monitoring with outputs disabled.
2. Enable MIRcat emission gate and verify stable probe/reference response **before** starting T660 trigger pulses.
3. Enable only the approved T660-2 probe/reference/DAQ sequence and verify one-to-one triggers, lock, no error, and stable detector levels.
4. Enable the slow pump timing path with the pump physically blocked; verify FIRE/Q timing and accepted pulse division from electrical/diagnostic markers.
5. Open/enable the final pump shutter or beam gate last, after operator confirmation. Begin with the lowest accepted dose and longest pulse separation.
6. For every acquisition, write readbacks/conditions before or with raw data, monitor error/overload/trigger counts/power/temperature/reference, and interleave required controls/anchors.

Changing wavelength, detector range, HF2 filter/reference, pump power, repetition, timing, cell position, sample fill, or baseline model closes the current acquisition and requires the relevant re-settle/revalidation step.

### 10.5 Normal stop

1. Block/close the pump first.
2. Disable the slow pump path and verify no Q-switch/FIRE events can produce laser output.
3. Stop T660 probe triggering, then disable all T660 outputs and verify safe-idle readback.
4. Disable MIRcat emission; retain cooling/control as required by its manual.
5. Stop acquisition only after final dark/reference/status records are captured.
6. Acquire post-exposure integrity evidence before removing the cell when safe.
7. Remove/secure the sample under the approved CO/waste procedure.
8. Shut down OPO/Surelite by the manufacturer procedure. Surelite daily shutdown stops flashlamps, closes the intracavity and exit shutters, returns the key to standby, and removes the key. [M01]
9. Restore the documented non-emitting baseline configuration, record all readbacks/errors, and complete the restoration report.

### 10.6 Fault response

Any interlock, CO alarm, leak/bubble, laser/OPO/MIRcat error, reference unlock, T660 rate error, missed/extra trigger, detector overload, unexpected optical signal, power/temperature excursion, sample-integrity failure, software exception, or loss of monitoring causes:

1. immediate pump block/shutter closure;
2. disable slow pump timing and all T660 outputs;
3. MIRcat emission off;
4. acquisition marked faulted without overwriting native data;
5. Surelite/OPO safe state or emergency shutdown per manufacturer/EHS procedure;
6. area evacuation/emergency response if the CO monitor, cylinder, cell, fire, or personnel condition requires it;
7. fault record, exclusions, affected acquisition IDs, and full restoration verification.

There is no automatic resume. A qualified operator reviews cause, validity envelopes, sample status, and required recalibration/recharacterization first.

## 11. Kinetic and uncertainty analysis plan

### 11.1 Preprocessing

Analysis is versioned and reproducible from immutable indexed native/raw data. The ordered pipeline is:

1. parse native channels, timestamps, readbacks, trigger counters, ranges, overload/error flags, and identifiers;
2. apply promoted detector latency/response and splitter/relative-response corrections with uncertainty;
3. form dark-corrected sample/reference ratios and matched-background double ratios; retain covariance;
4. convert to absorbance/difference absorbance without clipping or replacing invalid points;
5. label but do not automatically discard settling, fault, or integrity-failed records; exclusions require predeclared reason codes;
6. calculate per-repeat estimates before pooled averages;
7. preserve unsmoothed traces; smoothing, binning, baseline alternatives, or SVD are derived sensitivity products only.

### 11.2 Spectral model

Fit steady and time-resolved spectra jointly when SNR permits:

\[
A(\tilde\nu)=B(\tilde\nu)+\sum_j a_j g_j(\tilde\nu;\mu_j,\sigma_j),
\]

where \(j\) includes only supported A₀/A₁/A₃ components, \(B\) is the predeclared off-band baseline, and parameter covariance is retained. The primary kinetic observable is A₁ integrated bleach or its joint-fit amplitude, not a single noisy channel unless PF-01 shows equivalence.

### 11.3 Kinetic candidates

Use survival/recovery sign conventions consistently. Candidate models include:

**M0 — single apparent recovery**
\[
S(t)=b+f_0\exp(-t/\tau_s).
\]

**M1 — notebook geminate plus pseudo-first-order solvent recovery**
\[
S(t)=b+f_0\left[f_g e^{-t/\tau_g}+(1-f_g)e^{-k_{on}[CO]t}\right].
\]

**M2 — concentration-aware mass balance**

Use coupled rate equations for deoxy-Mb (D) and free CO (C) when photolyzed CO is not negligible relative to dissolved CO:

\[
\frac{dD}{dt}=-k_{on}DC,\qquad
\frac{dC}{dt}=-k_{on}DC,
\]

with (D(0^+)) set by the measured photolyzed fraction after any separately resolved geminate contribution and (C(0^+)) set by the pre-pump dissolved-CO mass balance plus nongeminately released CO. Protein and CO conservation, headspace/flow or refresh behavior, and the measurement window must be explicit. This model is required for 4 mM samples if the perturbation invalidates constant-[CO], as demonstrated by L01. A sum of exponentials may summarize the trace, but it is not automatically a molecular mechanism.

The measured prediction is

\[
\Delta A_{pred}(t)=\Big(\Delta A_{true}*h_{IRF}*h_{det}*h_{acq}*h_{HF2}\Big)(t)+B(t),
\]

with measured/configuration-specific kernels and uncertainty. If acquisition is pointwise settled rather than recording the transient through the lock-in, the applicable filter/window kernel must reflect the actual workflow, not be included twice.

### 11.4 Fit, diagnostics, and model selection

- Fit all technical repeats with an appropriate hierarchical or joint likelihood rather than fitting only a grand mean.
- Use noise/covariance estimated from pre-pump and controls; account for heteroscedasticity and common reference drift.
- Constrain only physical domains (for example nonnegative lifetimes and fractions within 0–1); do not fix \(f_g=0.04\) or \(\tau_g=180\) ns.
- Report parameter covariance/correlation, profile likelihood or bootstrap interval, residuals versus time/order/power/temperature, autocorrelation, leverage/influence, and prediction checks.
- Compare nested/non-nested candidates with predeclared AIC/AICc from the notebook analysis, likelihood-ratio tests where valid, and held-out/predictive residual behavior. Model selection must not rest on \(R^2\) alone. [N01]
- A mechanistic component is accepted only if its interval excludes the relevant boundary, the result is stable to IRF/baseline/noise alternatives, and simulated identifiability under the measured schedule/SNR supports it.
- If M1 and M2 cannot be distinguished, report an apparent recovery model and the ambiguity.

### 11.5 SNR, noise, and sensitivity

At each spectral/delay condition report:

\[
SNR=\frac{|\Delta A|}{s_{pre}},\qquad
NEA=\frac{s_{baseline}}{\sqrt{f_{NEPBW}}},
\]

using the HF2 order-specific NEPBW. Demonstrate the expected \(N^{-1/2}\) averaging trend over the stationary region and use an Allan/deviation-versus-averaging analysis to locate drift onset. PF-01 defines minimum detectable/quantifiable \(\Delta A\), usable averaging duration, and optimal filter settings. [M04, N01]

### 11.6 Uncertainty and sensitivity analysis

The uncertainty budget includes, at minimum:

- path length, Mb concentration, state fraction, temperature, pH, dissolved CO estimate, and dilution;
- sample/reference raw noise and covariance, splitter/response correction, detector nonlinearity, dark drift, and baseline;
- spectral axis and effective resolution;
- pump average power, verified repetition, beam geometry, overlap, pump absorbance, quantum-yield prior, and accepted pulse count;
- time zero, pump/probe durations, jitter, detector latency/response, acquisition window, HF2 filter, and delay setting;
- preparation, cell/reload, day, and configuration random effects;
- model-form choice and fit parameter covariance.

Use Monte Carlo propagation based on the notebook's input inventory, replacing placeholder distributions with measured/promoted estimates and preserving correlated inputs. The notebook's 10,000-draw default is not inherited as a mandatory count; increase draws until reported quantiles are numerically stable and document the convergence rule. [N01]

Report a predicted-versus-measured table for steady A₁ absorbance, initial \(\Delta A\), photolyzed fraction, noise/SNR, IRF width, recovery time, and repetition recovery. Each row states equation/model, inputs and sources, prediction interval, measured estimate, standardized discrepancy, and disposition.

## 12. Replication, randomization, drift, and exclusions

### 12.1 Hierarchy

Technical averages do not replace independent replication. Track these levels separately:

- **preparation:** independent buffer/reduction/CO-ligation workflow;
- **cell/sample:** independent cell assembly/fill or independent aliquot/loading;
- **spectrum:** independent forward/reverse scan or repeated kinetic block after complete reset;
- **delay/power:** raw accepted pulses/records within a block;
- **day:** independent startup/restoration and environmental condition.

For the confirmatory minimum claim, the final number of independent full-procedure replicates is set from pilot variance and the desired uncertainty/power, with the Eurachem 6–15 replicate range as the method-precision benchmark. A resource-limited feasibility stage may use fewer independent preparations or days only as a variance/feasibility pilot; its size must be declared before acquisition and cannot by itself support a high-precision population claim. The final thesis report must clearly label feasibility versus confirmatory evidence. [Q01, Q02]

Within each preparation, acquire enough raw repetitions for PF-01 to establish stationarity and the \(N^{-1/2}\) region; no fixed raw-shot count is inherited. If L04's 20 repeats at 0.5 Hz is used as a start, it remains a cited pilot start and is re-optimized from measured SNR. [L04]

### 12.2 Order and drift

- Randomize pump-power order with a return-to-low anchor.
- Randomize delay order within acquisition-compatible strata; interleave negative and fully recovered anchors.
- Counterbalance scan direction and cell/preparation order across days.
- Do not randomize in a way that violates settling, sample recovery, or safety state transitions.
- Record elapsed time, cumulative pulses/energy, cell position, temperature, reference amplitude/phase, pump average power, and A₁ anchor throughout.
- Model day/preparation/cell as random effects when data support it; otherwise report stratified results.

### 12.3 Exclusion policy

Predeclare reason codes for: interlock/fault; CO/leak/cell failure; detector overflow/under-range; invalid/missing trigger; reference unlock; wavelength/power/temperature outside validity; insufficient settling; bubble/precipitate; sample-state failure; incomplete recovery; cumulative-dose limit; corrupted/incomplete native file; or operator-documented protocol deviation.

Never exclude because a value is inconvenient, a fit residual is large, or a repository hash changed. Preserve excluded raw records and index rows, identify the decision maker/time/reason/evidence, and rerun only under a new acquisition ID.

## 13. Experiment phases, gates, deliverables, and aborts

| Phase | Entry gate | Ordered requirements-level actions | Mandatory deliverables | Acceptance / abort |
|---|---|---|---|---|
| **MB-00 claims and dependency freeze** | This brief reviewed; thesis minimum/optional claims agreed | Freeze analyte/species, observables, models, numeric evidence map, required promoted imports, and exclusions | Approved claim matrix; unresolved-dependency register; analysis preregistration | Abort freeze if a claim lacks an observable, calibration path, or analysis test. |
| **MB-01 safety/procurement readiness** | EHS review available | Select supplier/lot, CO supply/regulator/monitor, cell/windows/spacers/seals, temperature stage, waste route, and UV–visible access | SDS/manual set; training/authorization record; procurement/identity table; emergency plan | Abort for missing CO monitoring/ventilation, incompatible/unknown cell materials, or unapproved waste/gas procedure. |
| **MB-02 promoted platform imports** | PROM-01 and PROM-CH complete and valid | Import axis, timing, detector, normalization, power, beam/overlap, settling, IRF, sensitivity, and reproducibility bundles; fix/verify MIRcat range registry | Calibration links; validity-envelope assessment; configuration registry; readiness report | Abort on missing promotion, stale validity, unresolved reference detector, or software range mismatch. |
| **MB-03 blank/cell qualification** | MB-01/02 pass; no protein | Assemble and measure empty/buffer cell, path, leak, temperature hold, forward/reverse scan, pump-only/probe-only response | Cell/path report; background spectrum; compatibility/leak evidence; baseline/noise results | Abort on leak, bubble-prone fill, pump-correlated blank, insufficient transmission, nonlinearity, or irreproducible fringe. |
| **MB-04 sample chemistry pilot** | Approved sample procedure and UV–visible access | Prepare small independent batches, verify concentration/state/pH/stability, load cell, collect steady IR and post-check | Preparation records; pre/post UV–visible and IR; concentration/path uncertainty; stability window | Abort on mixed/oxidized state beyond validation limit, precipitation, concentration ambiguity, or irreproducible A₁. |
| **MB-05 pump/dose/overlap pilot** | Accepted steady sample; PB/OG/OV imports valid | Verify 540 nm sample-plane beam, begin lowest dose/0.5 Hz, run blank/deoxy/no-pump controls, dose series, overlap scan, post-integrity | Dose-response/overlap maps; derived mean-energy calculation; photolysis estimate; damage ceiling | Abort on pump artifact, nonlinearity at lowest useful dose, temperature/integrity failure, or overlap instability. |
| **MB-06 timing/IRF and discovery kinetics** | MB-05 passes; OP/CL/IR/DET valid | Verify time zero on surrogate, acquire adaptive negative/prompt/slow/recovery schedule, assess SNR/identifiability, repeat-pulse spacing | Time-zero/IRF link; discovery traces; identifiability simulation; selected delay/rate/filter design | Abort mechanistic extension if 180 ns component unidentifiable; abort all kinetics for trigger mismatch, incomplete recovery, or sample damage. |
| **MB-07 confirmatory MVP** | Analysis/settings frozen from independent pilot; sample size set | Run randomized/counterbalanced independent preparations/days, full controls, primary A₁ kinetics, post-integrity, restoration each day | Native/raw and derived datasets; fit diagnostics; uncertainty; predicted-vs-measured; reproducibility report | Accept minimum claim only if all primary criteria and retention audit pass; otherwise report feasibility/limitation. |
| **MB-08 optional mechanistic extension** | MVP accepted; IRF/SNR/model simulation supports extension | Add dense geminate schedule, A₀/A₃ kinetics, concentration series or qualified 532 nm comparison | Extension-specific preregistration, data, model comparison, sensitivity analysis | Keep this phase outside the MVP; stop if validity, sample, or identifiability fails. |
| **MB-09 closeout** | Acquisitions stopped safely | Complete restoration, exclusions, retention audit, result/limitation summary, thesis-ready provenance | Restoration report; retention audit; final tables/figures; readiness/closeout decision | No closeout while hardware state, raw indexing, exclusions, or calibration links are incomplete. |

Every phase that touches hardware inherits the complete safe startup/fault/restoration lifecycle. Advancement requires the deliverables and acceptance record, not a commit/object hash match.

## 14. Data retention and campaign-contract implementation

The biological campaign must conform to `docs/measurement_campaign_data_contract.md`. Create no campaign as part of this brief; the following are requirements for the later authorized campaign. [R04]

### 14.1 Stable identifiers

Every record must carry the applicable stable, human-readable identifiers:

- `campaign_id`, `phase_id`, `phase_run_id`, `acquisition_id`, and `configuration_id`;
- `calibration_bundle_id` and characterization/promotion references;
- sample preparation, supplier/catalog/lot, buffer batch, reductant batch, CO cylinder/gas, cell/window/spacer/seal, temperature stage/sensor, sample detector, reference detector, splitter, cables/adapters, power meter, PicoScope, HF2LI, T660-1, T660-2, MIRcat, Surelite, OPO, workstation/software, and operator IDs.

Use relative repository paths, UTC timestamps, explicit software/schema/analysis versions, branch/commit reference, dirty-file list, and source/producer records. A hash may be displayed for information, but no recorded hash is required to match for loading, analysis, aggregation, reproduction, acceptance, promotion, or closeout.

### 14.2 Phase contents

Each phase retains the contract's required structure and content:

- `phase_manifest` with purpose, claims, status, schema/software/configuration, inputs, entry/exit gates, and owner;
- `acquisition_index.csv` using the exact contract header and one row for every acquired or excluded native object;
- `conditions/` for sample, cell, gas, temperature, optical, timing, detector, power, environment, and operator/readback states;
- `measurements/` for machine-readable tabular outputs using the exact required header, units, uncertainty/provenance fields, and quality flags;
- `artifacts/` for native instrument files, immutable indexed raw exports, logs, screenshots where necessary, and derived products;
- `exclusions/` with reason code, scope, decision, evidence, timestamp, and author;
- `calibration_links/` for promoted bundle IDs, validity envelopes, imported values/uncertainties, and revalidation checks;
- `command_log/` for sent commands/readbacks/state transitions when execution is later authorized;
- `report/`, `restoration/`, `raw/`, `analysis/`, `figures/`, and `tables/` as specified by the contract.

Native/raw objects become immutable when indexed. A correction creates a new derived artifact with parent IDs, method/version, parameters, and reason. No spreadsheet/manual edit replaces native data.

### 14.3 Required condition fields beyond the base contract

At minimum retain: preparation time/history; verified concentration/state/pH; calculated ionic strength/free CO; cell path/fill/headspace/position; sample temperature; pump wavelength/average power/effective rate/derived mean energy/accepted pulse count; beam radii/overlap; probe wavenumber/mode/current/width/rate; every T660 delay/width/polarity/termination/enable/readback; scope trigger/timebase/range/sample interval/record/pretrigger/segments; HF2 reference/demodulator/input/range/order/τ/sample rate/phase/lock; detector gains/bandwidth/cables; time-zero/IRF; scan/delay randomization position; cumulative exposure; control type; pre/post integrity result; and all error/overload/trigger counts.

### 14.4 Retention audit

Closeout verifies all seven contract areas: required files exist; indexed paths resolve; native/raw data are retained; derived lineage is complete; identifiers/configurations/calibration links are consistent; exclusions and restoration are complete; and reports/tables reproduce from retained inputs. Any failure is a closeout blocker; a hash mismatch alone is not.

## 15. Safety and environmental requirements

### 15.1 Governance

Only personnel authorized by the institutional laser safety officer (LSO) and EHS may operate the platform or handle CO/dithionite. This brief does not supersede an institutional SOP, hazard assessment, SDS, training, two-person/occupancy rule, or emergency plan. The current supplier SDS for the exact protein, reductant, buffer reagents, CO cylinder, seals, and cleaning agents must be present.

### 15.2 Class 4 laser and optical hazards

The Surelite/OPO system is Class 4. The OPO manual warns that direct, specular, and diffuse reflections can cause severe eye/skin injury and that pump/output beams may be invisible; OSHA likewise identifies Class IV beams as direct/diffuse ocular, skin, and fire hazards. [S01, M02]

Requirements:

- LSO-approved controlled area, training, standard operating procedure, authorized personnel, entry/interlocks, warning lights/signage, key control, beam enclosures, noncombustible dumps, remote firing/monitoring as required, and spectator exclusion;
- wavelength- and irradiance-appropriate eyewear selected by the LSO for every accessible output/residual (including 355 nm pump, 540/532 nm experiment pump, OPO residual signal/idler/UV, and MIRcat mid-IR); one eyewear label is not assumed to cover the complete 192–2750 nm OPO range;
- remove jewelry/reflective tools and flammables; keep beams below eye level, avoid open vertical paths, and verify beam-off with an appropriate detector before entering the beam path; [M02]
- covers and interlocks remain active; no routine interlock defeat or thermal-lockout override;
- pump opens last and closes first; no unattended emission or automatic fault resume;
- stray pump light is blocked before the IR detectors, following the artifact-control logic used in L01.

### 15.3 Carbon monoxide and compressed gas

CO is colorless, odorless, acutely toxic, flammable, and supplied under pressure. NIOSH lists a 35 ppm time-weighted REL and 200 ppm ceiling; the current OSHA PEL is 50 ppm TWA. These are regulatory/reference limits, **not alarm setpoints for this lab**; EHS defines monitor/alarm/evacuation settings. [S02, S03]

Requirements:

- use CO only in an EHS-approved ventilated enclosure/hood with a compatible continuous CO monitor, current calibration/bump-test status, audible/visible alarm, and known evacuation response;
- secure the cylinder, use a CO-compatible regulator/check valve/tubing/fittings, label lines, leak-test by the approved method, and route purge/exhaust to the hood—never to the room;
- minimize connected volume and quantity; close the cylinder/isolate lines when not actively needed;
- never rely on smell, never work alone if the institutional assessment requires two people, and never attempt rescue in an alarmed atmosphere without trained emergency response;
- use atmospheric-pressure equilibration; do not pressurize a demountable spectroscopy cell;
- a CO alarm, suspected leak, damaged line/regulator, unexplained pressure change, cell leak, dizziness/headache, or ventilation loss invokes pump-off, safe shutdown if reachable without exposure, evacuation, emergency notification, and medical/EHS response.

The Airgas CO SDS classifies compressed CO as flammable gas category 1, gas under pressure, acute inhalation toxicity category 3, and reproductive toxicity category 1; the exact supplied-gas SDS controls. [S03]

### 15.4 Sodium dithionite and chemistry

Sodium dithionite is a strong reducing agent with decomposition/fire and sulfur-oxide hazards; water/acid exposure and storage conditions require the exact supplier SDS. [S04]

- handle/weigh/prepare only under the approved hood/PPE/storage procedure and on the smallest practical scale;
- keep away from acids, oxidizers, moisture/heat sources, and incompatible waste;
- prepare fresh only when authorized; label concentration/time/operator and do not store an improvised stock beyond its validated/approved period;
- collect protein/dithionite/CO-contact waste in the EHS-designated compatible container; no drain disposal without explicit approval;
- treat gas-exposed syringes/cells/tubing as CO-containing until safely vented/purged in the hood.

### 15.5 Biological material, cell, and waste

Commercial equine myoglobin is handled at the institutional risk level defined by its SDS; standard laboratory hygiene, gloves, eye protection, cleanable containment, and no ingestion/aerosol generation apply. The sample contains chemical hazards despite being a purified protein.

Inspect CaF₂ windows for chips/cracks and handle them with eye/hand protection appropriate to fragile optics and chemicals. Use a shield/secondary containment during leak testing/filling. Never tighten or heat a sealed cell beyond manufacturer limits. A cracked, leaking, pressurized, or stuck cell is isolated and handled under the approved response—not opened at the instrument.

Separate contaminated protein/reductant liquid, sharps/broken windows, solvent/cleaner waste, and cylinder/regulator return streams. Document waste container/route and final disposition.

## 16. Calibration and characterization dependency map

### 16.1 Results that must be promoted before recipe freeze

| Imported result | Source phase(s) | Used for | Required content/validity |
|---|---|---|---|
| Installed identities/topology/configuration | P0, S0, TR-01 | All device/sample records and wiring | Exact serial/device/cable/adapter/reference-detector identity; wiring unchanged or reviewed. |
| Scope/cable/splitter timing correction | MS-01, MS-02 | Electrical timing uncertainty | Corrected reference-plane offsets/uncertainty; campaign-local values only after promotion. |
| T660-2 route delays | T2-01 | Probe/reference/DAQ/pump-chain alignment | Per route corrected intercept/slope/uncertainty and valid configuration. |
| T660-1 FIRE/Q timing | T1-01 | Surelite DAT2 timing | Trigger-to-FIRE/Q offsets, closure, adapter/cable IDs, uncertainty. |
| Power-meter readiness | OM-01 | Direct pump average power | Meter identity, wavelength response, geometry, zero/range, validity. |
| Optical transfer/splitter | ATT-01, DET-04 | Sample/reference normalization and sample-plane power | Measured ratios versus wavelength/configuration with uncertainty; no 50/50 assumption. |
| HF2LI configuration/streams | HF-01, HF-02 | Reference/demodulators/filter/sample rate/data fields | Exact node mapping, demods 0/3, DIO mapping, LabOne version, τ/order/rates/readbacks. |
| MIRcat DIO/process mapping | MD-01 | TRIG IN/process/Trigger Out behavior | One-to-one edge behavior, active levels, widths, DIO20/21/22 mapping, no reserved-pin use. |
| MIRcat sweep/settling | MSW-01, AR-01 | Wavelength order/dwell | Direction-dependent tune latency/stability and 99% criterion. |
| Detector dark/linearity/latency/normalization | DET-01–DET-04 | Ranges, noise, IRF, dual normalization | Exact sample/reference detector identities, gains/bandwidths, latency offset, linear envelope, covariance. |
| Spectral references and axis | SP-01, SP-02, SV-01, SV-02 | 1933–1966 cm⁻¹ setpoints/uncertainty | Reference provenance, axis correction/uncertainty, verified usable range, resolution. |
| Pump command-to-sample timing | OP-01 | Optical time zero | 540/532 nm sample-plane arrival, reference plane, wavelength/path/configuration uncertainty. |
| Full clock chain/end to end | CL-01, E2E-01, E2E-CH | Delay sign/range, trigger sequencing, restoration | One-to-one mapping, no channel interaction, missed/extra-trigger behavior, end-to-end uncertainty. |
| Nd:YAG/OPO power/beam | PB-01, PB-02 | Wavelength selection, average power, duration/stability | 355 nm pump/OPO output; sample-required 540 nm and fallback 532 nm if used. |
| Probe envelope | QB-01 | MIRcat frequency/current/width/rate | Valid optical envelope across the core spectral window and safe detector/sample limits. |
| Sample-plane geometry/overlap | OG-01, OV-01 | Fluence model, illuminated volume, overlap fraction | Beam profiles/radii/positions/polarization and stable overlap with uncertainty. |
| Instrument response | IR-01 | Convolution, time zero, geminate identifiability | Measured sample-plane IRF and constituent response model across used configuration. |
| Sensitivity/noise | PF-01 | SNR, averaging, filter/dwell, quantification | Noise covariance, NEA, averaging/Allan behavior, detectable/quantifiable ΔA. |
| Reproducibility | RPT-01, RPT-CH | Drift/repeatability limits and revalidation | Within/between-startup/configuration results and control limits. |
| Promotion/validity | PROM-01, PROM-CH | Operational permission to freeze values | Canonical bundle IDs, uncertainty, validity envelope, revalidation triggers, limitations. |

### 16.2 Literature-derived biological starts

Species, 4 mM nominal concentration, 25 mM phosphate/pH 7.0, four equivalents dithionite, atmospheric CO equilibration, 10–25 µm path bracket, 293 K, 540 nm pump, A-band assignments, approximately 180 ns geminate prior, 10² µs–1 ms slow regime, and the 0.5 Hz conservative starting pump rate may enter pilot planning from literature. They never override measured sample integrity or promoted instrument limits. [L01–L09]

### 16.3 Proposed measurements that are unnecessary or out of scope

- Do not buy or simulate a pulse-energy meter result for this study; report average power and derived mean energy with the stated limitation.
- Do not claim pulse-to-pulse energy distribution or peak power from average power.
- Do not measure an absolute polystyrene/Mylar film path to support this biological claim; those references support spectral validation only within their promoted scope.
- Do not remeasure timing or spectral calibration with MbCO; use nonbiological standards/surrogates.
- Do not add a docking-site probe near 2119–2131 cm⁻¹; it is outside the installed range.
- Do not perform an absolute quantum-yield campaign unless the thesis claim explicitly expands and the needed metrology is separately approved.
- Do not restore archived recipes, reconnect the Arduino multiplexer, use reserved MIRcat pins, or invent a new physical topology for convenience.
- Do not make hash/checksum matching an operational or analytical gate.

## 17. Minimum viable sequential plan

The following stages retain their dependency order. Advancement is controlled
by entry gates, mandatory deliverables, and acceptance decisions rather than
calendar dates.

| Order | Mandatory outcome | Decision |
|---|---|---|
| **1 — requirements and readiness** | Review this brief; freeze minimum claim; select/procure Mb, cell/spacers/seals, CO hardware/monitor, temperature solution; approve safety/sample concepts; correct MIRcat range representation. | If required cell/CO safety items are unavailable, narrow thesis to platform/steady-state validation rather than improvising. |
| **2 — instrument dependencies** | Finish/promote calibration and characterization imports required for 1933–1966 cm⁻¹, 540 nm pumping, dual detection, timing/IRF, overlap, settling, and sensitivity. Qualify blank cell/path. | No biological recipe freeze without PROM-01/PROM-CH and reference detector identity. |
| **3 — chemistry and steady-state pilot** | Chemistry/steady-state pilot; verified pre/post UV–visible and IR; select concentration/path; prove blank/no-pump/pump-only behavior. | Stop if stable MbCO/A₁ cannot be produced reproducibly. |
| **4 — dose and kinetics pilot** | Dose/overlap/time-zero/discovery kinetics at conservative rate; finalize MVP power, delay grid, dwell/filter, sample replacement, and analysis preregistration. | Drop geminate extension if IRF/SNR identifiability fails. |
| **5 — confirmatory acquisition** | Confirmatory A₁ MVP across independent preparations/days with full controls and post-integrity. | Prioritize the complete reproducible minimum claim over extra bands/models. |
| **6 — locked analysis and closeout** | Locked analysis rerun, uncertainty/sensitivity, retention/restoration audit, thesis figures/tables, limitations. | No post-freeze setting/model changes without labeling them exploratory. |

### Mandatory MVP

- accepted, independently verified equine-heart MbCO sample;
- matched blank and pre/post integrity controls;
- accepted A₁ steady-state spectrum with axis/path/normalization uncertainty;
- 540 nm pump dose-response in a no-damage linear regime;
- sample-plane time zero/IRF and adaptive delays resolving at least the microsecond–millisecond recovery;
- recovery/repetition qualification at the chosen effective pump rate;
- independent preparation/day replication set by pilot precision;
- IRF-convolved apparent recovery model, residuals, uncertainty, and data-contract audit.

### Optional extensions, in priority order

1. Resolved 180 ns geminate fraction/lifetime.
2. A₃ and A₀ state-specific kinetics.
3. Concentration series sufficient for explicit second-order kinetics.
4. Qualified 532 nm versus 540 nm excitation comparison.
5. Flow-cell or translation-stage comparison.

## 18. Final readiness checklist

### Scientific and sample

- [ ] Minimum and optional claims are separated and analysis/model criteria preregistered.
- [ ] Equine-heart Mb supplier/catalog/lot/form/purity/SDS and concentration basis are recorded.
- [ ] Buffer formulation, calculated ionic strength, pH method, temperature, dithionite, oxygen exclusion, and CO mass-balance method are approved.
- [ ] Pre-run UV–visible MbCO state spectrum passes; steady A₁ spectrum passes.
- [ ] Prepared-sample stability and maximum delay from preparation to acquisition are validated.
- [ ] Cell/window/spacer/seal IDs, measured path, fill/dead volume, leak test, and compatibility pass.
- [ ] Sample temperature measurement/control and post-exposure verification pass.

### Calibration, characterization, and software

- [ ] PROM-01 and PROM-CH bundles exist, are valid, and cover the selected configuration.
- [ ] Replacement reference detector identity and DET-01–04 results are promoted.
- [ ] MIRcat registry/range accepts and verifies 1933–1966 cm⁻¹ without bypass.
- [ ] 540 nm PB-02/OG/OV characterization passes; 532 nm is absent unless separately qualified.
- [ ] SP/SV axis, OP/CL time zero, IR-01 IRF, AR dwell, HF configuration, PF sensitivity, and RPT reproducibility are imported with uncertainty.
- [ ] No imported archived recipe or campaign-local unpromoted value is treated as final.

### Timing and acquisition

- [ ] Fixed wiring/pin reservations match the recorded topology; Arduino multiplexer is bypassed.
- [ ] Every T660 channel delay/width/polarity/termination is derived from promoted receiver/timing evidence; D is off.
- [ ] Surelite lamp repetition/thermal behavior and DAT2 FIRE/Q requirements are preserved.
- [ ] MIRcat External Trigger mode and process trigger are verified; one edge gives one optical pulse.
- [ ] PicoScope actual interval/range/trigger/pretrigger/record/capture sequence passes with no overflow.
- [ ] HF2 sample/reference demodulators, reference lock, sample rate, τ/order/NEPBW, and 99% settling dwell pass.
- [ ] Pump–probe sign convention, sample-plane zero, IRF, accessible range, and adaptive grid are documented.
- [ ] Effective pump rate, complete recovery, cumulative-dose ceiling, sample refresh/replacement, and inter-scan anchors pass.

### Power and controls

- [ ] Direct sample-plane average power and uncertainty are recorded.
- [ ] Effective optical repetition is independently verified.
- [ ] Mean pulse energy is labeled derived; no distribution/peak-power claim exists.
- [ ] Pump absorbance, overlap, illuminated volume, predicted/observed photolysis, heating screen, and cumulative exposure are documented.
- [ ] Dark, empty-cell, matched blank, no-pump, pump-only, probe-only, deoxy/alternate state, time-zero surrogate, dose, repetition, preparation, reload, and post-integrity controls are complete.

### Safety, data, and closeout

- [ ] LSO/EHS training, SOPs, SDSs, controlled area, eyewear, interlocks, enclosures/dumps, and emergency stop pass.
- [ ] CO cylinder/regulator/ventilation/continuous monitor/leak test/alarm/evacuation and waste routes pass.
- [ ] Dithionite, biological, cell/sharps, and contaminated-waste controls pass.
- [ ] Phase manifest, acquisition index, conditions, measurements, native/raw, derived lineage, exclusions, calibration links, command log, report, and restoration are complete.
- [ ] Native files are indexed/immutable; every correction has a derived parent/analysis version.
- [ ] Retention audit and safe restoration pass; no hash match is used as a gate.

## 19. Unresolved dependencies and disposition

| ID | Dependency | Blocks | Owner/result needed | Disposition |
|---|---|---|---|---|
| U01 | No promoted calibration bundle | Any frozen timing/spectral/power/normalization setting | Complete PROM-01 with validity envelope | Hard gate. |
| U02 | No promoted characterization bundle | Pump/probe/geometry/settling/IRF/sensitivity/reproducibility settings | Complete PROM-CH | Hard gate. |
| U03 | Reference detector identity recorded; DET-01–04 remain incomplete | Dual normalization and latency | Complete DET-01–04 for installed SIP `445161066` / detector `21834` | Identity resolved; performance remains a hard gate. |
| U04 | MIRcat builder range 900–1800 cm⁻¹ conflicts with installed 1638.8–2077.3 cm⁻¹ | A₀/A₁/A₃ recipe construction | Correct configuration/capability implementation and verify with SP/QB evidence | Hard software-readiness gate. |
| U05 | No qualified gas-tight 10/25 µm aqueous cell/path/seal in inventory | Sample handling and quantitative absorbance | Select/procure, measure path, blank/leak/compatibility test | Hard gate. |
| U06 | Temperature stage/sensor capability not established | Rate comparison and CO estimate | Characterize sample temperature control/uncertainty | Hard gate for quantitative kinetics; report limitation for feasibility only. |
| U07 | Exact Mb supplier/lot and UV–visible access not selected | State/concentration verification | Procure and document; validate spectral method | Hard gate. |
| U08 | CO/EHS equipment and approved procedure not evidenced here | Any CO preparation | EHS approval, cylinder/regulator/hood/monitor/SOP/waste | Hard safety gate. |
| U09 | 540 nm sample-plane OPO output uncharacterized | Pump selection/dose | PB-02/OG-01/OP-01 at 540 nm | Hard gate; 532 nm requires separate qualification. |
| U10 | Probe envelope at 1933–1966 cm⁻¹ not promoted | Probe width/rate/current/throughput | QB-01/SV/PF results | Hard gate. |
| U11 | Optical time zero and full IRF absent | Delay values and geminate claim | OP-01/CL-01/IR-01/DET-03 | Hard gate for kinetics. |
| U12 | Sample-specific variance/damage/recovery unknown | n, averaging, pump rate/dose, replacement | MB-04–06 pilots | Pilot-dependent; cannot be literature-frozen. |

## 20. Source key and bibliography

Direct PDF links are supplied where a stable public PDF was located; otherwise the DOI or authoritative landing page is given. Repository manuals are linked to their read-only local copies and, where available, a manufacturer PDF.

### Primary MbCO and method literature

- **[L01]** M. Schleeger, C. Wagner, M. J. Vellekoop, B. Lendl, and J. Heberle, “Time-resolved flow-flash FT-IR difference spectroscopy: the kinetics of CO photodissociation from myoglobin revisited,” *Analytical and Bioanalytical Chemistry* 394, 1869–1877 (2009). DOI: [10.1007/s00216-009-2871-0](https://doi.org/10.1007/s00216-009-2871-0). [Full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC2709881/); [direct PDF](https://link.springer.com/content/pdf/10.1007/s00216-009-2871-0.pdf).
- **[L02]** E. R. Henry, J. H. Sommer, J. Hofrichter, and W. A. Eaton, “Geminate recombination of carbon monoxide to myoglobin,” *Journal of Molecular Biology* 166, 443–451 (1983). DOI/landing: [10.1016/S0022-2836(83)80094-1](https://doi.org/10.1016/S0022-2836(83)80094-1).
- **[L03]** L. Wan, M. B. Twitchett, L. D. Eltis, A. G. Mauk, and M. Smith, “In vitro evolution of horse heart myoglobin to increase peroxidase activity,” *PNAS* 95, 12825–12831 (1998). DOI: [10.1073/pnas.95.22.12825](https://doi.org/10.1073/pnas.95.22.12825); [full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC23613/); [direct PDF](https://pmc.ncbi.nlm.nih.gov/articles/PMC23613/pdf/pq012825.pdf).
- **[L04]** B.-J. Schultz, H. Mohrmann, V. A. Lorenz-Fonfría, and J. Heberle, “Protein dynamics observed by tunable mid-IR quantum cascade lasers across the time range from 10 ns to 1 s,” *Spectrochimica Acta Part A* 188, 666–674 (2018). DOI: [10.1016/j.saa.2017.01.010](https://doi.org/10.1016/j.saa.2017.01.010); [direct author-manuscript PDF](https://refubium.fu-berlin.de/bitstream/handle/fub188/26397/Schultz_Protein_2017.pdf?isAllowed=y&sequence=1).
- **[L05]** M. Devereux and M. Meuwly, “Structural assignment of spectra by characterization of conformational substates in bound MbCO,” *Biophysical Journal* 96, 4363–4375 (2009). DOI: [10.1016/j.bpj.2009.01.064](https://doi.org/10.1016/j.bpj.2009.01.064); [full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC2711460/); [direct PDF](https://pmc.ncbi.nlm.nih.gov/articles/PMC2711460/pdf/main.pdf).
- **[L06]** K. A. Merchant et al., “Myoglobin–CO substate structures and dynamics: multidimensional vibrational echoes and molecular dynamics simulations,” *Journal of the American Chemical Society* 125, 13804–13818 (2003). DOI: [10.1021/ja035654x](https://doi.org/10.1021/ja035654x); [direct author PDF](https://finkelsteinlab.org/assets/pdfs/0001-2003-JACS-Merchant%20et%20al.pdf); [full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC2435512/).
- **[L07]** J. D. Müller et al., “Connection between the taxonomic substates and protonation of histidines 64 and 97 in carbonmonoxy myoglobin,” *Biophysical Journal* 77, 1036–1051 (1999). DOI: [10.1016/S0006-3495(99)76954-7](https://doi.org/10.1016/S0006-3495(99)76954-7); [full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC1300394/); [direct PDF](https://pmc.ncbi.nlm.nih.gov/articles/PMC1300394/pdf/10423448.pdf).
- **[L08]** W. J. Bowen, “The absorption spectra and extinction coefficients of myoglobin,” *Journal of Biological Chemistry* 179, 235–245 (1949). DOI/landing: [10.1016/S0021-9258(18)56832-0](https://doi.org/10.1016/S0021-9258(18)56832-0); [direct publisher PDF](https://www.jbc.org/article/S0021-9258(18)56832-0/pdf).
- **[L09]** T. Polack et al., “CO vibration as a probe of ligand dissociation and transfer in myoglobin,” *Physical Review Letters* 93, 018102 (2004). DOI: [10.1103/PhysRevLett.93.018102](https://doi.org/10.1103/PhysRevLett.93.018102); [publisher PDF](https://link.aps.org/pdf/10.1103/PhysRevLett.93.018102).
- **[L10]** U. Samuni et al., “Kinetic modulation in carbonmonoxy derivatives of truncated hemoglobins: the role of distal heme pocket residues and extended apolar tunnel,” *Journal of Biological Chemistry* 278, 27241–27250 (2003). Its comparison used aqueous horse-heart MbCO and 8 ns, 532 nm excitation at 1 Hz. DOI: [10.1074/jbc.M212634200](https://doi.org/10.1074/jbc.M212634200); [publisher PDF](https://www.jbc.org/content/278/29/27241.full.pdf).
- **[L11]** NIST Chemistry WebBook SRD 69, “Carbon monoxide—Henry’s Law data,” values at 298.15 K. [Authoritative data page](https://webbook.nist.gov/cgi/cbook.cgi?ID=C630080&Mask=10).
- **[L12]** R. W. Cargill (ed.), *IUPAC Solubility Data Series, Vol. 43: Carbon Monoxide* (1990). [Direct IUPAC PDF](https://iupac.github.io/SolubilityDataSeries/volumes/SDS-43.pdf).
- **[L13]** K. Y. Oang et al., “Conformational substates of myoglobin intermediate resolved by picosecond X-ray solution scattering,” *Journal of Physical Chemistry Letters* 5, 804–808 (2014). DOI: [10.1021/jz4027425](https://doi.org/10.1021/jz4027425); [full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC3985870/); [direct author PDF](https://time.kaist.ac.kr/pub/98.pdf).

### Notebook and repository authorities

- **[N01]** `C:\Users\Chris\Documents\UC Davis\SETI\Thesis\articles\rsi-pump-probe\supplement\notebook\RSI_Supplemental_Theoretical_Calculations.nb`, canonical theoretical notebook, inspected read-only. Used for required variables/equations, model alternatives, lock-in response, normalization, noise/SNR, repeated-pulse relation, Monte Carlo input inventory, and predicted-versus-measured structure. Its Mb numerical entries are placeholders or literature start values unless independently cited.
- **[R01]** [Repository scope](../docs/repository_scope.md) and root/experiments `AGENTS.md`/README rules.
- **[R02]** [Repository cleanup and active-authority boundary](../docs/repository_cleanup_20260814.md).
- **[R03]** [Calibration campaign](../calibration/system_recalibration_001/README.md), its manifests/status/gap analysis/phase evidence, and promotion rules.
- **[R04]** [Measurement campaign data contract](../docs/measurement_campaign_data_contract.md).
- **[R05]** [Experiments requirements-design boundary](README.md).
- **[R06]** [P0 physical inventory](../calibration/system_recalibration_001/manifests/p0_physical_inventory.md), [requirement decisions](../calibration/system_recalibration_001/manifests/p0_requirement_decisions.md), wiring/topology, and blocker table.
- **[R07]** Current campaign-local MS-02, T2-01, and T1-01 results, treated as unpromoted evidence only.
- **[R08]** [Characterization sequence](../characterization/system_characterization_001/plans/characterization_sequence.md), characterization matrices/contracts, biological handoff requirements, and current status.
- **[R09]** Current experiment-builder/device-registry and safe-restoration implementation, inspected read-only; current MIRcat 900–1800 cm⁻¹ registry conflict recorded as U04.
- **[R10]** Current MIRcat manufacturer correspondence and process-trigger constraints retained by the active campaigns.
- **[R11]** Current calibration gap analysis: partial campaign complete, not promoted.
- **[R12]** Current characterization status: framework complete, experimental requirements/results not promoted.

### Installed-device/manufacturer sources

- **[M01]** Continuum, *Surelite Nd:YAG Laser Manual*, especially daily startup/shutdown, pulse division, DAT Mode 2, timing, thermal stabilization, and pulse-width diagnostics. [Local read-only PDF](../docs/YAG/Surelite%20NdYAG%20Laser%20Manual.pdf).
- **[M02]** Continuum, *Horizon Oscillating Parametric Oscillator Operation Manual*, especially Class 4 safety, 355 nm pumping, wavelength control, and 0.1 nm calibration-device requirement. [Local read-only PDF](../docs/SLOPO/Horizon%20Oscillating%20Parametric%20Oscillator%20Operation%20Manual.pdf).
- **[M03]** Highland Technology, *T660 Digital Delay Generator Technical Manual* (2025), timing, trigger/busy behavior, terminations, forced EOD, and jitter. [Local read-only PDF](../docs/T660/Highland%20Technologies%20T660%20Manual.pdf).
- **[M04]** Zurich Instruments, *HF2 User Manual*, revision 26.04, filter bandwidth/NEPBW, settling, grounding, and device behavior. [Manufacturer direct PDF](https://docs.zhinst.com/pdf/ziHF2_UserManual.pdf); [local read-only PDF](../docs/HF2LI/Zurich%20Insturments%20HF2LI%20User%20Manual.pdf).
- **[M05]** Daylight Solutions, *MIRcat-QT User Manual* and installed SDK guide, external-trigger/external-pulse/process-trigger behavior. [Local manual](../docs/MIRcat/Daylight%20Solutions%20MIRcat%20Manual.pdf); [SDK guide](../docs/MIRcat/SDK/MIRcatSDKGuide.pdf).
- **[M06]** VIGO Photonics, PVM-10.6 detector and SIP-TO39 amplifier data sheets. [Local read-only detector package PDF](../docs/Detectors/MIDIR-Detector-Package.pdf).
- **[M07]** Pico Technology, *PicoScope 5000D Series Data Sheet*. [Local read-only PDF](../docs/PicoScope/PicoScope%205000D%20Series%20Data%20Sheet.pdf); [manufacturer product family](https://www.picotech.com/oscilloscope/5000/flexible-resolution-oscilloscope).

### Safety and quality sources

- **[S01]** U.S. OSHA, *OSHA Technical Manual, Section III, Chapter 6: Laser Hazards*. [Authoritative page](https://www.osha.gov/otm/section-3-health-hazards/chapter-6).
- **[S02]** NIOSH, *Pocket Guide to Chemical Hazards*, carbon monoxide entry. [Direct CDC PDF](https://stacks.cdc.gov/view/cdc/209666/cdc_209666_DS1.pdf); [NIOSH IDLH page](https://www.cdc.gov/niosh/idlh/630080.html).
- **[S03]** Airgas, *Carbon Monoxide Safety Data Sheet*, SDS 001014. [Current SDS endpoint](https://www.airgas.com/msds/001014.pdf).
- **[S04]** Sigma-Aldrich/Merck, *Sodium dithionite Safety Data Sheet*. [Current SDS page/PDF endpoint](https://www.sigmaaldrich.com/sds/sigma/71699).
- **[Q01]** B. Magnusson and U. Örnemark (eds.), Eurachem Guide, *The Fitness for Purpose of Analytical Methods*, 2nd ed. (2014), especially §6.6 on independent replication and typical 6–15 replicate precision studies. [Direct PDF](https://www.eurachem.org/images/stories/Guides/pdf/MV_guide_2nd_ed_EN.pdf).
- **[Q02]** Eurachem, *Planning and Reporting Method Validation Studies* supplement (2019), nested intermediate-precision designs and independent runs. [Direct PDF](https://www.eurachem.org/images/stories/Guides/pdf/MV_Guide_planning_supplement_EN.pdf).
- **[Q03]** B. N. Taylor and C. E. Kuyatt, NIST Technical Note 1297, *Guidelines for Evaluating and Expressing the Uncertainty of NIST Measurement Results*. [NIST landing/PDF link](https://www.nist.gov/pml/nist-technical-note-1297).

## 21. Parameter-to-source traceability summary

| Parameter family | Direct evidence | Instrument/pilot dependency | Result used in this brief |
|---|---|---|---|
| Sample identity/preparation | L01, L03, L08 | MB-04 UV–visible/IR, supplier lot, cell | Equine-heart, 4 mM start, 25 mM phosphate pH 7, 4 eq dithionite, CO equilibration. |
| CO concentration | L01, L11, L12 | Measured T/P/headspace/liquid and mass balance | Approximately 1 mM expectation only; calculate actual estimate. |
| Cell/path | L01, L09 | Cell procurement, path measurement, DET/PF | 10 µm start, 25 µm alternative; final from transmission/signal/linearity. |
| Bands/window | L01, L04–L07 | SP/SV/QB and sample fit | A₃/A₁/A₀; 1900–1980 core, 1850–2050 survey. |
| Pump | L01, L09, L10, M01, M02 | PB/OG/OV/OP/IR and dose pilot | 540 nm primary; 532 nm conditional; measured duration/power/geometry. |
| Photolysis/dose | L01, L09, N01 | OM/PB/OG/OV/PF and MB-05 | Lowest linear accepted dose; 25% literature ceiling for development. |
| Kinetics/delay | L01, L02, L13, N01 | OP/CL/DET/IR/PF and identifiability pilot | Cover ~180 ns and 10² µs–1 ms; adaptive grid through recovery. |
| Repetition/refresh | L01, L04, M01, N01 | Recovery/damage pilot | Start 0.5 Hz effective pump while preserving lamp rate; promote only passing rate. |
| Timing/routing | M01, M03, M05, R03, R06–R08 | PROM-01/PROM-CH | Fixed wiring; all final edges/delays/terminations from promoted results. |
| Detectors/acquisition | M04, M06, M07 | DET/HF/PF/IR | Dual normalized response, actual capture settings, filter-specific NEPBW/settling. |
| Replication/uncertainty | Q01–Q03, N01 | Pilot variance and method precision | Independent hierarchy; 6–15 validation benchmark; Monte Carlo from measured inputs. |
| Safety | S01–S04, M01, M02 | Institutional LSO/EHS and exact SDS | Class 4/CO/dithionite/cell controls and emergency lifecycle. |

---

**Freeze decision:** this document is ready for design review. An executable biological recipe is **not** ready. Recipe freeze requires resolution of U01–U11, completion of MB-00 through MB-04, and a documented pilot selection of all PILOT-class quantities. The minimum scope remains valid only if those gates are resolved without bypassing safety, promotion, or data-contract requirements.
