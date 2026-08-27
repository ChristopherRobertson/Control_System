# Horseradish peroxidase–CO spectroscopy and time-resolved kinetics: requirements brief

> **2026-08-26 acquisition amendment:** HRP remains first biological use and covers
> fixed-wavelength kinetics plus both stroboscopic reconstructions in
> `time_resolved_acquisition_modes.md`. Settings remain prospective until required
> promotion; a single rapid scan is never an instantaneous spectrum.

- **Document class:** requirements-level experimental procedure; not an executable recipe
- **Selected system:** native, glycosylated horseradish peroxidase isoenzyme C in the ferrous carbonmonoxy state, HRP-C(FeII)–CO
- **Target environment:** room-temperature aqueous 0.10 M sodium phosphate, pH 6.00
- **Primary observables:** equilibrium ν(CO) bands near 1905 and 1934 cm⁻¹ and their pump-induced differential signals
- **Required pump:** WM-01-verified 540 nm OPO output through the permanent ATT-01-qualified electronic iris at its locked far-field mount and accepted aperture diameter
- **Status:** blocked from biological execution until the readiness gates in this brief are satisfied and the necessary campaign results are explicitly promoted

This brief defines what must be true, measured, recorded, and accepted before a biological run. It does not authorize sample preparation, gas handling, laser emission, hardware operation, or promotion. Values marked **literature anchor** reproduce a published or manufacturer value. Values marked **campaign-resolved** may be used only after an identified calibration or characterization result is promoted. Values marked **CH00 decision** are proposed project criteria that must be approved and frozen in characterization phase CH00 before becoming operational. No Git or file hash is an operational gate.

## 1. Decision summary and scope

The coherent chemical model is native HRP isoenzyme C, not an unspecified commercial HRP mixture, in the reduced CO-bound state. The starting preparation is 3.0 mM HRP-C in 0.10 M sodium phosphate at pH 6.00, reduced anaerobically with a 10-fold molar excess of sodium dithionite and equilibrated against 1.00 atm CO at room temperature. These values sit inside the 3–8 mM IR concentration, 0.10 M phosphate, 10-equivalent dithionite, and 1 atm CO system used by Doster et al.; a 25 µm PTFE spacer is selected within their 10–50 µm CaF₂ cell range ([Doster et al., direct PDF](https://wolfgang-doster.de/Gesamtfolder/jmb87hrp.pdf)).

The minimum viable experiment (MVP) is:

1. verify the ferric starting material and the ferrous–CO product by UV–visible spectroscopy;
2. establish the dark, unpumped QCL spectrum across a campaign-proven window that contains both HRP-C–CO bands;
3. record sample/reference-normalized steady-state spectra and negative controls;
4. use rare, optically observed post-iris 540 nm pump events and time-stamped dual-detector monitoring to measure the room-temperature recovery envelope;
5. report a measured recovery rate and determine, rather than assume, the allowable pump cadence;
6. withhold nanosecond pocket/escape kinetics unless the optional fast branch passes its additional timing and exposure gates.

The key room-temperature flash-photolysis study used 530 nm, which supports visible heme-band excitation but does not by itself establish quantitative equivalence at 540 nm. This campaign deliberately uses the same 540 nm OPO configuration required by the later MbCO campaign so the permanent iris, residual-spectral-content bound, sample-plane transfer, timing, and operational envelope are characterized once. HRP-specific absorbance, reversible dose response, photolysis efficiency, and damage limits are still measured in the HRP pilot and are never imported from MbCO. Direct 532 nm is outside the HRP MVP and requires a separately approved path qualification if later proposed.

## 2. Scientific questions, hypotheses, and claim boundaries

### 2.1 Primary questions

- Does prepared HRP-C(FeII)–CO at pH 6.00 show two resolvable bound-CO populations in the neighborhood of 1905 and 1934 cm⁻¹, as reported for HRP-C?
- Does post-iris 540 nm excitation produce a prompt loss of bound-CO absorbance at one or both ν(CO) bands, with a corresponding recovery attributable to rebinding?
- At room temperature and 1 atm CO, is the late recovery consistent with a single solvent-rebinding exponential, or is a more complex model justified?
- After accounting for spectral calibration, detector normalization, the measured instrument response, and preparation-to-preparation variation, are recovery kinetics distinguishable between the two conformer-associated bands?

### 2.2 Prespecified hypotheses

- **H1, equilibrium spectrum:** two bound-CO features will occur near 1905 and 1934 cm⁻¹. Their exact centers, widths, and area fractions are fitted results, not acceptance targets. Holzbaur et al. reported pH-dependent features at 1905 and 1934 cm⁻¹ ([article and DOI](https://pubs.acs.org/doi/10.1021/ja953715o)); earlier HRP-C work reported 1905 and 1933.5 cm⁻¹ ([DOI](https://doi.org/10.1016/0014-5793(83)80840-0)).
- **H2, photolysis sign:** at a bound-CO peak, the first resolvable pump-induced signal will be a bleach, ΔA < 0 under the definition in §14.1. A free-CO feature near 2137 cm⁻¹ is scientifically useful but is outside the selected two-band MVP unless the installed MIRcat range and transmission permit it; it is optional, not required.
- **H3, room-temperature recovery:** the late recovery will be tested first against a single exponential. Doster et al. found a solvent process of approximately 1 s⁻¹ at 300 K and 1 atm CO, but that value is a planning anchor only; the run cadence is set from the measured sample-specific recovery ([direct PDF](https://wolfgang-doster.de/Gesamtfolder/jmb87hrp.pdf)).
- **H4, conformer kinetics:** the null model is a shared late recovery rate for the 1905 and 1934 cm⁻¹ channels. Separate rates are reported only if the prespecified model comparison and uncertainty criteria support them. The notebook’s claim that the rates are indistinguishable is a hypothesis to test, not an input fact.

### 2.3 Claims explicitly out of scope for the MVP

The MVP must not claim absolute photolysis quantum yield, pulse-to-pulse energy distribution, peak power, multiphoton order, sub-100 ns geminate dynamics, structural assignments beyond the cited band/conformer association, microscopic CO-entry pathways, or a universal HRP rate constant. It must not treat a commercial Type II or Type VI-A mixture as identical to purified HRP-C. It must not infer analyte absorbance from equality of the sample and reference optical arms.

### 2.4 Intended thesis claims and alternative explanations

If every applicable gate passes, the minimum defensible thesis claim is:

> A verified native HRP-C(FeII)–CO preparation at pH 6.00 exhibits two calibrated mid-IR bound-CO bands consistent with the established HRP-C conformer-associated features, permanent-iris 540 nm OPO excitation produces a negative bound-CO difference signal, and the platform measures a reproducible room-temperature recovery envelope under a quantified low-duty exposure and dual-detector normalization.

A second claim—that the two bands share or differ in their recovery kinetics—is conditional on preparation-level precision and the prespecified shared-versus-separate model comparison. A microscopic pocket-to-solvent claim is conditional on the optional fast branch.

| Observation | Intended explanation | Alternatives that must be tested or bounded |
|---|---|---|
| Two equilibrium peaks | Two HRP-C(FeII)–CO conformer-associated ν(CO) bands | Isoenzyme mixture; pH error; H₂O/D₂O substitution; substrate/contaminant binding; calibration error; etalon/fringe; line-shape overfit |
| Pump-induced negative ΔA at a peak | CO photodissociation | Pump scatter; detector recovery; electrical pickup; heating/refractive-index change; irreversible heme photochemistry; cell motion |
| Positive-going recovery to baseline | CO rebinding | Instrument/filter relaxation; sample/reference drift; diffusion or illuminated-volume exchange; oxidation; cumulative damage |
| Different apparent rates at 1905 and 1934 cm⁻¹ | Conformer-dependent kinetics | Unequal SNR; spectral overlap; axis drift; wavelength-dependent detector latency/balance; sequential-scan filter memory |
| Rate changes with pump cadence | Repeated-pulse accumulation or incomplete recovery | Laser output drift; sample heating; pulse-selection error; sample depletion/damage |

The controls in §6 and sensitivity analyses in §14 must address these alternatives before the intended explanation is used.

## 3. Exact chemical system and materials identity

### 3.1 Required identities

| Item | Required identity and record | Acceptance rule |
|---|---|---|
| Protein | Native, glycosylated *Armoracia rusticana* peroxidase isoenzyme C; EC 1.11.1.7 | Supplier, catalog, lot, receipt date, storage history, and certificate are recorded. If purified in-house from a commercial mixture, the source lot and purification protocol/version are recorded and identity is demonstrated by an isoenzyme-resolving method. “HRP” alone is insufficient. |
| Purity | RZ = A403/A275 measured on the ferric starting material; activity by an approved assay on a sacrificial aliquot | RZ and activity are descriptive lot checks and are not substitutes for isoenzyme identity. Doster et al. used HRP-C with RZ 3.2; the proposed CH00 acceptance interval must be frozen before preparation. |
| Buffer | Sodium phosphate, 0.100 M total phosphate, pH 6.00 at the recorded preparation temperature | Reagent manufacturer, catalog, lot, water grade, calculation, actual mass/volume, calibrated pH-meter ID, electrode ID, temperature, and final measured pH are recorded. |
| Reductant | Sodium dithionite, Na₂S₂O₄, fresh anaerobic stock | Manufacturer, catalog, lot, assay if supplied, stock preparation time, solvent, calculated concentration, and addition time are recorded. The stock is not reused across days. |
| Ligand gas | Carbon monoxide, research grade, nominal 99.99% or the locally approved available grade | Cylinder ID, supplier, lot/batch if provided, nominal purity, regulator ID, manifold ID, connection time, pressure, and approved gas SOP ID are recorded. The nominal grade remains a CH00 procurement decision until EHS review. |
| Cell | Demountable gas-tight transmission cell, CaF₂ windows, 25 µm PTFE spacer, chemically compatible seals | Window IDs, spacer ID and measured thickness with uncertainty, aperture, seal material, assembled leak-test result, orientation, fill volume, and cleaning history are recorded. |

Commercial Sigma Type VI-A P6782 is a possible feedstock, not a defined HRP-C final material: its published RZ range is 2.5–4.0 and it is sold as HRP rather than an isolated C isoenzyme ([manufacturer product sheet, direct PDF](https://b2b.sigmaaldrich.com/deepweb/assets/sigmaaldrich/product/documents/223/099/p6782dat-mk.pdf)). Shannon et al. established that horseradish contains multiple separable isozymes ([PubMed record](https://pubmed.ncbi.nlm.nih.gov/5946638/)). The final sample must therefore carry an isoenzyme-C identity claim supported by a source certificate or an approved separation/identity record.

### 3.2 Selected starting composition

The nominal final composition is:

- HRP-C: 3.00 mM;
- sodium phosphate: 0.100 M;
- pH: 6.00 in H₂O at the recorded room temperature;
- sodium dithionite: 30.0 mM added as 10.0 molar equivalents relative to HRP-C;
- CO headspace: 1.00 atm partial pressure after equilibration;
- optical path: 25 µm;
- measurement temperature: campaign-measured room temperature, with a proposed CH00 set point of 298.15 K if active control exists; otherwise temperature is observational and must not be called controlled.

The first five numerical values are literature-anchored by Doster et al., except that 3.00 mM and 25 µm select the low end and midpoint, respectively, of their reported ranges. The temperature-control status is campaign-resolved. At 298.15 K, the Henry solubility coefficient compiled by Sander is approximately 9.7 × 10⁻⁶ mol m⁻³ Pa⁻¹, corresponding to about 0.98 mM dissolved CO at 1 atm in pure water; this is a calculated planning value and is not a direct measurement in phosphate/protein solution ([Sander, direct PDF](https://www.atmos-chem-phys.net/15/4399/2015/acp-15-4399-2015.pdf)). The analysis must use measured pressure and temperature and propagate the literature coefficient uncertainty/model limitation; it must not label the dissolved CO concentration exact.

H₂O is selected for the MVP because the central published bands are established in aqueous samples and replacing H₂O with D₂O shifts both bands. D₂O/pD is therefore a separate isotope experiment, not an interchangeable solvent. No glycerol is included: Doster et al. used 70% glycerol for cryogenic samples, whereas the MVP is room-temperature aqueous kinetics.

### 3.3 Storage, thawing, ionic strength, and usable lifetime

The as-received protein is stored exactly as specified by the source certificate/product label, in darkness and with a logged temperature history. A supplier storage temperature is not generalized to a differently purified HRP-C preparation. Lyophilized material remains sealed and dry until a preparation is authorized. If the source is supplied frozen or an approved concentrated stock is aliquoted, use single-use aliquots; refreezing or pooling thawed aliquots is prohibited until a dedicated stability study demonstrates equivalence.

Record container-open time, reconstitution time, time at room temperature, reduction time, CO-loading time, cell-closure time, first/last spectrum, and disposal time. The usable lifetime is the shorter of the source instruction and the CH00 stability interval established by repeated UV–visible/IR checks; it is not “same day” by assumption. A sample that exceeds the interval may be analyzed as a stability observation but not pooled with accepted kinetics.

No salt is added beyond the declared sodium-phosphate formulation. Record the exact acid/base species and amounts and calculate ionic strength from the actual formulation, including dithionite and its counterions. “0.10 M phosphate” is not itself a complete ionic-strength value. Any added salt, cryoprotectant, substrate, surfactant, or preservative defines a new chemical condition.

## 4. Sample preparation, O₂ exclusion, CO loading, and verification

Only trained personnel working under an approved site-specific CO/compressed-gas SOP may execute this section. The sequence below is a requirements specification for that SOP.

### 4.1 Pre-preparation records and release

Before opening reagents, assign `sample_id`, `protein_lot_id`, `buffer_lot_id`, `reductant_lot_id`, `gas_cylinder_id`, `cell_id`, and `preparation_id`. Record operator, UTC start time, calculation sheet/version, intended final volume, cell fill volume, and waste route. Confirm the fume hood/manifold is released for CO, the fixed or portable CO monitor passed its required bump/function check, the regulator and tubing are CO-rated, the cylinder is secured, exhaust is operating, and a second trained person is available if the local SOP requires one.

### 4.2 Ferric stock

Prepare HRP-C in 0.100 M sodium phosphate, pH 6.00. Determine concentration on a sacrificial diluted aliquot from A403 using the promoted lot-specific or literature-backed ferric extinction coefficient; the Merck technical record gives ε403 = 100 mM⁻¹ cm⁻¹ for native HRP as a generic reference, but isoenzyme- and state-specific analysis must be frozen in CH00 ([manufacturer technical note](https://www.merckmillipore.com/TD/en/technical-documents/technical-article/protein-biology/enzyme-activity-assays/peroxidase-enzymes)). Record the full 250–700 nm spectrum, path length, dilution, blank, extinction coefficient source, and propagated concentration uncertainty. Measure and record RZ. Do not return the aliquot to the stock.

### 4.3 Oxygen exclusion and reduction

1. Assemble and leak-test the closed gas path with inert gas before introducing CO. Record the leak-test method and result.
2. Deoxygenate buffer and protein using the EHS-approved manifold or glovebox method. The acceptable residual-O₂ criterion and sensor method are CH00 dependencies; absence of visible bubbles is not evidence of anaerobiosis.
3. Prepare fresh anaerobic sodium dithionite stock immediately before use. Add sufficient stock to give 10.0 molar equivalents relative to HRP-C while maintaining the final 3.00 mM protein and 0.100 M phosphate composition.
4. Mix without aeration. Record actual volumes, times, temperature, and any color change.
5. On a sacrificial aliquot, confirm conversion from ferric HRP (approximately 403 nm Soret) toward ferrous HRP (reported near 437 nm) before CO addition. The exact acceptance spectrum and tolerance must be established by a reference preparation in CH00.

Doster et al. prepared ferroperoxidase by anaerobic addition of a 10-fold molar excess of dithionite in 0.1 M phosphate ([direct PDF](https://wolfgang-doster.de/Gesamtfolder/jmb87hrp.pdf)). Sodium dithionite is self-heating and harmful if swallowed and can generate hazardous decomposition products; the current supplier SDS and local chemical hygiene plan control handling and disposal ([MilliporeSigma SDS](https://www.sigmaaldrich.com/US/en/sds/saj/28-2930)).

### 4.4 CO loading and sealed-cell filling

1. With the system closed and exhausted, replace the inert headspace with CO using the locally approved number of exchange cycles or continuous equilibration method. The exact cycle count, flow, and duration are not fixed here because they must be validated for the actual vessel/manifold volume and promoted as `CO_LOAD_METHOD_VERSION`.
2. Equilibrate the reduced solution against 1.00 atm CO partial pressure at the recorded room temperature. Record absolute/barometric pressure method and uncertainty. Do not infer 1.00 atm from regulator gauge pressure alone.
3. Confirm the HRP-C(FeII)–CO optical spectrum on a sacrificial aliquot. A conforming reference is expected to show a Soret maximum near 423 nm and Q bands near 541 and 572–575 nm; exact centers and ratios are reference-preparation results, not hard-coded tolerances. Klapper and Hackett reported 423, 541, and 572 nm for ferrous HRP–CO, Doster et al. monitored 400–440 nm, and later work provides the structural/spectroscopic context ([Klapper and Hackett](https://pubmed.ncbi.nlm.nih.gov/14109214/), [Doster et al.](https://wolfgang-doster.de/Gesamtfolder/jmb87hrp.pdf), [Carlsson et al.](https://pubs.acs.org/doi/10.1021/bi0483211)).
4. Fill the gas-tight CaF₂ cell completely, with no intentional headspace and without introducing bubbles. Record fill order, visible bubble check, mass-before/mass-after if the approved cell method supports it, and closure time. A bubble, unfilled aperture, leak, cracked/chipped window, or uncertain seal is an abort. CO equilibration occurs in the preparation vessel; the analytical cell is not used as an unquantified gas–liquid equilibration vessel.
5. Keep the cell dark or under validated safelight conditions until the dark spectrum is recorded. Place the assembled cell in secondary containment for transport.

### 4.5 State verification at the instrument

Before pump exposure, acquire:

- a UV–visible spectrum from a matched sacrificial preparation or compatible inline/parallel cell;
- a QCL dark spectrum over the promoted HRP window;
- a buffer + dithionite + CO blank in the same cell design;
- sample/reference detector dark and illuminated baselines;
- an unpumped stability time series at least as long as the planned acquisition block, with duration frozen in CH00 from AR01/PF01.

The sample is released only if the bound-CO IR band pattern is present, the detector channels are within their promoted linear ranges, the sample/reference ratio is stationary by the CH00 drift criterion, and the before/after UV–visible state comparison shows no oxygenated/ferric contamination beyond the CH00 reference envelope.

CH00 must turn “reference envelope” into a reproducible calculation. Build the envelope from independently prepared accepted reference samples and include at least Soret/Q-band centers and normalized amplitudes, RZ/start concentration, IR band centers/areas, baseline slope, and time-dependent drift. Accept a candidate only when its measurement lies inside the predeclared multivariate prediction region after combining candidate and reference uncertainty, with no individual detector/saturation/leak/bubble failure. Freeze the confidence level, reference sample count, preprocessing, and outlier policy before testing the MVP samples. A failed candidate is assigned a rejection reason and retained; limits are not widened after seeing its result.

Post-acquisition integrity uses paired before/after differences and the same uncertainty framework. Reject subsequent kinetic events from a sample state at the first statistically supported irreversible change, loss of recovery, or dose trend under the CH00 rule. Earlier events remain analyzable only if their event-index/dose range passed the prespecified changepoint and integrity checks.

## 5. Cell, optical geometry, and state preservation

The selected cell is a sealed demountable CaF₂ transmission cell with a 25 µm PTFE spacer. Doster et al. used CaF₂ windows and 10–50 µm spacers for 3–8 mM HRP IR measurements ([direct PDF](https://wolfgang-doster.de/Gesamtfolder/jmb87hrp.pdf)). The 25 µm choice must be verified during a non-pumped path-length pilot: the 1905/1934 cm⁻¹ region must retain adequate probe transmission, avoid detector saturation, and yield both peak and baseline measurements above the promoted platform sensitivity. If it fails, a different value inside the cited 10–50 µm range may be selected only through CH00 and recorded as a new configuration.

Determine nominal illuminated-chamber volume from the measured wetted aperture and spacer thickness and, if compatible with the approved assembly, verify fill volume gravimetrically with a matched liquid. Report both value and uncertainty. Do not borrow a catalog volume for a spacer/aperture assembly. The static MVP has no mixing, injection, flow, translation, or sample refresh after closure; the optical pump is the sole kinetic initiation. Any flow/translation design is a later configuration requiring residence-time, exchange-volume, pressure, leak, synchronization, and cross-contamination characterization.

The optical configuration record must include cell face normal, window orientation, spacer aperture, beam positions, pump and probe spot metrics at the sample plane, crossing angle, polarization states if controlled, and photographs/diagrams sufficient to reproduce placement. The pump spot must encompass the analyzed probe region with a characterized overlap margin; the required margin is set by OG01/OV01, not visual judgment. At least three independent remove/replace placements and one realignment are required by OV01 before overlap uncertainty can be promoted.

The cell must remain sealed throughout a block. Opening, topping up, changing the headspace, or reusing a previously illuminated sample creates a new `sample_state_id` and normally a new acquisition block. Temperature and relative humidity sensors are observational unless their calibration status supports a quantitative environmental claim.

## 6. Control matrix

Each control receives its own `sample_id`, preparation record, and acquisition block. Controls are processed identically except for the named factor.

| Control | Purpose | MVP status |
|---|---|---|
| Buffer + dithionite + CO, no protein | Cell, solvent, reductant, free-CO, and pump/probe artifacts | Required |
| HRP-C(FeIII) in buffer under CO, no dithionite | Demonstrate that the assigned bound-CO bands require the ferrous state | Required |
| HRP-C(FeII) under inert gas, no CO | Distinguish ferrous-protein/pump artifacts from CO-bound response | Required; prepare only under an approved anaerobic SOP |
| HRP-C(FeII)–CO, probe only/no pump | Dark stability, probe-induced change, baseline drift | Required and interleaved |
| HRP-C(FeII)–CO, pump commanded but physically blocked | Electrical pickup, timing feedthrough, scattered light | Required and interleaved |
| HRP-C(FeII)–CO, probe off/pump on | Pump scatter and detector recovery artifact | Required during commissioning, then per configuration |
| Off-band QCL channel | Broad thermal/photophysical background | Required if a suitable transmitted off-band point exists in the promoted module range; otherwise unresolved dependency |
| Recovered vs fresh aliquot | Detect irreversible photochemistry or state loss | Required |
| BHA-bound HRP-C(FeII)–CO | Positive mechanistic control expected to favor a single CO conformer | Optional follow-on, not MVP |
| Isotopically labeled CO | Band-assignment control | Optional follow-on; requires separate gas and safety approvals |

A “no effect” control is interpretable only when its uncertainty is reported and the platform sensitivity is sufficient to exclude the prespecified effect size. Controls may not be pooled across configurations, sample preparations, or calibration bundles without a justified hierarchical model.

## 7. Platform authority, fixed wiring, and unresolved capability

The repository’s current wiring authority is `hardware_configuration.yaml` and its associated wiring map. The required signal topology is:

- T660-2 channel A → HF2LI external reference;
- T660-2 channel B → MIRcat trigger input;
- T660-2 channel C → HF2LI DIO acquisition marker;
- T660-2 channel D → T660-1 external trigger;
- T660-1 channel A → Surelite FIRE, external connector pin 7;
- T660-1 channel B → Surelite Q-SWITCH, external connector pin 6;
- T660-1 channel C → MIRcat process input, DB9 pin 4, active low;
- VIGO sample detector → HF2LI signal input 1;
- VIGO reference detector → HF2LI signal input 2;
- MIRcat direction/sweep/wavelength outputs → HF2LI DIO20/DIO21/DIO22 when those mappings are promoted.

This list describes intended identity, not proof of timing or polarity. Physical cable length is provenance, not a delay calibration.

The present experiment-builder capability registry limits MIRcat wavenumber to 1800 cm⁻¹, below both target HRP-C–CO bands. It also marks external process triggering and relevant DIO capabilities unavailable. Therefore no biological plan may be compiled until QB01 demonstrates the installed module’s accessible range around 1905/1934 cm⁻¹, the capability registry is updated and tested, MD01/MSW01 establish the trigger/status behavior actually used, and a dry-run plan passes. A configuration-file edit alone is not evidence of optical capability.

The successful return of the current experiment engine does not automatically prove safe restoration. Every normal completion, abort, exception, and operator stop must explicitly apply the safe-idle state and verify readback. `TRIGger:SHOTs n` on the T660 clears the shot counter; it does not limit emitted shots. It must never be used as a finite-exposure control.

## 8. Calibration and characterization dependency map

### 8.1 Minimum promoted calibration bundle

The biological run requires a single promoted calibration bundle containing, at minimum:

| Dependency | Required result used by this experiment |
|---|---|
| MS-01/MS-02 | PicoScope channel/path correction plus timebase/threshold/model uncertainty for optical/electrical timing capture |
| T2-01/T1-01 | Retained T660-2 and T660-1 electrical route fits/closure with reference planes and uncertainty; import only through the promoted bundle |
| PT-01 | MIRcat process-trigger electrical path polarity timing and uncertainty |
| MC-01 | Verified MIRcat GUI process-trigger behavior and safe stop |
| TR-01 | Installed replacement reference-detector identity and resource mapping |
| OM-01 | Bounded power-meter working-reference identity, range, zero, stability, uncertainty, and device IDs; its pre-iris mixed-output observation is historical evidence, not HRP dose |
| WM-01 | Qualified Coherent WaveMaster identity, cable/adapter, RS-232 behavior, air-nanometre pulsed configuration, native response states, 540 nm repeatability, uncertainty, validity, and explicit exclusion from spectral-power-fraction assignment |
| ATT-01 | Qualified electronic-iris USB/API control and faults; permanent far-field X/Y/Z mount; accepted 540 nm diameter/tolerance; residual-contamination and core-clipping bounds; post-iris sample-plane transfer; optical splitter transfer for both sample and reference arms; no assumed 50/50 split |
| HF-01/HF-02 | HF2LI routing, external reference, demodulator/stream integrity, timestamps, dropped-sample behavior |
| MD-01/MSW-01 | MIRcat DB9 mapping and only the point-tuning/trigger behavior used by the approved plan |
| DET-01/02/03/04 | Dark behavior; gain/linearity/saturation/SNR; latency; wavelength-dependent optical/detector/system balance and normalization |
| SP-01/SP-02 | Reference features and spectral-axis mapping/uncertainty spanning the HRP window |
| OP-01 | Optical sample-plane timing for the selected permanent-iris OPO-540 and MIRcat paths, including jitter and latency; the static iris is configuration provenance, not a timing origin |
| CL-01 | Electrical-to-optical timing closure for the selected acquisition mode |
| FE-01 | Finite emitted-pump-event control with independent optical-event reconciliation and safe stop |
| E2E-01/RPT-01/PROM-01 | Non-biological end-to-end demonstration, reusable report, and explicit promotion |

Completed electrical measurements MS-01, MS-02, T2-01, and T1-01 are informative but not yet promoted. Their current campaign-local results—approximately 0.11 ns Pico channel skew, route-specific T660 delays, about 50.9 ns T660-1 trigger-to-Q-switch-command path, and the measured adapter delays—must not be copied into an experimental definition until the enclosing bundle is promoted. The current nominal 179.830 µs FIRE-to-Q-SWITCH value is explicitly uncalibrated, and the control UI’s 250 µs default is not experimental evidence.

### 8.2 Minimum promoted characterization bundle

| Phase | Required result |
|---|---|
| CH-00 | Frozen chemical, spectral, delay, power-ladder, acceptance, randomization, and analysis plan |
| ATT-01/PB-02 at 540 nm | ATT-01 performs the preliminary pre-iris delay search and qualifies the permanent iris; PB-02 performs the final locked-iris delay search and qualifies the post-iris 540 nm output, including WM-01-linked wavelength/status evidence, independently measured residual spectral content, post-iris average power, verified repetition, stability, pulse-duration bound, X/Y centroid/profile, and aperture margin. Supplemental PB-01 direct-355 measurement is not a biological-path gate. |
| QB-01 in the HRP grid | MIRcat accessibility and stable point operation across the actual HRP window and off-band point; pulse/repetition operating envelope |
| SC-01 | Qualified gas-tight CaF2 cell/path and the applicable temperature state without protein or CO |
| OG-01 | Sample-plane pump/probe transfer, spot definitions, overlap area, and fluence/irradiance calculation inputs |
| OV-01 | Pump/probe overlap repeatability over ≥3 placements plus a realignment |
| AR-01 | Wavelength-settle, detector-settle, HF2 filter-settle, dwell, and direction-history behavior |
| SV-01/SV-02 | Frozen nonbiological spectral reference/correction and independent Mylar validation; the actual HRP-C–CO FTIR state reference is acquired in experiment phase R4 and never calibrates the instrument |
| IR-01 | Measured instrument response for each acquisition mode, including optical timing, detector response, digitizer, and any scan/filter history |
| PF-01 | Dark/baseline noise, NEA, detection limit convention, Allan behavior, common-mode rejection, artifacts, and minimum independent averaging |
| RP-01 | Repeatability on ≥3 days/configuration realizations |
| E2E-CH/RPT-CH/PROM-CH | Non-biological end-to-end run, report, repeatability, and promotion |

### 8.3 Characterization deliberately removed from the MVP

- Direct 355, 1064, and 532 nm sample-path characterization is not an MVP biological dependency. PB-01 is a supplemental post-promotion phase for direct-355 thesis/source evidence; residual 1064/532 nm observations are source-health and safety evidence, not biological pump authority.
- Broad OPO wavelength characterization is removed. PB-02, OG-01, OV-01, and IR-01 qualify only the permanent-iris 540 nm path. Because the OPO center walks in X/Y with wavelength, another OPO wavelength requires a separately approved iris/centroid qualification rather than interpolation from 540 nm.
- A broad MIRcat 1650–2050 cm⁻¹ sweep is removed. QB01/MSW01 need only validate the installed module and point-tuning behavior covering the approved HRP band/baseline/off-band grid. The current broad sweep candidate is not approved.
- Polymer spectra do not calibrate a biological sample. Polystyrene is used only to freeze the spectral-axis fit; Mylar is an independent validation material. Neither substitutes for HRP-C state verification.
- Peak-power characterization and pulse-energy distribution are removed because there is no energy meter. Only average power, verified repetition rate, their uncertainties, and derived mean pulse energy are permitted.

## 9. Clock model, trigger model, and exposure control

### 9.1 Time definitions

- `t_master`: accepted T660-2 trigger initiating the platform timing sequence.
- `t_probe_elec`: T660-2 MIRcat trigger edge at the calibrated observation point.
- `t_probe_sample`: center or other promoted fiducial of the measured MIRcat optical pulse at the sample plane.
- `t_fire_cmd`: Surelite FIRE command at the PCU connector.
- `t_q_cmd`: Surelite external Q-SWITCH command at the PCU connector, when DAT Mode 2 is used.
- `t_pump_sample`: promoted optical fiducial of the post-iris 540 nm pulse at the sample plane.
- `t_chem = 0`: `t_pump_sample`, not an electrical command.
- `delay = t_probe_sample − t_pump_sample` for point-delay measurements.

All reported chemical time is derived from optical fiducials and the promoted OP-01/CL-01 model. The Surelite manual states that DAT Mode 1 accepts one negative 5 V→0 V, 10 µs FIRE pulse, has approximately 180 µs lead time, and ±10 ns optical jitter. DAT Mode 2 uses separate negative 10 µs FIRE and Q-SWITCH commands, with Q-SWITCH approximately 170 ns before lasing and specified ±1 ns jitter. These are manufacturer anchors, not installed-system calibration ([local Surelite manual](../../references/manuals/YAG/Surelite%20NdYAG%20Laser%20Manual.pdf), pp. 44–46).

### 9.2 Candidate master architecture and selection test

The preferred MVP candidate uses T660-2 as a 10 Hz master. On each accepted master trigger, T660-2 A produces the HF2 external-reference edge, B triggers one MIRcat probe pulse, C produces the acquisition marker, and D triggers T660-1. The 10 Hz candidate is inherited from the qualified Surelite cadence and gives 100 ms probe sampling, which is appropriate for the literature-scale ~1 s⁻¹ late recovery. It becomes operational only if QB01/PF01 show that a 10 Hz externally triggered MIRcat probe has adequate stability and sensitivity.

If 10 Hz probe SNR is inadequate, the allowed fallback is a high-rate MIRcat carrier—2 MHz is only the current alignment candidate—combined with independently time-stamped rare pump events. The fallback requires a promoted clock-bridge/timestamp test proving the relative HF2, Pico, T660, and pump-observation timelines over the full recovery record. It may not assume that independently started computer streams share time zero.

The architecture-selection E2E test must compare both candidates, where physically available, on a non-biological stable absorber. Select the lowest probe duty/rate that meets the CH00 precision and temporal-resolution targets without detector saturation or source instability. Record master source, synthesizer/readback rate, predivider/burst state, missed/rate-error flags, and verified optical probe rate. The selected architecture becomes a distinct `configuration_id`; data from the two architectures are not pooled without a bridge study.

### 9.3 Laser thermal cadence versus sample pump cadence

The Surelite flashlamps and OPO drive must run at their installed qualified cadence; the laser manual warns that changing lamp frequency changes thermal lensing, and the OPO output must not be assumed stable under an unqualified drive cadence. The proposed MVP keeps the qualified source cadence and reduces *post-iris 540 nm events transmitted to the sample* to a recovery-compatible cadence. The permitted implementation must be selected and proven in ATT-01/PB-02/OP-01/FE-01 from one of the following:

1. a validated Surelite pulse-division mode that maintains 10 Hz lamp operation while emitting the optically verified selected fraction of Q-switched pulses;
2. a validated, interlocked external pulse picker/shutter downstream of the OPO that blocks unwanted 540 nm pulses while the Surelite/OPO operates at its qualified cadence; or
3. another EHS- and manufacturer-approved topology that independently preserves lamp cadence and limits sample exposure.

The present two-T660 wiring and global predivider/burst behavior do not by themselves prove independent 10 Hz FIRE and rare Q-SWITCH control. `TRIGger:SHOTs` is only a counter reset. This is a blocking exposure-control dependency.

The candidate implementations are mutually exclusive and must have separate configuration IDs. If Surelite pulse division is used, ATT-01/PB-02/OP-01 must establish that the resulting 540 nm OPO output remains inside its promoted stability envelope; T660-1 B remains disabled unless the manufacturer-approved topology explicitly requires it. If an external optical pulse picker is used, DAT Mode 2 may run FIRE and Q-SWITCH at the qualified cadence while the interlocked picker admits only selected, independently observed post-iris 540 nm pulses to the sample. Sending external Q-SWITCH commands every cycle while assuming the PCU divider suppresses them is prohibited unless directly validated. The iris remains static and is never used as the pulse picker, event limiter, or safety shutter.

For commissioning only, use a proposed starting sample pump cadence of 10/99 Hz ≈ 0.101 Hz if—and only if—the installed Surelite pulse-division behavior is verified optically at the sample plane. This value is a campaign-resolved candidate tied to the manual’s 10 Hz laser cadence and P01–P99 divider range. Every actual pump event must be detected by an independent optical pickoff or validated pump monitor; command counts are not emitted-shot counts.

After measuring the late recovery rate `k_rec`, require

`f_pump ≤ k_rec / [-ln(1 − R_target)]`,

where `R_target` is the recovered fraction frozen in CH00. For the proposed `R_target = 0.99`, `f_pump ≤ k_rec/4.605`; Doster’s approximate 1 s⁻¹ planning value implies ≤0.217 Hz, demonstrating why 10 Hz sample pumping is unacceptable. This formula and decision must be re-evaluated using the lower confidence bound on `k_rec`, not its point estimate. Alternatively, validated sample refresh may establish independence, but a static sealed cell is the MVP and no refresh/flow assumption is allowed.

### 9.4 Finite-exposure enforcement

Before unblocking the pump, the control system must know the approved maximum emitted events for the block. It must increment that count only from the independent pump observation. On reaching the limit, loss of the observation signal, mismatch between commands and observed events, exception, or operator abort, it must close/block the pump, disable MIRcat emission, stop both T660s, and apply safe idle. The run must prove the normal-completion path also restores safe idle and records readbacks.

### 9.5 T660 channel requirements

All final delays and receiver levels come from promoted calibration/readback. This table fixes roles and selection rules, not unmeasured values.

| Channel | Required edge/width | Termination and level | Delay/interaction rule |
|---|---|---|---|
| T660-2 A → HF2 DIO0 | Positive reference edge; width long enough for reliable DIO capture and shorter than the master period | Start from documented 50 Ω source only after HF01 verifies delivered logic at the receiver | Defines probe reference phase; relative delay to B comes from HF01/QB01/CL01 |
| T660-2 B → MIRcat TRIG IN | Positive rising edge meeting the installed MIRcat trigger input; optical width is MIRcat-set in External Trigger mode | Verify delivered high/low and absence of double termination in MD01 | One accepted edge must map to one optical pulse; a missed/double pulse aborts the block |
| T660-2 C → HF2 DIO1 | Positive acquisition marker | Verify in HF01/MD01 | Must mark the accepted analysis window without coupling into detector channels |
| T660-2 D → T660-1 TRIG IN | Positive edge; documented alignment candidate used 10 µs | Verify T660-1 threshold, polarity, 50 Ω/HIZ choice, and delivered amplitude in T2/CL | Must not retrigger T660-1 while busy; any rate-error flag aborts |
| T660-1 A → Surelite FIRE | Negative 5 V→0 V command, 10 µs manufacturer value | Documented candidate is 50 Ω; verify delivered receiver voltage with laser inhibited | FIRE precedes optical pump by the OP01 result; preserve qualified lamp cadence |
| T660-1 B → Surelite Q-SWITCH | Negative 5 V→0 V command, 10 µs manufacturer value when DAT Mode 2 is used | Same installed-receiver verification | FIRE-to-Q command is the promoted optical optimum; nominal 179.830 µs and UI 250 µs default are not authority |
| T660-1 C → MIRcat DB9 pin 4 | Active-low process command; manufacturer correspondence permits 1–100 ms, with 10 ms candidate | Verify DB9 voltage/ground in MD01 | Used only for an approved discrete process step; never as a substitute for B external trigger |
| T660-1 D | Disabled and disconnected | Safe-idle state | Any activity is a fault |

The safe-idle baseline has both trigger sources OFF, predivider 1, burst disabled, gate mode 0, frames off, all outputs disabled, and force-EOD applied. Disabled-channel widths/polarities in `instrument/recipes/safe_idle.yaml` define a deterministic inactive state, not active experimental pulse settings. Stage any active configuration while triggers are OFF, read it back, verify receiver waveforms with sources inhibited, then arm in the ordered workflow below.

### 9.6 MIRcat, detector, PicoScope, and HF2 parameter algorithms

**MIRcat.** Use External Trigger mode, not External Pulse mode, unless QB01 specifically validates a different mode. Final probe width, current, repetition rate, module, and trigger-to-optical latency come from QB01/DET02/DET03/IR01. The current 150 ns, 2 MHz, 1850 cm⁻¹ alignment values are not biological settings. At each wavelength, accept data only after commanded/actual wavenumber, module, emission, process state, and AR01 settle gate pass.

**Detectors and splitter.** Record exact sample/reference detector and SIP identities, gains, coupling, bandwidths, cables, ranges, darks, overload flags, and temperature/status readbacks. DET03 supplies individual latencies and relative delay; DET04 supplies wavelength-dependent `B_opt`, `B_det`, and `B_sys`. Analysis may interpolate only inside the promoted table and uncertainty envelope. Extrapolation or an assumed 50/50 splitter is prohibited.

**PicoScope.** Use serial 10261. Enable only needed channels; select the highest vertical resolution whose returned sampling interval and analog bandwidth resolve the fastest IR01/DET03 feature used in the claim. Range each channel below clipping with the CH00 headroom rule. The trigger source is the promoted DAQ/probe/pump marker appropriate to the mode, with source, threshold, hysteresis, polarity, coupling, impedance, and delay recorded. Choose pretrigger length to contain an artifact-free baseline outside the time-zero uncertainty/IRF support. Choose posttrigger length to include every latency/normalization window used. Save the API-returned interval, sample counts, overflow, segment, trigger, and rejected-capture records. Raw segments are retained; waveform averaging is derived. The MS campaign’s 8-bit, 10 V, 2 ns, 100000-sample, 1000-pretrigger setup is evidence for that electrical calibration only and is not a biological default.

**HF2LI.** Device `dev18500` uses sample input 1/demodulator 0 and reference input 2/demodulator 3, DIO0 external reference, and DIO1 acquisition marker, subject to HF01. Record input range, AC/DC coupling, differential/single-ended mode, 50 Ω state, oscillator/reference selection, harmonic, phase, filter order `n`, time constant `τ`, actual sample rate, enabled nodes, and lock state. The current order 4, τ = 1 ms, and 2 kSa/s preset is provisional. For an `n`-stage first-order low-pass, calculate the required fraction-settle time from

`1 − exp(−x) Σ[k=0…n−1] x^k/k! = F_settle`, with `t_settle = xτ`.

CH00 selects `F_settle` from the allowable settling bias; AR01 verifies the result including tuning, transport, and detector effects. Accepted dwell is at least the larger of measured source/detector settling and filter settling, plus the independent averaging interval. A range, reference, phase, order, time-constant, or wavelength change starts a new settling interval and configuration boundary.

For either Pico or HF2 averaging, estimate the independent-sample count from PF01 autocorrelation/Allan behavior, not the number of digitizer points. For target half-width `ε` and pilot standard deviation `s`, use the prespecified interval formula (for example `N = ceil[(z s/ε)²]` when its assumptions hold), then cap by recovery, stability, and exposure limits. If the required count exceeds the cap, the claim is underpowered; do not silently add correlated samples.

### 9.7 Ordered startup, arming, acquisition, stop, and failure workflow

1. **Administrative entry:** confirm phase gate, operator authorization, laser/CO SOPs, configuration and promoted bundle IDs, immutable plan, sample/control IDs, free storage, and emergency contacts. Confirm no concurrent controller owns a device.
2. **Safe start:** verify physical pump block/shutters closed, MIRcat emission off, OPO stopped/parked, iris ownership/readback safe and no OPO emission authorized, both T660s stopped, all channels disabled, and safe-idle readbacks recorded.
3. **Electronics:** power/connect the power meter, WaveMaster, detectors/SIPs, HF2, Pico, T660s, and controllers per manufacturer instructions. Wait their promoted warm-up/stability intervals; perform identity/version/interlock/error/readback checks.
4. **Surelite/OPO drive:** follow the manufacturer start sequence. The laser manual enforces approximately 20 minutes before shutter opening and calls for harmonic operation/stabilization before optimization; the ATT-01/PB-02 configuration supplies the exact approved warm-up and FIRE-to-Q-SWITCH delay. Keep the sample path blocked and verify separation and dumps for residual 1064/532 nm. Supplemental PB-01 direct-355 characterization is not an experiment-readiness gate.
5. **OPO, wavelength reference, and iris:** complete the manufacturer warm-up, crystal-heater, 355 nm pump, calibration-table, WM-01-qualified 540 nm measurement, output-port, residual-beam, and PB-02 stability confirmations. Retain the WaveMaster device/adapter/probe configuration, air-nanometre pulsed mode, autocalibration state, native time tag/value/status, and uncertainty. Acquire exclusive iris controller ownership; verify the permanent mount/fiducials, configuration ID, commanded/read-back diameter, tolerance, aperture margin, and current ATT-01/PB-02 validity before any downstream arming. A wavelength/status failure, iris mismatch, communications loss, or moved mount blocks OPO emission and invokes revalidation.
6. **MIRcat:** initialize with emission disabled; confirm device/SDK/GUI identity, module/range, no errors/interlocks, safe current/pulse/rate settings, and external-trigger/process state. Do not tune through an unsafe/unvalidated range with the biological sample present.
7. **Alignment:** align and verify pump/probe/reference paths with the approved non-biological target or blank at the lowest qualified exposure. Confirm beam dumps, cell-plane spot/overlap, detector ranges, and absence of pump scatter. Do not use HRP-C as an alignment target.
8. **Sample installation:** with all emissions blocked/off, install the sealed cell, record orientation/position, inspect leak/bubble/window condition, and allow the CH00 equilibration interval. Acquire darks and unpumped state checks.
9. **Stage timing:** with triggers OFF, stage T660 channels and MIRcat/HF2/Pico settings; read back every value. Perform non-emitting electrical checks, force EOD if required, clear counters as counters only, and start logging before arming.
10. **Probe-only arm:** open only the probe path/emission under the approved low-duty condition. Verify one-to-one trigger/optical response, reference lock, detector linearity, baseline stability, and acquisition indexing. Failure returns to safe idle.
11. **Pump arm:** confirm event budget and recovery interval, enable independent pump observation, then open the final pump block/shutter only after a two-person/operator confirmation if required by the local SOP. Admit the planned event(s); count observed events, not commands.
12. **Acquisition:** execute the immutable randomized block, recording all native streams, commands, readbacks, exclusions, environment, power checks, and state anchors. A setting change creates a new acquisition/configuration boundary.
13. **Normal stop:** block pump first, stop/disable its commands, finish the required post-event recovery/state record, block/disable MIRcat, stop T660s, apply safe idle, verify readbacks/no optical events, and complete §15 restoration and gas closure.
14. **Failure/abort:** the first detected abort condition immediately blocks pump, inhibits emission and triggers, preserves already acquired native data/logs, applies safe idle, verifies the area/device state, executes the approved gas emergency response if relevant, and records the exception. Software cleanup is not allowed to delay a physical emergency action.

## 10. Steady-state QCL spectroscopy

### 10.1 Spectral grid

The final grid is set by SP02, QB01-HRP, DET02/04, the measured QCL linewidth, and the actual HRP-C reference spectrum. The literature planning window is 1885–1950 cm⁻¹ because it brackets the 1905 and 1934 cm⁻¹ bands and local baselines; this window may become operational only if the installed module covers it and CH00 approves it. No biological run may rely on the current builder maximum of 1800 cm⁻¹.

The proposed grid has two stages:

- reconnaissance: campaign-resolved step no larger than one-half the measured effective spectral resolution;
- final: denser points across each fitted feature and sparser local-baseline points, with exact values frozen in CH00.

The direction order must be balanced. At least one forward and one reverse realization per preparation is required so settling/backlash/direction artifacts can be detected. The system must wait the AR01-promoted wavelength-settle time and the HF2 filter-settle time before accepting data. The notebook’s generic 5 cm⁻¹ trigger candidate and a hard-coded 0.5 cm⁻¹ manufacturer comparison are not biological acceptance criteria.

At each grid point, acquire enough *independent* observations to meet the CH00 confidence-interval target using the PF01 variance/autocorrelation estimate and the averaging rule in §9.6. Report commanded and measured dwell, discarded settling portion, accepted averaging portion, number of native detector samples, effective independent count, and any pump/probe event count. The final spectral resolution is the convolution of QCL linewidth, axis uncertainty, sampling grid, and analysis line shape; it is not equal to step size.

Acquire the following order within every preparation unless the pre-generated balanced schedule specifies the mirror order: detector dark; matched cell/buffer background; HRP-C(FeII)–CO forward spectrum; repeated band-anchor point; reverse spectrum; repeated band-anchor point; end dark; end state spectrum. Randomize whether forward or reverse occurs first across preparations. Blank and sample records must share the same promoted optical configuration and be close enough in time to satisfy PF01 drift limits.

### 10.2 Acquisition sequence at each wavenumber

1. Confirm source state, wavelength/readback, process-active status, detector ranges, and no saturation.
2. Wait the promoted wavelength and detector settling intervals.
3. Acquire detector dark if scheduled by the block plan.
4. Acquire paired sample/reference background state and sample state with immutable timestamps and state codes.
5. Compute provisional normalized transmission only for live QC; retain native sample and reference streams.
6. Apply drift, saturation, dropout, and common-mode QC. Exclude only by a prespecified reason code; never delete native data.
7. Continue or safe-stop according to the phase gate.

The equilibrium absorbance definition is

`A(ν) = −log10[(V_s,S(ν)/V_r,S(ν)) / (V_s,B(ν)/V_r,B(ν))]`,

with wavelength-dependent DET04 corrections applied as a versioned analysis artifact. `B_opt`, `B_det`, and `B_sys` are measured quantities. Neither optical splitter balance nor detector responsivity equality is assumed.

### 10.3 Spectral acceptance and fit

Fit the two-band region with two candidate line-shape families frozen in CH00: Gaussian components with a shared or independent sloping local baseline, and a minimally more flexible Voigt alternative only if effective instrument linewidth warrants it. Report calibrated centers, widths, integrated areas, covariance, residuals, and sensitivity to baseline/window choice. Do not divide band areas into molecular populations unless relative integrated extinction strengths are externally supported or measured; otherwise call them **relative spectral area fractions**.

The spectrum passes state QC when both literature-associated features are detectable under the PF01 sensitivity definition, fitted centers agree with the reference FTIR within combined uncertainty, residuals show no structured failure under the CH00 rule, and beginning/end spectra agree within the photodamage criterion. Failure is scientifically reportable but blocks time-resolved interpretation as HRP-C(FeII)–CO.

## 11. Pump–probe and time-resolved acquisition

### 11.1 MVP mode: rare-pump recovery stream

This mode targets the room-temperature solvent-rebinding envelope from the instrument-resolved early time through full recovery.

1. Operate the MIRcat at a QB01-promoted point on one fitted bound-CO band, with sample/reference detectors in their DET02 linear ranges and HF2 referenced to the verified QCL carrier/trigger.
2. Stream sample, reference, pump-observation marker, MIRcat trigger/status, T660 markers, and environmental observations continuously.
3. Establish an unpumped pre-event baseline of duration determined by AR01/PF01 and frozen in CH00.
4. Admit exactly one optically observed post-iris 540 nm event to the sample.
5. Continue recording until the recovery criterion is met or the CH00 maximum observation interval is reached.
6. Wait the recovery-derived inter-event interval before another pump event.
7. Repeat at the other bound-CO band and the approved off-band point in randomized blocks.
8. Interleave pump-blocked events and fresh/recovered comparisons.

The HF2LI is used for carrier-selective sample/reference amplitude streams; the PicoScope captures pump/probe optical/electrical fiducials and detector pulse/waveform diagnostics at the promoted settings. If the HF2 filter obscures relevant kinetics, use the measured IR01 kernel and/or a promoted direct Pico detector-amplitude path. Do not deconvolve beyond the bandwidth supported by IR01 and PF01.

Between pumped scans/blocks, wait until the lower confidence bound on recovered fraction exceeds the CH00 target and acquire a pre-next-block anchor. Wavelength/source settling and chemical recovery run concurrently only if both are independently demonstrated complete; otherwise use the longer interval. A failed anchor forces a longer wait, a fresh sample/position under an approved refresh design, or abort—it is not baseline-corrected away.

### 11.2 Optional fast point-delay mode

This branch is forbidden until all of the following are true:

- DAT Mode 2 or an equivalent low-jitter pump path is installed and OP01/CL01-promoted;
- independent rare-pulse exposure control preserves the 10 Hz lamp cadence;
- the MIRcat can produce a stable, externally triggered probe pulse at the required delay and repetition behavior;
- the detector/Pico chain resolves the probe amplitude without relying on an HF2 time constant longer than the feature;
- IR01 demonstrates a response capable of supporting the proposed fastest delay;
- scan-order and sample-recovery independence are demonstrated.

The delay grid must be generated after IR01. It must contain negative delays, a dense region through the measured response, logarithmically or information-optimally spaced positive delays through the early and intermediate response, and late points connecting to the recovery stream. No nominal nanosecond grid is frozen in this brief because the optical timing and probe-pulse behavior are unpromoted.

Generate the grid by the following algorithm:

1. define IR01 support as the interval containing the CH00-selected fraction of the measured response and include the promoted time-zero uncertainty;
2. place negative-delay controls far enough before zero that the upper uncertainty bound on IRF contribution is below the PF01 detection criterion;
3. sample the rise/prompt region at an interval no larger than one-half the measured effective IRF FWHM, then test identifiability by convolved simulation;
4. extend positive delays on a logarithmic or Fisher-information-optimized grid through the pocket/escape candidates and into the MVP recovery interval;
5. extend the last delay until the lower confidence bound on recovered fraction exceeds the CH00 recovery target, using `t ≥ −ln(1 − R_target)/k_rec,lower` for a validated single exponential or the slower supported model otherwise;
6. include interleaved negative, near-zero pump-blocked, off-band, and late-recovery anchors in every delay block;
7. simulate all candidate models with the promoted IRF, PF01 covariance, event budget, and parameter priors; accept the grid only if required parameters are identifiable and the target precision is achievable without violating dose/recovery limits.

The accessible range is the intersection of T660 programmed/readback capability, MIRcat trigger behavior, detector/Pico/HF2 acquisition support, sample stability, and the promoted timing-validity envelope. The T660 manual’s broad delay range is not by itself an accessible chemical-time claim.

At each delay, acquire paired pump-blocked and pump-admitted observations under a randomized/block-balanced order. The primary transient definition is

`ΔA(ν,t) = −log10{[V_s,on(ν,t)/V_r,on(ν,t)] / [V_s,off(ν,t)/V_r,off(ν,t)]}`.

“On” and “off” must be adjacent or otherwise paired within the drift correlation time established by PF01. A commanded pump with no optical observation is not an on event.

### 11.3 Time-zero control and determination

Determine time zero from a non-biological prompt optical response at the actual sample reference plane, using the same pump/probe routes, cell-window geometry or validated correction, detectors, and capture configuration. OP01/CL01 must report the chosen optical fiducials, fixed offsets, adapter correction, relative detector delay, jitter distribution, drift, and combined uncertainty. Confirm time zero at the beginning and end of each day/configuration and after any moved optic, cable, cell holder, wavelength path, detector, adapter, trigger threshold, or timing setting.

The biological block contains pump-blocked near-zero captures and negative-delay captures. A signal that precedes the promoted zero beyond uncertainty, persists with the pump blocked, or moves when only electrical threshold changes is an artifact until proven otherwise. Commanded delay and cable length are retained as diagnostics but never relabeled optical delay.

### 11.4 Pump wavelength, duration, and selection workflow

For the MVP, select only the permanent-iris Horizon OPO output at independently verified 540 nm. Document the 355 nm pump configuration; warm-up and crystal-heater state; GUI/software/calibration-table identity; commanded wavelength; WaveMaster working-reference bundle and device/adapter/probe configuration; units, pulsed mode, autocalibration state, native time tag/value/status, and uncertainty; output port; bandwidth bound; residual spectral content from the accepted spectral/power method; pointing/overlap; X/Y centroid/profile and aperture margin; post-iris average power; effective repetition; pulse-duration bound; optical latency; electronic-iris device/service/configuration ID; locked-mount check; and commanded/read-back diameter. The Horizon `GoTo` value is not independent wavelength evidence, and a WaveMaster center wavelength is not a residual spectral-power fraction. The accepted diameter and mount remain unchanged through the HRP pilot and confirmatory acquisition; the iris is not optimized against biological response.

The 540 nm configuration is valid only inside the ATT-01/PB-02/OG-01/OV-01/IR-01 envelope. Another OPO wavelength requires a separately approved wavelength-specific iris/centroid qualification. Direct 532 nm is not a fallback within this MVP; adding it creates a new pump-path configuration and requires a prospective brief amendment and qualification.

## 12. Pump/probe power, exposure, recovery, and photodamage

There is no pulse-energy meter. For the final qualified configuration, record post-iris sample-plane total average power `P_total`, the residual off-wavelength fraction or upper bound `r_off`, and the assigned desired-wavelength power `P_540 = P_total(1-r_off)` through the ATT-01/PB-02/OG-01 chain using the OM-01-qualified meter. With independently verified sample-transmitted repetition rate `f`, report only derived mean 540 nm pulse energy

`E_mean,540 = P_540 / f`

with propagated covariance and uncertainty and an explicit statement that it is a mean. Do not report pulse-energy distribution or peak power. If only an upper bound on `r_off` is available, carry it as a one-sided dose uncertainty rather than treating total meter power as pure 540 nm power. The pre-iris OM-01 mixed-spectrum observation is not a dose input. Combine ATT-01, PB-02, OG-01, spot-area uncertainty, and overlap to derive mean incident fluence/irradiance. Retain the conservative absorbed-photon contribution of every detected residual band using its power fraction, photon energy, and HRP absorbance envelope; disregard it only when the predeclared uncertainty criterion demonstrates that it is negligible for the claimed comparison. Otherwise improve rejection or use a multiwavelength forward model.

The pump power ladder begins at the lowest ATT-01/PB-02/OG-01-promoted post-iris setting that gives a detectable signal and advances only through CH00-frozen settings. At each step:

1. acquire fresh pre-exposure spectrum and state checks;
2. record a fixed, optically counted number of pump events;
3. measure transient amplitude and recovery;
4. reacquire the equilibrium IR spectrum and available UV–visible state check;
5. examine buffer-only, pump-blocked, off-band, and fresh-aliquot controls;
6. stop escalation on the first photodamage, detector nonlinearity, thermal background, incomplete recovery, or non-proportionality flag.

CH00 must freeze numerical thresholds for acceptable irreversible spectral change, recovered fraction, signal linearity versus mean fluence, maximum events per spot/sample, and temperature change. Those numbers must be derived from PF01 uncertainty and a pilot dose-response, then promoted; they are deliberately not guessed here. The final operating point is the lowest setting that meets the prespecified precision target and remains inside the reversible linear regime.

Estimate the initial observable photolyzed fraction at each bound-CO band as `f_obs = −ΔA(0+)/A_bound` only after correcting for spectral overlap, incomplete spatial overlap, and IR01 blurring. Independently calculate a photon-balance expectation from the notebook:

`N_inc,540 = E_mean,540 λ_540/(hc)`

`N_abs,540 = N_inc,540 · (1 − 10^(−A_540)) · f_overlap`

`N_HRP,illum = c_HRP · V_illum · N_A`

`f_photon = min[1, Φ · N_abs,540/N_HRP,illum]`, with the residual-band contribution reported separately as a bounded correction or uncertainty term.

Pump absorbance, quantum yield `Φ`, illuminated volume, and overlap are measured inputs or explicitly cited priors with uncertainty; the cap at one is a physical bound, not evidence of saturation. Uniform concentration/overlap and single-path Beer absorption are model assumptions. The promoted operating target is selected from the pilot as the smallest `f_obs` that meets the CH00 precision criterion, remains proportional to derived mean fluence, gives the same normalized kinetics across adjacent lower-dose settings, and passes all integrity checks. No fixed percentage is adopted from a notebook placeholder.

Calculate a conservative per-event adiabatic temperature-rise screen,

`ΔT_ad = E_abs/(ρ C_p V_therm)`,

using cited buffer properties and a documented thermal volume model. Also measure any available sample temperature and off-band thermal response. The calculation cannot rule out local hot spots or replace the dose-linearity and post-state tests. Cumulative incident and absorbed energy are calculated from optically accepted events only and reported per sample and per illuminated location.

Photodamage indicators include permanent loss/shift/broadening of either CO band, failure of the 423/541/572–575 nm optical-state pattern, increased baseline/scatter, new bands, slower or incomplete recovery, dose-history dependence, visible bubble/precipitate, detector baseline change attributable to the sample, and disagreement between fresh and recovered aliquots. Any indicator triggers quarantine of that sample state and safe stop.

## 13. Replication, randomization, and statistical design

The independent experimental unit is an independently prepared and sealed HRP-C(FeII)–CO sample, not a laser shot. The minimum design uses at least three independent preparations made and measured on at least three days; this is a feasibility minimum, not an automatically powered confirmatory sample size. CH00 must state the precision target for band centers and `k_rec`, use PF01/pilot variance to calculate the required number of preparations, and revise upward if needed.

The plan must separately name and count:

- preparation replicates: independent reduction/CO-loading/cell-fill operations;
- sample/cell replicates: distinct sealed cells or aliquots from a preparation, when used to estimate fill/cell variation;
- spectral replicates: complete forward/reverse scans and repeated anchor points;
- delay replicates: independently recovered pump events at the same delay, not detector samples within one event;
- day/configuration replicates: fresh startup, placement, and readback realizations;
- raw detector samples: correlated time-series observations, never treated as independent preparations.

Within each preparation:

- randomize the order of the 1905-region, 1934-region, and off-band blocks subject to recovery and source-settling constraints;
- balance spectral sweep direction;
- interleave pump-blocked controls;
- randomize delay order within early/middle/late strata for point-delay mode rather than scanning monotonically;
- record preparation order, day, operator, cell placement, and configuration as blocking factors;
- distinguish technical repeats, emitted pump events, detector samples, and biological/preparation replicates.

Primary inference is across preparations. Use a hierarchical model with preparation/day random effects or a two-stage analysis that estimates each preparation first and combines estimates with their uncertainties. Report all preparation estimates, not only a pooled curve. Technical repeat count may improve within-preparation precision but cannot increase biological degrees of freedom.

## 14. Analysis, uncertainty, and notebook implementation

### 14.1 Required analysis stages

1. Validate data-contract structure, IDs, time ordering, byte sizes, and acquisition-index relationships.
2. Preserve native sample/reference streams and construct versioned corrected artifacts.
3. Apply DET04 wavelength-dependent balance and dark corrections.
4. Calculate equilibrium `A(ν)` and transient `ΔA(ν,t)` from paired ratios.
5. Apply spectral-axis mapping and uncertainty from SP02.
6. Fit equilibrium spectra and propagate center/width/area covariance.
7. Align time to the measured optical pump fiducial and apply OP01/CL01 uncertainty.
8. Model the measured instrument response; never substitute cable length or nominal electronic delay.
9. Fit kinetic candidate models and compare them under the prespecified rule.
10. Perform sensitivity analyses for baseline window, line shape, pairing window, exclusions, response kernel, filter history, and correlated calibration inputs.
11. Generate predicted-versus-measured tables and residual plots.
12. Produce preparation-level and combined estimates with confidence/credible intervals.

### 14.2 Kinetic models

For the MVP late recovery, compare:

- `M1: ΔA(t) = A0 exp(−k_rec t) + c`;
- `M2:` a two-state pocket/solvent model only if the measured time response and data span identify both components;
- a nonparametric/spline diagnostic used to expose model failure, not as the primary mechanistic claim.

For the optional fast branch, the notebook’s model is:

`dP/dt = −(k_gem + k_esc)P`

`dS/dt = k_esc P − k_on[CO]S`

with the unbound population proportional to `P + S`. Parameters are shared or band-specific only as prespecified. `k_on[CO]` may be treated as a pseudo-first-order recovery rate only when CO concentration is stable and its uncertainty is propagated. Compare the full model with a solvent-only exponential using AIC/AICc plus residual and identifiability diagnostics; an information criterion alone does not establish mechanism.

### 14.3 Instrument response and HF2 filtering

Use the empirical IR01 kernel for each mode. The HF2 demodulator is a causal cascaded low-pass system whose output depends on order, time constant, data rate, and acquisition history. During a sequential delay scan, that filter memory is not automatically equivalent to a physical-time convolution of the chemical transient. Either reset/wait to the AR01-promoted settled state at every point or model the actual chronological input/filter history. The notebook’s generic convolution is a theoretical starting point, not a substitute for this treatment.

### 14.4 Uncertainty budget

At minimum, propagate:

- protein concentration, optical path, and relevant extinction coefficients;
- CO pressure, temperature, Henry coefficient/model limitation;
- spectral-axis mapping, QCL linewidth, step grid, and fit covariance;
- detector dark, gain, linearity, responsivity imbalance, latency, and saturation margin;
- sample/reference covariance and common-mode rejection;
- average-power reading, zero, transfer ratios, repetition rate, spot area, and overlap;
- pump/probe optical timing, jitter, detector response, Pico timebase, and HF2 filter parameters;
- preparation, placement, day, and technical-repeat variation;
- correlation among calibration quantities.

Monte Carlo propagation is appropriate for the nonlinear ratio, spectral fit, photon/exposure calculation, and kinetic model. The notebook’s 10,000-draw default is a candidate; convergence of reported quantiles, rather than a fixed draw count, is the operational criterion. Correlated calibration inputs must be sampled jointly.

### 14.5 Canonical notebook audit result

The canonical notebook at `C:\Users\Chris\Documents\UC Davis\SETI\Thesis\articles\rsi-pump-probe\supplement\notebook\RSI_Supplemental_Theoretical_Calculations.nb` correctly identifies many required inputs: calibrated spectral mapping, QCL linewidth, dual-detector normalization, the HRP P/S kinetic model, repeated-pulse recovery, lock-in response, detectivity/noise, Allan behavior, and Monte Carlo uncertainty. It is the first-principles modeling authority, not a source of missing measurements.

Before analysis release, create a separately versioned executable derivative or analysis package because the saved notebook contains `Missing["ValueRequired"]` gates and saved syntax-message cells in at least the polymer-state, HRP-state-table, and myoglobin-state-table areas. Demonstrate clean evaluation from a fresh kernel with test data, preserve the canonical notebook unchanged, and record software/schema/analysis versions. No output value may be accepted merely because it appears in a saved output cell.

## 15. Experimental phases, gates, deliverables, and abort/restoration

This campaign is the first biological use of the shared permanent-iris 540 nm
OPO configuration. Complete R9 analysis/closeout and verify platform
restoration before MbCO biological phase MB-01 begins. The handoff exports the
promoted instrument configuration and validity state, not HRP absorbance,
quantum yield, overlap, dose-response, damage, or kinetic parameters. Failure
of an HRP scientific hypothesis is reportable and does not by itself prevent
the later MbCO campaign once HRP closeout and all independent MbCO gates pass.

| Phase | Work and deliverable | Gate to continue |
|---|---|---|
| R0 — requirements freeze | Approve this brief; assign question, claims, controls, parameter registry, and owners | No unresolved blocker classified “must resolve before characterization” |
| R1 — calibration completion | Complete and promote the minimum bundle in §8.1 | Explicit promotion; references resolve; no hash match gate |
| R2 — characterization | Complete §8.2 with non-biological samples/targets | CH00 settings frozen; E2E-CH and repeatability accepted and promoted |
| R3 — chemistry dry run | Practice buffer/reductant/CO records and sealed-cell handling under approved SOP without valuable protein as locally allowed | EHS authorization; leak/state/data records complete; waste route verified |
| R4 — reference preparation | Prepare sacrificial HRP-C(FeII)–CO; UV–visible and FTIR verification | State and stability acceptance; no pump exposure |
| R5 — steady-state pilot | Dark spectrum, controls, both directions, beginning/end state | Both target regions supported; no drift/saturation/state loss |
| R6 — exposure/recovery pilot | Verify the unchanged promoted iris configuration and post-iris power; run the lowest-setting 540 nm power ladder and rare-pump recovery without optimizing the iris on biology | Reversible regime and measured cadence established; iris/configuration validity passes |
| R7 — MVP acquisition | ≥3 independent preparations, randomized/interleaved blocks | Per-block QC and completion of planned controls |
| R8 — optional fast branch | Only after all §11.2 gates | IR01-supported resolution and independent exposure control |
| R9 — analysis/closeout | Versioned analysis, uncertainty, exclusions, predicted-vs-measured, report | Reproducible from indexed native data; restoration and retention audits pass |

### Abort conditions

Abort and safe-stop on: CO alarm or ventilation/interlock failure; gas leak or regulator/manifold anomaly; laser interlock failure; unidentified beam or optic; cell leak/crack/bubble; detector saturation or missing reference channel; MIRcat wavelength/status mismatch; lost external reference; timing-marker mismatch; pump command without expected observation or observed pump without command; exceeded event budget; unrecovered sample; photodamage flag; data-path/index failure; source or controller exception; or operator stop.

### Required restoration sequence

On normal completion and every abort path:

1. physically block/close the pump path;
2. disable MIRcat emission, stop tuning/process mode, disarm/deinitialize as required;
3. stop both T660 trigger sources and disable all channels;
4. apply `instrument/recipes/safe_idle.yaml` or its promoted successor;
5. verify readbacks and absence of optical events;
6. close HF2/Pico acquisitions without altering indexed native files;
7. place OPO parked/stopped and return the iris controller to its promoted safe ownership/state without changing the accepted aperture;
8. close/isolate the CO cylinder and depressurize/purge through the approved exhaust route;
9. move the sealed sample to its approved secondary containment or waste route;
10. write `restoration_confirmation` with operator, UTC times, state/readbacks, exceptions, and unresolved hazards.

The operator must never rely on process exit or a successful engine return as restoration evidence.

## 16. Data-contract implementation

Every phase follows `docs/data_contract/measurement_campaign_data_contract.md` version 1.0.0 or a later explicitly recorded version. Required core IDs include `campaign_id`, `phase_id`, `phase_run_id`, `acquisition_id`, `configuration_id`, `calibration_bundle_id`, `sample_id`, all installed device/component IDs, and operator ID.

Each phase directory contains, at minimum:

- manifest;
- acquisition index;
- conditions;
- measurements;
- artifacts;
- exclusions;
- calibration links;
- command log;
- final report;
- restoration confirmation;
- `raw/`, `analysis/`, `figures/`, and `tables/` subdirectories.

Biological additions to the conditions/acquisition records are: protein supplier/catalog/lot/isoenzyme evidence; RZ/activity; buffer/reductant/gas identities; calculations and actual additions; pH/temperature/pressure; preparation and closure timestamps; cell/window/spacer/seal IDs; sample state; UV–visible/FTIR verification artifact IDs; pump/probe spot and overlap configuration; post-iris average power and verified repetition; optically observed pump count; independently verified wavelength and residual-spectral-content bound; electronic-iris device/service/configuration ID, locked-mount check, commanded/read-back diameter, tolerance/fault and revalidation state; beam centroid/profile/aperture margin; wavelength/delay block; randomization block; control type; and beginning/end state checks.

Native raw data become immutable once indexed. Corrections, normalization, exclusions, and refits create new artifacts with `schema_version`, `analysis_version`, producer, source acquisition IDs, parameter-set ID, UTC creation time, relative path, and byte size. Checksums may be recorded diagnostically but matching a prior checksum is never the sole application, analysis, acceptance, closeout, or promotion gate. Aggregation validates human-readable IDs, paths, byte sizes, schemas, and relationships.

## 17. Safety requirements

### 17.1 Carbon monoxide and compressed gas

CO is colorless, odorless, flammable, and acutely toxic. NIOSH lists a 35 ppm time-weighted REL, a 200 ppm ceiling, and 1200 ppm IDLH; OSHA lists a 50 ppm TWA ([NIOSH Pocket Guide](https://www.cdc.gov/niosh/npg/npgd0105.html); [direct PDF](https://www.cdc.gov/niosh/docs/2005-149/pdfs/2005-149.pdf)). These are hazard references, not permission to work up to a limit.

Requirements are: current institutional approval; secured cylinder; compatible dual-stage regulator and tubing; ventilated enclosure or fume hood; exhausted purge; leak test with inert gas before CO; functioning area/personal monitoring as required by EHS; no lone work if prohibited; labeled secondary containment; trained response to alarm; and documented cylinder shutdown/purge. Never vent CO into the room, smell-test, use an unapproved improvised bag, or open a CO-equilibrated cell outside approved containment. The site SOP and EHS control alarm thresholds, occupancy response, PPE, and emergency actions.

### 17.2 Laser and optical radiation

The Surelite/Horizon and MIRcat beams are Class 4 hazards; invisible 1064/355 nm residuals, residual OPO outputs, and MIR radiation remain hazardous even when 540 nm is the intended beam. Requirements are trained/authorized operators, controlled access, interlocks, wavelength-appropriate eyewear selected by the laser safety officer for every accessible source/residual, enclosed beam paths where practicable, beam dumps, removal of reflective items, low-power/alignment mode, verified residual-harmonic/OPO-output separation, covers installed for normal operation, and no card/viewing method not explicitly approved. The Horizon manual specifically warns that both the 355 nm pump and its 192–2750 nm output can cause severe injury ([local manual](../../references/manuals/SLOPO/Horizon%20Oscillating%20Parametric%20Oscillator%20Operation%20Manual.pdf), p. 10).

### 17.3 Chemical, biological, and cell hazards

Follow the current SDS for sodium dithionite, phosphate reagents, cleaning agents, and HRP product. Handle protein to avoid inhalation/sensitization exposure and treat all solutions as laboratory chemical waste according to the approved plan. CaF₂ windows are brittle; inspect before use, handle with appropriate tools/gloves, and contain a cracked or leaking cell without touching fragments or contents. Dithionite/CO waste must not be sealed in a way that creates unassessed pressure and must not be mixed with incompatible oxidizers.

## 18. MVP versus optional scope

### Mandatory MVP

- one exact HRP-C(FeII)–CO system at pH 6.00 in H₂O;
- UV–visible state verification and actual-sample FTIR reference;
- QCL sample/reference steady-state spectrum containing both bound-CO bands;
- required chemical, optical, pump-blocked, and off-band controls;
- permanent-iris 540 nm OPO pump only;
- rare-pump room-temperature recovery streams at both bands;
- mean-energy/fluence reporting from average power and verified repetition only;
- at least three independent preparations, with feasibility-level inference if precision does not support more;
- versioned dual-detector analysis, uncertainty budget, data-contract closeout, and restoration audit.

### Optional after MVP

- fast point-delay pocket/escape kinetics;
- other-wavelength OPO or direct-532 excitation comparisons;
- D₂O/pD isotope study;
- BHA ternary complex as a single-conformer mechanistic test;
- isotope-labeled CO;
- pH series;
- CO-pressure series for `k_on` separation;
- flow/refresh cell for higher independent pump cadence;
- absolute photolysis yield, but only with validated absorbed-photon and spatial-overlap measurements.

Optional work remains outside the MVP, must not contaminate its frozen design or evidence, and requires a revised CH00 definition and any added safety/hardware dependencies.

## 19. Readiness checklist

### Scientific and chemical

- [ ] HRP-C source/identity, lot, RZ, activity, storage, and concentration method approved.
- [ ] 0.100 M phosphate/pH 6.00 calculation and measurement record approved.
- [ ] Dithionite and CO identities/SDS/SOP/waste plan approved.
- [ ] Residual-O₂ verification method and CO-loading method validated and promoted.
- [ ] CaF₂ 25 µm cell path, seals, volume, transmission, and leak method verified.
- [ ] UV–visible ferric, ferrous, and ferrous–CO reference envelopes frozen.
- [ ] FTIR reference of the actual prepared state acquired.
- [ ] Control matrix and preparation count frozen in CH00.

### Platform and timing

- [ ] Minimum calibration bundle in §8.1 promoted.
- [ ] Minimum characterization bundle in §8.2 promoted.
- [x] Replacement reference detector identity recorded: VIGO `SIP-DC-250M`
  serial `445161066`, detector `PVM-10.6-1x1` serial `21834`; DET-01 through
  DET-04 qualification remains pending.
- [ ] MIRcat installed range demonstrably includes the approved HRP grid.
- [ ] Experiment-builder capability registry updated and tested.
- [ ] WM-01 WaveMaster identity/communications/settings/response-state,
  repeatability, uncertainty, and validity bundle is promoted; every required
  OPO-540 block retains native wavelength/status evidence.
- [ ] ATT-01 iris control/fault behavior, permanent mount, 540 nm diameter/tolerance, contamination bound, and core margin are promoted; PB-02/OG-01/OV-01 pass with that exact configuration.
- [ ] Post-iris 540 nm wavelength, residual spectral content, sample-plane centroid/profile/spot/overlap/power, pulse-duration bound, and timing are characterized; another pump wavelength is absent.
- [ ] Independent finite-exposure path preserves qualified flashlamp cadence and counts optical pump events.
- [ ] OP01/CL01 optical timing and IR01 response promoted for the acquisition mode.
- [ ] HF2 settling/filter-history rule and Pico capture settings promoted.
- [ ] Normal, abort, exception, and operator-stop restoration paths dry-run and read back.

### Acquisition, analysis, and records

- [ ] Immutable plan contains exact wavenumbers, order, controls, dwell/settle, event budget, and abort rules.
- [ ] Average-power and repetition measurements support each reported mean pulse energy.
- [ ] Detector linearity/saturation margins and DET04 normalization table apply to the whole grid.
- [ ] PF01 sensitivity supports the prespecified claims.
- [ ] Randomization schedule and replicate/block definitions generated before acquisition.
- [ ] Analysis package evaluates cleanly from a fresh environment and is independent of saved notebook outputs.
- [ ] Data-contract directories, IDs, schemas, command logging, exclusions, and restoration records pass a non-biological dry run.
- [ ] Retention audit and final report template are ready.

No unchecked item may be waived by verbal assurance or by a matching hash.

## 20. Parameter evidence and dependency table

Classes: **LIT** = literature-backed biological/physical start; **MAN** = manufacturer constraint requiring installed-system verification; **CAL** = promoted calibration result; **CHAR** = promoted characterization result; **PILOT** = sample-specific feasibility/stability result that may set the biological envelope but never recalibrate hardware; **DER** = calculated from identified inputs with uncertainty; **DESIGN** = proposed CH00 criterion.

| Parameter | Recommended start/range | Rationale and source | Confidence | Class | Finalization/dependency |
|---|---|---|---|---|---|
| Protein species | Native glycosylated HRP isoenzyme C | Doster studied C and A2; HRP-C has the target two-band record | High scientifically; source availability unresolved | LIT/DESIGN | Source certificate or approved isoenzyme separation/identity record |
| Protein concentration | 3.00 mM | Low end of Doster’s 3–8 mM IR range, reducing absorption/material burden | High as literature bracket; medium as optimum | LIT/PILOT | UV–visible concentration; CH00 cell-transmission/sensitivity pilot |
| Buffer | 0.100 M sodium phosphate; no added salt | Doster preparation | High | LIT | Record exact acid/base recipe, pH, calculated ionic strength |
| pH | 6.00 | Doster and FTIR work; both conformer-associated bands are expected in this regime | High | LIT/PILOT | Calibrated pre/post measurement; CH00 tolerance from reference stability |
| Solvent | H₂O | D₂O shifts HRP-C–CO bands, so it is not interchangeable | High | LIT | D₂O/pD requires a new condition/model |
| Reductant | Fresh 10.0 eq dithionite | Doster preparation | High as start | LIT/PILOT | Anaerobic addition; UV–visible state verification; matched blank |
| CO pressure | 1.00 atm partial pressure | Doster preparation and kinetic anchor | High | LIT/SAFETY | Approved manifold; measured absolute pressure/temperature and SOP |
| Approx. dissolved CO | ~0.98 mM at 298.15 K | Derived from Sander’s pure-water coefficient | High for scale; medium for actual phosphate/protein solution | DER | Propagate pressure, temperature, coefficient/model uncertainty; do not call measured |
| Cell | CaF₂, 25 µm PTFE; cited range 10–50 µm | Doster cell materials/range; 25 µm midpoint | High for bracket; medium for selected path | LIT/PILOT | Measure path, leak, seals, transmission, fringes, detector linearity |
| Storage/usable lifetime | Source-instruction storage; single-use aliquots; lifetime from stability study | Avoids generalizing one product’s storage to purified HRP-C | Medium until source selected | MAN/PILOT | Source certificate + CH00 repeated state checks |
| Temperature | target 298.15 K only if active control is qualified; otherwise measured room temperature | Doster reports room-temperature behavior; Sander reference is 298.15 K | Medium | LIT/CHAR | Stage characterization determines control/tolerance and validity |
| IR bands | near 1905 and 1934 cm⁻¹ | Holzbaur; Smith/Ohlsson/Paul; Barlow; Ingledew/Rich | High | LIT/CAL | Exact centers/widths fitted with SP02 and sample uncertainty |
| Planning window | 1885–1950 cm⁻¹ | Brackets cited bands/local baselines | Medium as start | DESIGN/CAL/CHAR | QB01-HRP + SP02 + actual FTIR; freeze exact grid in CH00 |
| Spectral increment | ≤ one-half measured effective resolution | Sampling/identifiability rule; avoids equating step with resolution | High as algorithm | CAL/CHAR/DESIGN | QCL linewidth + SP02 + SV02 + simulation |
| Spectral dwell/averaging | `max(t_source/detector settle, t_filter settle) + t_average` | HF2 filter model and AR01/PF01 | High as algorithm | CHAR/DER | AR01/PF01 and CH00 precision target |
| Pump wavelength | permanent-iris OPO 540 nm | Doster's 530 nm result supports nearby visible heme excitation; 540 nm is the project-selected shared biological path, with equivalence established by the HRP dose/response pilot rather than assumed | High as design; biological efficiency pilot-dependent | LIT/MAN/CHAR/PILOT | ATT01 + PB02 + OG01/OV01/IR01 wavelength/path/iris/overlap/timing verification and R6 response |
| Pump pulse duration | not fixed | OPO output duration must be measured or bounded in the final post-iris configuration | Low until measured | MAN/CHAR | PB02/IR01 measure or bound; propagate uncertainty |
| Laser/OPO cadence | 10 Hz source candidate; rare sample-transmitted events | Installed laser thermal-lensing and OPO stability constraints | Medium pending installed QA | MAN/CHAR | ATT01/PB02 and laser/OPO QA; terminal PB01 does not gate the biological path; do not slow the source merely to protect sample unless the full output envelope is qualified |
| Sample pump cadence | 10/99 Hz ≈0.101 Hz commissioning candidate | Lowest approximate rate from 10 Hz and manual P99 range; below literature-planning recovery ceiling | Medium-low until optical behavior proven | MAN/CHAR/PILOT | Verify divider/pulse-picker optically; update from lower CI of `k_rec` |
| Recovery target | proposed 0.99 | Repeated-pulse model gives `t = −ln(1−R)/k`; protects independence | Medium; project criterion | DESIGN/PILOT | Freeze in CH00; enforce using lower confidence bound and slower supported model |
| Mean pulse energy | `E_mean=P_avg/f` only | Repository metrology rule; no energy meter | High | DER/CAL | OM01-qualified meter + ATT01/PB02/OG01 post-iris power + verified optical repetition + uncertainty/limitation statement |
| Pump fluence/overlap | derived, not fixed | Needs transfer, spot, profile, and overlap | Low until characterization | CAL/CHAR/DER | ATT01 + OG01 + OV01; select lowest reversible detectable ladder point |
| Photolyzed fraction | lowest detectable, proportional, reversible `f_obs`; no fixed percentage | Must come from actual bleach, overlap, IRF, and dose ladder | Low until pilot | PILOT/DER | PF01 + power ladder + state checks; freeze CH00 operating interval |
| MIRcat pulse/repetition | 10 Hz probe candidate; high-rate fallback only after E2E | 10 Hz supports ~1 s recovery and common master; current 2 MHz/150 ns is alignment-only | Medium-low | CHAR/DESIGN | QB01-HRP/DET/PF01/IR01 architecture comparison |
| HF2 order/τ/rate | not fixed | Current order 4, 1 ms, 2 kSa/s are provisional | Low until AR01/PF01 | CHAR/DER | Settle equation + measured filter/source response + precision target |
| Pico settings | not fixed for biology | MS settings served electrical timing, not biological kinetics | Low until PT/IR | CAL/CHAR | PT01 + DET03 + IR01 returned interval/range/record selection |
| Delay grid | IRF-derived negative, dense prompt, optimized/log positive, recovery tail | Prevents nominal electronic values from defining chemical time | High as algorithm | CAL/CHAR/DER | OP01/CL01/IR01 + PF01 + kinetic simulation |
| Independent preparations/days | feasibility minimum 3 preparations across 3 days | Minimum for preparation/day variation; not automatic confirmatory power | Medium; design minimum | DESIGN/PILOT | CH00 precision calculation may only increase it |
| Spectral/photodamage thresholds | not fixed | Must depend on PF01 uncertainty and pilot dose response | Low until pilot | CHAR/PILOT/DESIGN | Freeze in CH00 before MVP acquisition |

## 21. Traceability and unresolved-decision register

| ID | Decision or blocker | Owner/evidence required | Blocks |
|---|---|---|---|
| HRP-01 | Identify an obtainable, defensible HRP-C source or approve purification/identity method | Scientific lead; source certificate or isoenzyme-resolving evidence | All biological work |
| HRP-02 | Freeze RZ/activity/state spectral acceptance envelopes | CH00 + sacrificial reference preparation | Sample release |
| GAS-01 | Approve CO cylinder grade, manifold, monitor, loading, residual-O₂ method, waste, and emergency SOP | EHS + laboratory owner | CO handling |
| CELL-01 | Verify 25 µm gas-tight cell path, seals, fill volume, transmission, and leak method | Characterization record | Sample loading |
| MIR-01 | Demonstrate installed MIRcat coverage at 1905/1934 cm⁻¹ and update capability registry | QB01-HRP + software tests | Spectroscopy/kinetics |
| EXP-01 | Implement and prove finite sample exposure independent of T660 shot-counter reset and iris motion | ATT01/PB02/OP01/FE01/E2E; optical pump observation | Pumped experiment |
| TIM-01 | Promote optical pump/probe timing and IRF for MVP mode | OP01/CL01/IR01 | Time-resolved claims |
| POW-01 | Promote post-iris average-power/transfer/spot/overlap chain; freeze reversible power ladder | OM01/ATT01/PB02/OG01/OV01 | Quantitative exposure |
| WAV-01 | Promote installed 540 nm wavelength working-reference identity/settings/native-status/uncertainty and retain separate residual spectral-power evidence | WM-01/ATT-01/PB-02 | All pumped biological work and notebook wavelength assignment |
| DET-01 | Install/identify reference detector and promote wavelength normalization | TR-01/DET01–04 | Quantitative absorbance |
| ANA-01 | Repair/port notebook logic into a clean-evaluating, versioned analysis package | Analysis lead; tests with synthetic and reference data | Final kinetic inference |
| STAT-01 | Freeze precision target, sample size, exclusions, model comparison, and recovery criterion | CH00 after PF01/pilot | MVP acquisition |
| OPO-01 | Promote the permanent-iris 540 nm OPO wavelength, stability, residual-content, power/profile, aperture-margin, timing, and finite-event envelope | WM-01/ATT-01/PB-02/OG-01/OV-01/OP-01/FE-01/IR-01 | All pumped biological work; supplemental PB-01 direct-355 measurement is excluded from this gate |

## 22. Sources utilized

Direct PDF URLs are supplied when a stable public or publisher endpoint was found. Publisher PDF links may still require institutional access; the adjacent DOI/article link is the durable fallback.

### Literature traceability

| Requirement/claim | Controlling source(s) | How used; disagreement/limit resolved |
|---|---|---|
| HRP-C selection and preparation | Doster 1987; Shannon 1966 | Doster supplies the exact C/A2 preparation context; Shannon establishes isoenzyme heterogeneity. A commercial mixed HRP product is therefore feedstock only. |
| 1905/1934 cm⁻¹ assignments | Holzbaur 1996; Smith/Ohlsson/Paul 1983; Barlow 1976; Ingledew/Rich 2005 | All support a low- and high-frequency HRP-C–CO form; small center differences are treated as condition/sample results, not contradictions or fixed acceptance values. |
| pH 6.00/H₂O choice | Doster 1987; Holzbaur 1996; Smith/Ohlsson/Paul 1983; Kaposi 2001 | pH changes band populations and D₂O shifts centers. The MVP fixes pH 6.00/H₂O; pD/D₂O is separate. Holzbaur’s broader pH interpretation supersedes treating one band ratio as universal. |
| 3 mM, 0.1 M phosphate, 10 eq dithionite, 1 atm CO, CaF₂/25 µm | Doster 1987 | Values/ranges are directly anchored; 3 mM and 25 µm deliberately choose the low concentration and midpoint path, then require transmission verification. Glycerol is excluded because it was a cryogenic matrix. |
| Approximate dissolved CO | Sander 2015 | Provides pure-water Henry coefficient. The ~0.98 mM result is a calculated prior, not a measurement in phosphate/protein. |
| 540 nm pump | Doster 1987; Horizon/Surelite manuals; project experiment-order decision | The 530 nm primary-literature precedent supports nearby visible excitation but does not prove quantitative equivalence. The shared 540 nm OPO path is qualified instrumentally once, then HRP-specific response/damage and absorbed-photon inputs are established in R6. |
| ~1 s⁻¹ late recovery planning value | Doster 1987 | Used only to expose 10 Hz accumulation risk and plan record length; each preparation’s cadence uses its measured lower-confidence recovery result. |
| Two-state kinetic model | Doster 1987; canonical notebook | Literature supports pocket/solvent processes, but room-temperature MVP begins with the identifiable late exponential. Full P/S parameters require optional fast-mode resolution. |
| Dual-detector normalization/filter/IRF | canonical notebook; HF2 manual; repository DET/IR phases | Notebook equations define required inputs. Empirical detector balance and IRF replace assumed equality/nominal shapes. Chronological HF2 filter memory is modeled rather than automatically treated as chemical-time convolution. |
| Nd:YAG timing and thermal cadence | Surelite manual; repository calibration evidence | Manufacturer values bound DAT modes. Installed optical timing comes from OP01/CL01. Nominal 179.830 µs and UI 250 µs are rejected as unpromoted defaults. |
| OPO scope | Horizon manual; WaveMaster and ELL15 manuals; WM-01/ATT-01/PB-02/OG-01/OV-01 | OPO 540 nm is mandatory. Its 355 nm drive, wavelength identity/status, bandwidth, timing, residual outputs, pointing, permanent iris, and post-iris transfer are qualified before HRP exposure; broad tuning remains excluded. Center-wavelength and spectral-power-fraction authorities remain separate. |
| CO/reductant/laser hazards | NIOSH; supplier SDS; Surelite/Horizon manuals | These define hazards and manufacturer constraints. Local procedures/alarms/approvals remain institutional decisions and are not invented here. |

### Primary HRP/CO literature

1. Doster, W.; Bowne, S. F.; Frauenfelder, H.; Reinisch, L.; Shyamsunder, E. “Recombination of Carbon Monoxide to Ferrous Horseradish Peroxidase Types A and C.” *Journal of Molecular Biology* 194 (1987) 299–312. [Direct PDF](https://wolfgang-doster.de/Gesamtfolder/jmb87hrp.pdf) · [DOI](https://doi.org/10.1016/0022-2836(87)90377-9). Used for isoenzyme choice, preparation, cell/path range, 530 nm photolysis precedent, and room-temperature recovery anchor.
2. Holzbaur, I. E.; English, A. M.; Ismail, A. A. “Infrared Spectra of Carbonyl Horseradish Peroxidase and Its Substrate Complexes: Characterization of pH-Dependent Conformers.” *JACS* 118 (1996) 3354–3359. [Article/DOI](https://pubs.acs.org/doi/10.1021/ja953715o) · [Publisher PDF](https://pubs.acs.org/doi/pdf/10.1021/ja953715o). Used for 1905/1934 cm⁻¹ bands, pH dependence, and BHA control rationale.
3. Smith, M. L.; Ohlsson, P.-I.; Paul, K. G. “Infrared Spectroscopic Evidence of Hydrogen Bonding between Carbon Monoxide and Protein in Carbonylhorseradish Peroxidase C.” *FEBS Letters* 163 (1983) 303–305. [Article/DOI](https://doi.org/10.1016/0014-5793(83)80840-0). Used for HRP-C band positions and H₂O/D₂O shifts.
4. Barlow, C. H.; Ohlsson, P. I.; Paul, K. G. “Infrared Spectroscopic Studies of Carbonyl Horseradish Peroxidases.” *Biochemistry* 15 (1976) 2225–2229. [PubMed/DOI](https://pubmed.ncbi.nlm.nih.gov/1276134/) · [Publisher PDF](https://pubs.acs.org/doi/pdf/10.1021/bi00655a031). Used for isoenzyme- and pH-dependent CO bands.
5. Evangelista-Kirkup, R.; Smulevich, G.; Spiro, T. G. “Alternative Carbon Monoxide Binding Modes for Horseradish Peroxidase Studied by Resonance Raman Spectroscopy.” *Biochemistry* 25 (1986) 4420–4425. [Article/DOI](https://pubs.acs.org/doi/10.1021/bi00363a037) · [Publisher PDF](https://pubs.acs.org/doi/pdf/10.1021/bi00363a037). Used for the two-binding-mode interpretation.
6. Ingledew, W. J.; Rich, P. R. “A Study of the Horseradish Peroxidase Catalytic Site by FTIR Spectroscopy.” *Biochemical Society Transactions* 33 (2005) 886–889. [Institutional record](https://research-portal.st-andrews.ac.uk/en/publications/a-study-of-the-horseradish-peroxidase-catalytic-site-by-ftir-spec/) · [DOI](https://doi.org/10.1042/BST0330886). Used for light-minus-dark FTIR, pH/pD behavior, the photolyzed-CO feature, and protein/heme difference signals.
7. Carlsson, G. H.; Nicholls, P.; Svistunenko, D.; Berglund, G. I.; Hajdu, J. “Complexes of Horseradish Peroxidase with Formate, Acetate, and Carbon Monoxide.” *Biochemistry* 44 (2005) 635–642. [Article/DOI](https://pubs.acs.org/doi/10.1021/bi0483211) · [Publisher PDF](https://pubs.acs.org/doi/pdf/10.1021/bi0483211). Used for ferrous–CO state and structural context.
8. Kaposi, A. D.; Wright, W. W.; Fidy, J.; Stavrov, S. S.; Vanderkooi, J. M.; Rasnik, I. “Carbonmonoxy Horseradish Peroxidase as a Function of pH and Substrate: Influence of Local Electric Fields on the Optical and Infrared Spectra.” *Biochemistry* 40 (2001) 3483–3491. [Direct PDF](https://biofiz.semmelweis.hu/people/fidy_judit/2001_Biochem_Kaposi.pdf) · [DOI](https://doi.org/10.1021/bi002784z). Used to check solvent/pH sensitivity and optical/IR state interpretation.
9. Shannon, L. M.; Kay, E.; Lew, J. Y. “Peroxidase Isozymes from Horseradish Roots. I. Isolation and Physical Properties.” *JBC* 241 (1966) 2166–2172. [PubMed](https://pubmed.ncbi.nlm.nih.gov/5946638/) · [Article/DOI](https://doi.org/10.1016/S0021-9258(18)96680-9). Used to establish that HRP isoenzyme identity is material.

### Physical chemistry, product, and safety sources

10. Sander, R. “Compilation of Henry’s Law Constants (Version 4.0) for Water as Solvent.” *Atmospheric Chemistry and Physics* 15 (2015) 4399–4981. [Direct PDF](https://www.atmos-chem-phys.net/15/4399/2015/acp-15-4399-2015.pdf) · [DOI](https://doi.org/10.5194/acp-15-4399-2015). Used for the approximate dissolved-CO calculation.
11. MilliporeSigma. “Peroxidase from Horseradish, Type VI-A, P6782” product information. [Direct PDF](https://b2b.sigmaaldrich.com/deepweb/assets/sigmaaldrich/product/documents/223/099/p6782dat-mk.pdf) · [Product page](https://www.sigmaaldrich.com/US/en/product/sigma/p6782). Used to distinguish a commercial HRP product from defined isoenzyme C and document RZ meaning.
12. MilliporeSigma. Sodium dithionite Safety Data Sheet. [Current SDS](https://www.sigmaaldrich.com/US/en/sds/saj/28-2930). Used for reductant hazards.
13. NIOSH. “Carbon Monoxide,” *Pocket Guide to Chemical Hazards*. [Current web entry](https://www.cdc.gov/niosh/npg/npgd0105.html) · [Direct guide PDF](https://www.cdc.gov/niosh/docs/2005-149/pdfs/2005-149.pdf). Used for CO identity, flammability, exposure limits, symptoms, and IDLH.

### Manufacturer manuals and repository authorities

14. Continuum. *Surelite Nd:YAG Laser Manual*, document 996-0207. [Repository PDF](../../references/manuals/YAG/Surelite%20NdYAG%20Laser%20Manual.pdf). Used for 532/355 nm outputs, DAT timing/jitter, command pulse widths, pulse division, thermal-cadence warning, and Class 4 precautions.
15. Continuum. *Horizon I and II OPO Operation and Maintenance Manual*, document 996-0034. [Repository PDF](../../references/manuals/SLOPO/Horizon%20Oscillating%20Parametric%20Oscillator%20Operation%20Manual.pdf). Used to define the mandatory 355 nm-pumped 540 nm OPO path, wavelength verification, warm-up, output-port, timing, residual-output, and safety requirements.
16. Daylight Solutions. *MIRcat Manual* and *MIRcat SDK Guide*. [Repository manual](../../references/manuals/MIRcat/Daylight%20Solutions%20MIRcat%20Manual.pdf) · [Repository SDK guide](../../references/sdk/MIRcat/MIRcatSDKGuide.pdf). Used for source modes, trigger/process behavior, and safe state.
17. Highland Technology. *T660 Manual* and *T660 Programming Guide*. [Repository manual](../../references/manuals/T660/Highland%20Technologies%20T660%20Manual.pdf) · [Repository programming guide](../../references/manuals/T660/Highland%20Technologies%20T660%20Programming%20Guide.pdf). Used for predivider/burst semantics, trigger/shot behavior, timing specifications, and readback requirements.
18. Zurich Instruments. *HF2 User Manual*. [Current official manual](https://docs.zhinst.com/hf2_user_manual/index.html) · [Repository PDF](../../references/manuals/HF2LI/Zurich%20Insturments%20HF2LI%20User%20Manual.pdf). Used for dual-input demodulation, external reference, time constants, filter order, streaming, and DAQ behavior.
19. Pico Technology. *PicoScope 5000D Series Data Sheet*. [Direct official PDF](https://www.picotech.com/download/datasheets/picoscope-5000d-series-data-sheet.pdf) · [manual index](https://www.picotech.com/oscilloscope/5000/picoscope-5000-manuals). Used for the installed 5244D capture capability and environmental/accuracy context.
20. VIGO System. *MID-IR Detector Package* documentation. [Repository PDF](../../references/manuals/Detectors/MIDIR-Detector-Package.pdf). Used only as a starting hardware reference; DET01–04 measurements control experimental use.
21. Repository authorities: [`repository_scope.md`](../../docs/architecture/repository_scope.md), [`measurement_campaign_data_contract.md`](../../docs/data_contract/measurement_campaign_data_contract.md), [`repository_cleanup_20260814.md`](../../docs/architecture/repository_cleanup_20260814.md), the active calibration/characterization campaign records, hardware configuration/wiring map, safe-idle recipe, and current control/workflow implementation. Used for authority boundaries, campaign state, IDs/retention, wiring, restoration, and builder limitations.
22. Daylight Solutions/manufacturer correspondence. [`daylight_db9_process_trigger_correspondence.md`](../../references/manuals/MIRcat/daylight_db9_process_trigger_correspondence.md). Used for installed DB9 pin roles and the active-low process-trigger interval; still subject to MD01 installed verification.
23. Coherent. *WaveMaster User Manual*, part 1095245 Rev. AA, and catalog data sheet. [Repository manual](../../references/manuals/WaveMaster/WaveMaster_Manual.pdf) · [repository data sheet](../../references/manuals/WaveMaster/Coherent_WaveMaster_33-2650_Datasheet.pdf). Used for wavelength range, accuracy/resolution, pulsed mode, autocalibration, native response states, thermal stability, probe handling, RS-232 settings, and measurement limitations.
24. Thorlabs. *ELL15K Motorized Iris Manual*, Rev. A, and Elliptec communication protocol, Issue 12. [Repository manual](../../references/manuals/Iris/ELL15K_Iris_Manual.pdf) · [repository protocol](../../references/manuals/Iris/Ellx_Iris_Communication_Protocol.pdf). Used for aperture range/units, repeatability/backlash, control behavior, USB identity, homing, and 950 nm home-sensor leakage control.
23. Merck. “Horseradish Peroxidase (HRP) Enzymes.” [Manufacturer technical note](https://www.merckmillipore.com/TD/en/technical-documents/technical-article/protein-biology/enzyme-activity-assays/peroxidase-enzymes). Used only as the generic ε403/RZ concentration reference pending HRP-C-specific CH00 freeze.
24. `RSI_Supplemental_Theoretical_Calculations.nb`, canonical theoretical notebook at `C:\Users\Chris\Documents\UC Davis\SETI\Thesis\articles\rsi-pump-probe\supplement\notebook\RSI_Supplemental_Theoretical_Calculations.nb`. Used for equations, required inputs, candidate model structure, repeated-pulse behavior, lock-in/IRF/noise treatment, and uncertainty architecture; missing inputs and saved outputs are not measurement authority.
25. Klapper, M. H.; Hackett, D. P. “The Oxidatic Activity of Horseradish Peroxidase. II. Participation of Ferroperoxidase.” *Journal of Biological Chemistry* 238 (1963) 3743–3749. [PubMed/free-article record](https://pubmed.ncbi.nlm.nih.gov/14109214/). Used for the ferrous HRP–CO electronic absorption maxima and light sensitivity.
