# HF-01 revalidation triggers

The provisional bundle `HF01-PROVISIONAL-ELECTRICAL-RESPONSE-v1` remains valid
only while its device, route, configuration, and application envelopes remain
unchanged. Revalidate the affected result after any of the following:

- HF2LI replacement, repair, service, firmware/API-server change, oscillator or
  demodulator implementation change, or a node readback outside the retained
  configuration snapshot;
- failure to reload a selected ID within exact integer and `1e-9` relative
  double-node equivalence;
- a change to `CLOCK-SPLITTER-01`, T660 clock mode, DIO0 external-reference
  route, T660-2 A/C routes, reference frequency, or imported MS-01/MS-02/T2-01
  timing/path corrections;
- a change in signal-input topology, coupling, impedance, differential mode,
  range, cable/tee path, grounding, or another source on an HF2LI input;
- detector output exceeding the retained 1 V range margin, any ADC clipping,
  sample loss, reference unlock, or zero-noise/channel-equivalence drift beyond
  the limits in `tables/hf01_uncertainty_acceptance.csv`;
- use at a sweep speed or feature/distortion tolerance outside the analyzed
  scan-response envelope;
- an HRP claim with a faster early feature, tighter precision, greater drift,
  or longer record envelope than the downstream-approved bounds; or
- a changed channel count, readout mode, output rate, filter order, time
  constant, or full-DIO recording requirement.

The MbCO mandatory 1 us limitation cannot be cleared by reloading or choosing
another supported HF2LI setting. Clearing it requires a different acquisition
path/hardware, a valid higher-bandwidth strategy, or an explicitly changed
scientific requirement followed by prospective qualification.

HF-02 must still qualify timestamp integrity, buffering, loss, and maximum
duration at the retained rates. Detector and optical phases must import rather
than silently replace the HF-01 electrical response.
