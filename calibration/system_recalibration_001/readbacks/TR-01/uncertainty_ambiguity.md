# TR-01 uncertainty and ambiguity statement

TR-01 introduces no new measured quantity. Its uncertainty contribution is
classification and applicability: every later quantitative result must use the
uncertainty stated by its linked completed phase or by the later phase that
qualifies the selected working reference.

The PicoScope `5244D` serial `10261` is the only current formal working
reference in the completed electrical timing chain. The manufacturer data
sheet supplies an initial timebase bound of +/-2 ppm and drift of +/-1 ppm per
year for the 5244D family. Completed timing analyses already include the 2 ppm
term and their MS-01/MS-02 path terms. The 8-bit analog gain bound is +/-2% of
signal +/-1 LSB, applicable at 15-30 C after one hour warm-up; it is applied
only when voltage is a quantitative result, not when voltage merely defines a
threshold diagnostic. No accredited traceability is claimed because the
reported available certificate was unavailable and P0-D002 narrowed the
requirement to applicable manufacturer specifications.

T660-1, T660-2, MIRcat, HF2LI, both installed detector chains, Nd:YAG, and OPO
are devices under test. Their identity and installed behavior are not upgraded
to formal reference status. Completed direct campaign measurements retain
their own uncertainty and configuration envelopes; later named phases remain
required for unmeasured behavior.

Polystyrene and Mylar are selected spectral working-reference candidates but
remain comparison-only until SP-01 establishes authoritative feature values
and uncertainty. Missing certificates, peak lists, lot identity, path length,
or thickness tolerance are preserved as limitations, never represented as
zero. Absolute film absorbance and quantitative etalon claims are excluded.

MIRcat GUI/SDK, LabOne package, host, GUI-observation, T660, and HF2LI clocks
are not a synchronized common timebase. MC-01's DIO21 events are correlated
event evidence, not a persistent ready level or a universal fixed delay.
Hash/checksum equality is not used as an acceptance or aggregation gate.
