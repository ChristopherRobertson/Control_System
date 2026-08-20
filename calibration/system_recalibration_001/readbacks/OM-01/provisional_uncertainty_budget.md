# OM-01 provisional uncertainty budget

Representative condition: mixed-spectrum OPO output with the OPO GUI and meter
wavelength setting at 540 nm, 300 us programmed FIRE-to-Q delay, 10 Hz, manual
range 0, 0.5 Hz analog filter, digital filter off.

The three accepted window means were 83.053, 84.414, and 85.478 mW. Their mean
was 84.315 mW and their sample standard deviation was 1.215 mW (1.442%).

| Contribution | Treatment | Relative standard uncertainty |
|---|---|---:|
| Sensor certificate | 1.9% expanded, k=2 | 0.950% |
| Manufacturer linearity | +/-1%, rectangular | 0.577% |
| Installed between-window repeatability | observed sample SD of window means | 1.442% |
| Background/noise | conservative 0.2 mW at 84.315 mW | 0.237% |
| Manufacturer uniformity / unresolved placement | +/-2%, rectangular | 1.155% |

The provisional root-sum-square relative standard uncertainty is 2.17%; a
provisional k=2 expanded value is 4.34% (about 3.66 mW at 84.315 mW).
Binary containment of the full visible footprint, including the observed
halos, was confirmed, but no quantitative edge margin was measured.

The OPO output is not spectrally pure. Because the component wavelengths and
their power fractions were not measured, the bias caused by applying one
540 nm responsivity correction to the combined incident spectrum cannot be
quantified and is not treated as zero or included in the 4.34% value. Thus the
budget applies to the meter indication under this mixed-spectrum condition,
not to spectrally isolated 540 nm power. Wavelength-specific delivered-power
claims require spectral characterization or qualified wavelength-selective
filtering in PB-02 and the applicable downstream transfer phase.

The later return-to-setting stable tail averaged 126.073 mW, 49.5% above the
initial mean. This is source/OPO evolution under nominally unchanged controls,
not a calibrated meter-reference drift test. It is retained for PB-02 and is
not added to the power-meter uncertainty budget.
