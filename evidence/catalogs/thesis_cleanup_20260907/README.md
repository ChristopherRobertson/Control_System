# Thesis evidence cleanup — 2026-09-07

User-authorized removal of failed/superseded development payloads to recover disk space. This specific instruction overrides older blanket retention instructions for the listed files only. No hardware actions, phase acceptance changes, or promotion occurred.

Historical manifests and reports describe the original acquisitions. Their retention assertions must be read with deletion_plan.csv and deletion_results.csv; removed native data cannot be reanalyzed. Failure logs, settings, summaries, scripts and accepted replacements remain. Reasons that were not recorded remain unknown.

## Failure and remedy record

### evidence/experiments/runs/authorized_mbco_phase_reconstruction_20260904T002152_3132654Z/Phase Scan

Failed startup: LASER_NOT_TUNED

Recorded subsequent action: Later attempts changed tuning/startup sequence; see subsequent launcher scripts and results.

Source: evidence/experiments/runs/authorized_mbco_phase_reconstruction_20260904T002152_3132654Z/Phase Scan/ (result.json, launcher_result.json, progress.txt)

### evidence/experiments/runs/authorized_mbco_phase_reconstruction_20260904T002152_3132654Z/retry_01_20260904T002525_6487854Z

Failed: multiple QCL sweeps after one process trigger

Recorded subsequent action: Later attempts replaced per-record operation with externally triggered consecutive sweeps.

Source: evidence/experiments/runs/authorized_mbco_phase_reconstruction_20260904T002152_3132654Z/retry_01_20260904T002525_6487854Z/ (result.json, launcher_result.json, progress.txt)

### evidence/experiments/runs/authorized_mbco_phase_reconstruction_20260904T002152_3132654Z/retry_02_20260904T002907_3724697Z

Incomplete: operator explicitly stopped per-record retuning for replacement with consecutive externally triggered sweep

Recorded subsequent action: Result records the reason for stop; subsequent retries use consecutive DDG scheduling.

Source: evidence/experiments/runs/authorized_mbco_phase_reconstruction_20260904T002152_3132654Z/retry_02_20260904T002907_3724697Z/ (result.json, launcher_result.json, progress.txt)

### evidence/experiments/runs/authorized_mbco_phase_reconstruction_20260904T002152_3132654Z/retry_03_consecutive_ddg_20260904T011613_6295456Z

Failed: compound T660 command returned only two responses for fourteen commands

Recorded subsequent action: Subsequent buffered command implementation is retained in retry_04 and retry_06 scripts.

Source: evidence/experiments/runs/authorized_mbco_phase_reconstruction_20260904T002152_3132654Z/retry_03_consecutive_ddg_20260904T011613_6295456Z/ (result.json, launcher_result.json, progress.txt)

### evidence/experiments/runs/authorized_mbco_phase_reconstruction_20260904T002152_3132654Z/retry_04_buffered_consecutive_ddg_20260904T012240_7263264Z

Aborted development attempt; missing-pulse retries continued and completion was not verified

Recorded subsequent action: Later attempt changed to buffered single-rearm DDG; retry_06 and its derived reconstruction are retained for human review. Exact operator reason for this abort is not recorded and is not inferred.

Source: evidence/experiments/runs/authorized_mbco_phase_reconstruction_20260904T002152_3132654Z/retry_04_buffered_consecutive_ddg_20260904T012240_7263264Z/ (result.json, launcher_result.json, progress.txt)

### campaigns/instrument_readiness_001/phases/T1-01/setup_1_extref_to_fire/rejected_initial_wiring

300 rejected initial-wiring traces; zero accepted at this setup

Recorded subsequent action: Corrected wiring was acquired separately and supplies the accepted result; precise undocumented wiring fault remains unknown.

Source: campaigns/instrument_readiness_001/phases/T1-01/procedural_writeup.md, rejected_initial_wiring/status.json

### campaigns/instrument_readiness_001/phases/HF-01

Selected rejected DIO export, pulse-width, poll-window, unlocked-clock and detuned-reference raw records only. Lower-rate boundary tests and slow-settling failure remain for review.

Recorded subsequent action: Accepted timing R5 and corrected-reference response acquisitions remain. Exclusion ledger contains per-attempt causes, amendments and replacement IDs.

Source: exclusions.csv and procedural_writeup.md

### evidence/experiments/runs/authorized_air_scan_after_detector_recovery_20260903T213002_3743882Z/mircat_sweep_20260903T213017_174260Z

Failed startup: MircatCommandError('MIRcatSDK_StartSweepScan returned 95 (TECS_NOT_AT_SET_TEMPERATURE)')

Recorded subsequent action: Retained subsequent attempts and configuration records document recovery. TEC failures require settling; manual-tune/startup correction is documented in exploratory_air_checkout failure_analysis.json. No new cause or successful outcome is inferred.

Source: evidence/experiments/runs/authorized_air_scan_after_detector_recovery_20260903T213002_3743882Z/mircat_sweep_20260903T213017_174260Z/result.json

### evidence/experiments/runs/authorized_mbco_phase_reconstruction_20260904T002152_3132654Z/Phase Scan/2026-09-04/20260904T002309_270337Z_run

Failed startup: MIRcatSDK_TurnEmissionOn returned 94 (LASER_NOT_TUNED)

Recorded subsequent action: Retained subsequent attempts and configuration records document recovery. TEC failures require settling; manual-tune/startup correction is documented in exploratory_air_checkout failure_analysis.json. No new cause or successful outcome is inferred.

Source: evidence/experiments/runs/authorized_mbco_phase_reconstruction_20260904T002152_3132654Z/Phase Scan/2026-09-04/20260904T002309_270337Z_run/result.json

### evidence/experiments/runs/direct_air_external_pulse_20260903T024207_749523Z/acquisition_20260903T024213_710724Z

Failed startup: MircatCommandError('MIRcatSDK_StartSweepScan returned 95 (TECS_NOT_AT_SET_TEMPERATURE)')

Recorded subsequent action: Retained subsequent attempts and configuration records document recovery. TEC failures require settling; manual-tune/startup correction is documented in exploratory_air_checkout failure_analysis.json. No new cause or successful outcome is inferred.

Source: evidence/experiments/runs/direct_air_external_pulse_20260903T024207_749523Z/acquisition_20260903T024213_710724Z/result.json

### evidence/experiments/runs/direct_air_reset_explicit_on_three_modes_20260903T025720_147056Z/02_external_trigger/acquisition_20260903T025829_924698Z

Failed startup: MircatCommandError('MIRcatSDK_TurnEmissionOn returned 94 (LASER_NOT_TUNED)')

Recorded subsequent action: Retained subsequent attempts and configuration records document recovery. TEC failures require settling; manual-tune/startup correction is documented in exploratory_air_checkout failure_analysis.json. No new cause or successful outcome is inferred.

Source: evidence/experiments/runs/direct_air_reset_explicit_on_three_modes_20260903T025720_147056Z/02_external_trigger/acquisition_20260903T025829_924698Z/result.json

### evidence/experiments/runs/exploratory_air_checkout_20260902T224505_935642Z/Phase Scan/2026-09-02/20260902T224603_439271Z_background

Failed startup: MIRcatSDK_StartSweepScan returned 71 (START_SWEEPSCAN_FAILURE)

Recorded subsequent action: Retained subsequent attempts and configuration records document recovery. TEC failures require settling; manual-tune/startup correction is documented in exploratory_air_checkout failure_analysis.json. No new cause or successful outcome is inferred.

Source: evidence/experiments/runs/exploratory_air_checkout_20260902T224505_935642Z/Phase Scan/2026-09-02/20260902T224603_439271Z_background/result.json

## Human review

human_review_queue.csv lists uncertain operational evidence in descending retained size. No assumption that a publication_eligible=false flag alone makes scientific data disposable was used. Successful capacity tests, high-rate loss diagnostics supporting the rate limit, spectra, blanks and reconstruction inputs remain pending review. Registered accepted readiness measurements and phase documentation remain.

The first item is the earlier MbCO phase reconstruction: retry_06 supplies its saved derived reconstruction and remains intact. Earlier failed/superseded attempts listed in the deletion ledger were removed.

Files were individually selected; no broad recursive directory deletion or Git history rewriting is performed.

## Cleanup paused at user request

Completed through R012. Total removed: 70.131 GB across 12,640 files. User-confirmed keep decisions and unreviewed items remain. Continue only when requested; next pending review is R013. Per-review deletion ledgers and verification files supplement the initial bulk ledger.
