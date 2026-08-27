# OM-01 final report

Decision: **PASS - COMPLETE, QUALIFIED BOUNDED WORKING REFERENCE**

The Newport 1918-R serial `15879` and 919P-010-16 sensor serial `161791`
passed identity, Python 3 USB communication, sensor-condition, covered dark,
stored-zero, uncovered ambient, manual-range, status, shutter-response,
installed repeatability, wavelength-rule, saturation-rule, restoration, and
bounded spatial/polarization applicability checks.

At the representative OPO condition with the meter wavelength setting at
540 nm, three accepted 30-reading window
means were 83.053, 84.414, and 85.478 mW. Their mean was 84.315 mW and the
between-window CV was 1.44%. All meter status words were normal. The operator
confirmed the full visible beam, including the observed surrounding halos, fit
within the sensor's 8 mm active radius. The OPO output is known not to be
spectrally pure at the GUI-selected wavelength. Accordingly, 84.315 mW is an
indicated total incident OPO-output power using the meter's 540 nm responsivity
setting; it is not a measurement of spectrally isolated 540 nm power.

The return-to-setting record stabilized near 126.073 mW, 49.5% above the
initial mean under nominally unchanged controls. This is retained as OPO/source
evolution for PB-02 and is not misrepresented as meter drift or added to the
meter uncertainty.

The representative provisional expanded uncertainty is 4.34% at k=2 for the
meter indication under the observed mixed-spectrum condition. Spectral-
composition bias is unquantified and is not included in that value. The
bundle is limited to average optical power and binary total-beam containment.
It does not establish pulse-energy distributions, peak power, quantitative
beam diameter/fluence, polarization-dependent transfer, source stability, or
final sample-plane power.

Final restoration passed: both T660 units matched Safe Idle with every channel
off; Nd:YAG was powered down; OPO remained intentionally powered for thermal
stability with no pump and output shutter closed; MIRcat was not used and was
left emission-off, disarmed, shutter-closed, cooling/interlock normal, and
ownership-free; the sensor was removed, covered, and left with zero inactive.

No canonical calibration promotion, Git stage, commit, or push was performed.
ATT-01 and later phases remain unauthorized pending separate approval.
