# MC-01 emitting/SDK continuation authorization

Authorization ID: `MC01-AUTH-002`  
Recorded UTC: `2026-08-17T20:32:17.9445320Z`  
Authorizer/operator: Christopher Robertson  
Phase run: `system_recalibration_001_MC-01_001`

The operator authorizes the actions necessary to complete MC-01, including a
controlled emitting continuation and MIRcat SDK controls where needed to obtain
the mandatory MC-01 results. This authorization remains valid across task or
session boundaries until MC-01 passes, reaches a new genuine blocker, or the
operator explicitly revokes or changes it. Future tasks resuming this same
phase shall import this stable authorization ID and shall not ask for the same
authorization again.

This authorization is limited to the retained MC-01 Step and Measure
point/process sequence, its inhibited control, three bounded repeats,
state/DIO/latency and failure observations, configuration evidence, and final
restoration. It permits arming and optical emission only to the minimum extent
needed for those bounded tests. GUI qualification remains first; SDK control
may be used only where needed after the GUI behavior is established or to
obtain a required readback unavailable in the GUI.

The following boundaries remain in force:

- No TR-01, PB-01, other calibration, characterization, or experiment phase.
- No samples, CO handling, or biological work.
- No T660-1 channel D and no MIRcat DB9 pins 5, 6, or 8.
- Preserve all prior and new evidence; do not overwrite PT-01 or the earlier
  non-emitting MC-01 evidence.
- Apply and verify safe idle before physical transitions and after completion.
- No calibration promotion, staging, commit, or push.

This record supersedes only the earlier MC-01 non-emitting authorization
boundary. It does not alter completed immutable phases or authorize later
phases.
