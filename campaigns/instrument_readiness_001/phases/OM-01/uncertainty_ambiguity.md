# OM-01 uncertainty and ambiguity statement

The available 919P-010-16 certificate reports 1.9% expanded uncertainty at
`k=2` and passed tabulated checks at 532, 1066, and 10600 nm. The certificate's
July 2026 recommended recalibration date has passed. The operator reports that
the sensor has not been used since calibration and accepts bounded campaign
use. This is not represented as an issuer extension or a new certificate date.

The 532 nm point has direct certificate support. The 355 nm, 540 nm, and 5--6
um regions use the sensor EEPROM wavelength response and are labeled bounded
rather than independent point calibrations. Exact later setpoints must record
the requested wavelength/wavenumber and meter integer-nm setting.

The representative 540 nm provisional budget is in
`provisional_uncertainty_budget.md`: 4.34% expanded at `k=2`. It includes the
certificate, manufacturer linearity/uniformity, installed between-window
repeatability, and background/noise. Binary full-beam containment was observed
against the known 8 mm active radius, but no numerical beam diameter or fluence
is claimed. OG-01 owns quantitative and invisible-beam geometry.

The 49.5% initial-to-revisit output change is classified as OPO/source
evolution because the OPO is not a calibrated transfer standard. It is not
silently folded into meter uncertainty and remains a PB-02 input.

The OPO output is also known not to be spectrally pure at the GUI-selected
wavelength and exhibited visible halos. The thermopile reading combines all
incident wavelength components, while the 540 nm meter setting applies a
single responsivity correction. Component wavelengths and power fractions were
not measured, so spectral-composition bias is unquantified, is not treated as
zero, and is not included in the 4.34% value. That value describes uncertainty
of the meter indication under the observed mixed-spectrum condition, not
uncertainty of spectrally isolated 540 nm power.

Only average optical power is qualified. Later mean pulse energy may be
derived from average power and a verified repetition rate. Direct pulse-energy
distributions and calibrated peak power remain excluded.
