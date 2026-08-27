# HF-01 electrical parameter characterization

This is the stable evidence directory for HF-01 of campaign
`system_recalibration_001`. The phase is an electrical-only calibration of
HF2LI `dev18500` using the monitored PicoScope 5244D generator and T660-2
timing copies. No laser arming, firing, optical emission, shutter opening,
optical alignment, sample work, or biological work is permitted.

- Phase run: `system_recalibration_001_HF-01_001`
- Authorization: `HF01-AUTH-001`
- Status: `PASS` with an explicit MbCO applicability limitation
- Promotion: prohibited unless separately and explicitly authorized
- Next phase: none; execution stops at the HF-01 boundary

All physical work is operator-led. Under `HF01-AUTH-AMEND-001`, routine
inspection and wiring instructions may be batched; explicit confirmation is
still required before first nonzero generator enable and before restoration is
accepted. A physical state is accepted only from an operator observation
recorded in `action_ledger.csv`.
The prior phase did not supply a current final observation of all laser and
shutter states, so HF-01 begins with fresh observations and makes no inference
from silence or old evidence.

The installed `CLOCK-SPLITTER-01` distribution is unchanged throughout. The
temporary stimulus tee and two retained RG-58 cables receive stable IDs only
after operator inspection. Programmed generator voltage is never the stimulus
authority; the connected PicoScope channel-A measurement is.

No object hash or checksum is an operational gate. Stable IDs, relative paths,
device/component identities, UTC timestamps, versions, source records, branch,
and dirty-file lists provide provenance.

The corrected timing result is `HF01-TIMING10-R5-001`. The governing response
method is the prospective paired-demodulator plan `HF01-PLAN-v3` under
`HF01-AUTH-AMEND-005` and `HF01-MODEL-RESIDUAL-v3`. Demodulator 0 is the filter
under test and demodulator 1 is a synchronized wideband reference on the same
input and HF2LI clock domain. One bounded constant paired-pipeline delay per
anchor is reported and removed before phase and group-delay comparison. Earlier
v1/v2 records remain preserved as superseded evidence. The accepted fast,
intermediate, and slow-repeat v3 anchors all pass. The complete installed
parameter space was then evaluated computationally, the selected and immediately
lower rates were confirmed, both signal inputs passed equivalence, range
endpoints passed, and all three restorable configuration IDs passed reload
equivalence.

Selected configuration IDs:

- `HF01-SWEEP-SELECTED-001`: order 4, 1.0018887 ms, 899.46546 Sa/s.
- `HF01-HRP-SELECTED-001`: explicit numeric alias of the sweep setting with a
  separate HRP validity envelope.
- `HF01-MBCO-SELECTED-001`: order 1, 5.6000175 us, 230263.1579 Sa/s, retained
  only as the fastest valid two-channel boundary. It is not valid for the
  mandatory 1 us MbCO claim.

Default wiring was operator-confirmed in `HF01-OPCONF-014`. Final acquisition
`HF01-FINAL-RESTORATION-STATE-R1-001` confirms T660 safe idle, PicoScope AWG
zero, exact HF2LI prechange settings, locked external master clock, outputs off,
and clean clip/loss flags. The preceding COM3-contention attempt is preserved
as rejected evidence. See `final_report.md`, `restoration_confirmation.json`,
and `retention_audit.md` for closeout. No later phase or promotion was performed.
