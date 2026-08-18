# PT-01 reference planes and sign convention

- Reference: falling-edge arrival at the disconnected Nd:YAG timing harness
  FIRE pin 7, measured through Adapter A on PicoScope channel A; pin 2 is the
  adapter shield/ground reference.
- Target: falling-edge arrival at pin 4 at the MIRcat-disconnected end of
  `MIRCAT-DB9-CABLE-01`, measured through Adapter B on PicoScope channel B;
  MIRcat DB9 pin 7 is the adapter shield/ground reference.
- Sign: target CHB arrival minus reference CHA arrival. Positive means Process
  Trigger arrives later than FIRE.
- Corrections: subtract MS-02 PicoScope CHB-minus-CHA path correction and
  subtract T1-01 Adapter B-minus-A differential delay. Raw and each corrected
  state remain distinct in `analysis.json`.
