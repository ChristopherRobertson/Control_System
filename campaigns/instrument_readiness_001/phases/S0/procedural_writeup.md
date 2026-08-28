# S0 — safe-idle and interlock verification: procedural writeup

## Document control

| Field | Value |
| --- | --- |
| Canonical campaign ID | `instrument-readiness-001` |
| Phase ID | `S0` |
| Phase run ID(s) | No stable phase-run ID is present in the retained S0 record. |
| Domain | Calibration/readiness foundation |
| Scientific disposition | `PASS — COMPLETE` |
| Documentation status | `DRAFT_RECONSTRUCTION_REVIEW_PENDING` |
| Preparation mode | `RETROSPECTIVE_EVIDENCE_RECONSTRUCTION` |
| Operator | Christopher Robertson |
| Draft author | Codex, from retained repository evidence |
| Reviewer | Not assigned; review remains pending. |
| Document version | `0.1.0` |
| Execution interval (UTC) | 2026-07-24T18:52:27Z to 2026-07-24T18:52:41Z |
| Draft date | 2026-08-27 |
| Governing records | `plan.md`; `run_record.md`; `s0_record.json`; `recipes/safe_idle.yaml` |

## Executive synopsis

S0 tested whether hardware measurements could begin from a known, inhibited,
recoverable state. The operator confirmed physical inhibits and standing wiring
exclusions; the control procedure then verified T660 identities, disabled states,
MIRcat safety state, and ownership cleanup without moving cables, enabling
outputs, arming a laser, or emitting light.

The run passed. Both T660s identified correctly and reported firmware
`28E660-1-1.7`; both trigger sources and all eight channels were off. MIRcat was
connected only for bounded status readback and was emission-off and disarmed.
The main limitation is that S0 demonstrates the recorded safe-idle configuration
at one execution, not permanent safety or performance under every later setup.

## 1. Purpose — WHY

Subsequent electrical calibration required exclusive device ownership and a
verified safe state. Merely assuming that outputs were disabled could expose
equipment to unintended triggers or make measurements irreproducible. S0 was
therefore the transition from P0's documentary inventory to hardware-access
readiness.

The acceptance question was whether physical inhibits, device identities,
T660 disabled-state readbacks, MIRcat safety readbacks, and final ownership
release all agreed with the safe-idle recipe. S0 did not authorize rewiring,
signal generation, optical emission, or MS-01 acquisition.

## 2. Procedure performed — HOW

### 2.1 Entry state and topology

The normal installed wiring was left untouched. The operator confirmed the room
interlock and laser inhibits, normal clock distribution, fixed bulkheads, T660-1
channel D disconnected, MIRcat DB9 pin 5 disconnected, pins 6 and 8 unwired, the
Arduino MUX disabled, and competing clients closed. These confirmations and the
machine readbacks are preserved in `s0_record.json`.

### 2.2 Chronological reconstruction

| Step | Action actually performed | Purpose and decision rule | Evidence | Outcome |
| ---: | --- | --- | --- | --- |
| 1 | The operator confirmed the physical inhibits, wiring exclusions, clock splitter state, and closed-client condition. | Establish a safe boundary before device access. | `s0_record.json`; `run_record.md` | Preconditions were confirmed without cable movement. |
| 2 | Each T660 was placed or retained in STOP with trigger source OFF and channels A–D OFF before identity queries. | Prevent identity access from occurring with an active output state. | `s0_record.json`; `t660_preidentity_disabled_readback.json` | Both devices reported all outputs and trigger sources off. |
| 3 | T660 identity and firmware queries were issued to the two configured serial ports. | Verify that device ownership and logical names matched the physical inventory. | `t660_identity_firmware.json`; `s0_record.json` | T660-1 returned serial `00369`; T660-2 returned serial `00431`; both returned firmware `28E660-1-1.7`. |
| 4 | MIRcat ownership was acquired for status-only inspection. | Confirm that the installed source could be queried while remaining inhibited. | `mircat_identity_firmware.json`; `s0_record.json` | Model/serial and SDK information were recorded; emission and armed state were false, interlock/key readbacks were true, and scan state was false. |
| 5 | The safe-idle recipe was reapplied and read back. | Require direct agreement with the repository recipe before cleanup. | `t660_safe_idle_command_readback.json`; `s0_record.json` | The recipe matched with no mismatches. |
| 6 | Device ownership was released and clients were closed. | Leave the system recoverable and available for the next separately authorized phase. | `s0_record.json`; `command_log.txt` | Cleanup completed; no output-enable or emission command was used. |

### 2.3 Acquisition and analysis design

S0 was a state-verification phase rather than a waveform acquisition. The direct
observations were operator confirmations and device readbacks. The analysis was
categorical: identity tokens had to match the P0 inventory, each T660 trigger and
channel state had to be off, MIRcat had to remain nonemitting and disarmed, and
the final recipe comparison had to contain no mismatches.

### 2.4 Deviations and restoration

No cable, MUX, channel-enable, trigger, arm, emission, or laser command was
performed. No deviation requiring a replacement run is recorded. The final
safe-idle application and ownership release served as restoration because the
physical topology was never changed.

## 3. Results — WHAT

- Run status: `PASS`.
- T660-1 identity: `HTI,T660-1,00369,28E660-1-1.7`.
- T660-2 identity: `HTI,T660-2,00431,28E660-1-1.7`.
- Initial and final T660 state: both trigger sources OFF and all eight channels
  OFF.
- MIRcat status: connected for readback, emission false, armed false, scan false;
  interlock/key safety readbacks true.
- Physical topology: normal wiring retained, specified unused/disconnected paths
  confirmed, MUX disabled.
- Cleanup: ownership released with no output or emission action.

The evidence population consists of one bounded state-verification run with
operator confirmations and machine readbacks. No waveform, optical, sample, or
performance measurement was attempted.

## 4. Implications, caveats, and claims

### Supported claims

S0 supports the bounded claim that, during the recorded interval, the identified
T660 and MIRcat devices were accessible under exclusive control and agreed with
the stated safe, inhibited configuration. It also establishes the firmware
identity used by later timing phases.

### Unsupported or prohibited claims

S0 does not calibrate delay, amplitude, interlock response time, optical output,
or device reliability. A passing state snapshot does not guarantee that later
rewiring or software activity preserves safe idle; every later phase must perform
its own entry and restoration checks.

### Downstream implications

The pass allowed MS-01 to be considered for separate authorization. Later phases
may import the stable device identities and safe-idle recipe, but must record
their own ownership, topology, readbacks, and final state.

## 5. Reproducibility and source map

| Narrative item | Primary retained source | Reproduction note |
| --- | --- | --- |
| Complete event/state record | `s0_record.json` | Treat machine readbacks and timestamps as authority. |
| T660 identities | `t660_identity_firmware.json` | Match logical device names and serials; do not collapse the two T660 units. |
| MIRcat identity/state | `mircat_identity_firmware.json`; `s0_record.json` | Interpret as status-only evidence. |
| Safe-idle comparison | `t660_preidentity_disabled_readback.json`; `t660_safe_idle_command_readback.json` | Compare explicit state fields to the recorded recipe; do not use hashes as a gate. |
| Cleanup/restoration | `s0_record.json`; `command_log.txt` | Confirm ownership release and that no physical topology change was introduced. |

Minimal reproduction is a read-only review of the retained JSON records and
command log. Re-executing hardware is neither necessary nor authorized by this
writeup.

## 6. Review record

| Review | Reviewer | UTC date | Outcome | Comment |
| --- | --- | --- | --- | --- |
| Evidence traceability | Not assigned | Pending | `PENDING` | Verify the chronological summary against `s0_record.json`. |
| Technical/scientific | Not assigned | Pending | `PENDING` | Confirm the bounded safe-state interpretation. |
| Thesis readiness | Not assigned | Pending | `PENDING` | Editorial integration remains outstanding. |
