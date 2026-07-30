# MS-01 final report

Status: **PASS — MS-01 COMPLETE; LATER PHASES NOT STARTED**

## Ownership and safety

- No surviving device-control process was found before access.
- PicoScope 5244D, configured serial `10261`, SDK identifier `10261/0071`,
  opened successfully.
- T660-1 serial `00369` and T660-2 serial `00431` were controlled directly.
- Initial safe idle matched the repository recipe with no mismatches.
- Both lasers and the room interlock were operator-confirmed inhibited/ready.
- No MIRcat connection or Process Trigger command was used.

## Wiring confirmations

- Normal: T660-2 CHA fixed 12-inch SMB-to-BNC bulkhead to splitter input;
  S1 directly to PicoScope CHA; S2 directly to PicoScope CHB; third branch open.
- Swapped: splitter input and third branch unchanged; S2 directly to PicoScope
  CHA; S1 directly to PicoScope CHB.
- No additional measurement cables or adapters were present on S1/S2.

## PicoScope and acquisition

- Resolution: 8 bit; CHA/CHB: DC coupled, 10 V range, zero offset.
- Trigger: CHA rising, threshold 5000 ADC, no auto-trigger.
- Timebase 1; sample interval 2 ns; 100000 samples; 1000 pre-trigger samples.
- Normal: 100 accepted, 0 rejected.
- Swapped: 100 accepted, 0 rejected.

## Result

Sign convention: B minus A; positive means CHB arrived later. Splitter sign is
S2 minus S1.

- Normal mean B-A: `0.129250529 ns`
- Swapped mean B-A: `0.110702516 ns`
- PicoScope channel/path skew B-A: `0.119976522 ns ± 0.577372813 ns`
  standard uncertainty
- Splitter branch skew S2-S1: `0.009274007 ns ± 0.577372813 ns`
  standard uncertainty
- Normal repeatability, sample SD: `0.076662454 ns`
- Swapped repeatability, sample SD: `0.067346895 ns`
- Pooled within-orientation repeatability: `0.072155167 ns`

The uncertainty uses repository swap analysis with orientation standard errors
and the 2 ns sample-resolution term. Cable-reconnection repeatability was not
separately evaluated.

## USER_INPUT_REQUIRED

- PicoScope calibration-certificate uncertainty and exact equipment association
- CLOCK-SPLITTER-01 manufacturer specifications
- Separate cable-reconnection repeatability

## Restoration and final state

- Operator confirmed the installed EXT REF cable was restored to the fixed
  T660-2 CHA bulkhead.
- Operator confirmed CLOCK-SPLITTER-01 was restored to T660-2 CLOCK and its
  labeled 1.5-foot branches restored to T660-1 CLOCK and HF2LI CLOCK.
- The first two final readback attempts failed because the T660-2 RS-232 cable
  was physically unplugged. No output-enable command was sent during those
  failures.
- After the RS-232 cable was restored, final safe idle matched with no
  mismatches: both T660 trigger sources OFF and all eight outputs OFF.
- MS-02 and every later phase were not started.
