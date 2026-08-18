# TR-01 final report

Campaign: `system_recalibration_001`  
Phase run: `system_recalibration_001_TR-01_001`  
Decision: **PASS - COMPLETE**

## Acceptance

Every mandatory TR-01 criterion is satisfied. The retained resource register
records stable identity, manufacturer/model, installed identity, role,
configuration relevance, evidence, uncertainty/reference basis,
applicability, validity limits, and disposition. The P0 export accounts for
all 21 decisions. Working references are explicitly separated from devices
whose installed behavior is or will be directly qualified.

PicoScope `5244D` serial `10261` is retained as the electrical timing working
reference. Accepted completed configurations used 8-bit DC acquisition on
channels A/B at the 10 V range, timebases 1, 3, 11, and 12, corresponding in
the saved readbacks to 2, 8, 72, and 80 ns sample intervals. The manufacturer
data sheet basis is +/-2 ppm initial timebase accuracy and +/-1 ppm/year drift.
Its 8-bit gain specification is +/-2% of signal +/-1 LSB under the documented
temperature/warm-up condition and is nonapplicable to threshold-only
diagnostics. No certificate or accredited traceability is claimed.

T660-1, T660-2, MIRcat, HF2LI, detector chains, Nd:YAG, and OPO remain devices
under test. Completed MS-01, MS-02, T2-01, T1-01, PT-01, CH-00, and MC-01
records are linked by stable identifiers without copying or reacquisition.
P0, S0, and the completed phases were not modified.

MIRcat accepted configuration provenance is GUI `1.9.0.4`, firmware `3.1.0`,
and SDK API `2.4.1`. The accepted MC-01 HF2LI diagnostic used LabOne packages
`zhinst 26.4.0` and `zhinst.core 26.4.0.940`, API level 1, with a 210000000 Hz
clockbase readback. Later accepted configurations must record their versions
again. The data contract/schema convention is `1.0.0`; configuration and
analysis identities are stable human-readable versions and hashes are not
operational gates.

Polystyrene and Mylar authority is retained but correctly deferred to SP-01.
Optical resource selection/qualification is deferred to OM-01. Missing,
unavailable, comparison-only, superseded, nonapplicable, excluded, and later-
phase inputs are classified in the unresolved and exclusion registers; none
blocks the TR-01 identity/resource closure claim.

## Restoration and boundary

TR-01 was records-only. No device client was opened and no physical state was
changed. Final recorded state: MIRcat powered down; manual shutter closed;
interlock ON; default wiring restored with T660-1 channel D and MIRcat DB9 pin
5 disconnected and pins 6/8 unused/unwired; ownership released; retained final
T660 safe idle linked to the completed MC-01 restoration. No laser was armed
or emitted, no sample/CO/biological work occurred, and no canonical output was
promoted. Nothing was staged, committed, or pushed.

Downstream eligibility is limited to consuming this identity/resource
register and its linked completed evidence. It does not authorize or satisfy
any optical calibration, source characterization, detector qualification,
characterization, promotion, or experiment.

The exact next phase is **OM-01 - optical metrology readiness and transfer
standards**. It requires separate authorization. No subsequent phase began.
