Experiment development task prompts

These are complete, independent prompts to paste into new Codex tasks. They are development briefs derived from EXPERIMENTS.md and the current application; they do not replace scientific requirements or authorize instrument operation.

Run [00 — Shared experiment host](C:/Users/Chris/Documents/GitHub/Control_System/tmp/experiment_task_prompts_20260909/00_shared_experiment_host.md) once first. The current app hardcodes tab construction, lifecycle and hardware ownership, so six tasks editing those files simultaneously would conflict. Complete and integrate that foundation, including the current uncommitted working Phase Scan implementation, then create six isolated worktrees from the same resulting baseline and run tasks 01–06 in parallel. Each task owns its experiment package, tests and procedure; the foundation remains the sole owner of shared integration changes.

| Task | Full prompt | Single-detector tab | Dual-detector tab |
| --- | --- | --- | --- |
| 01 | [Steady-State Slow Scan](C:/Users/Chris/Documents/GitHub/Control_System/tmp/experiment_task_prompts_20260909/01_steady_state_slow_scan.md) | Slow Scan | Dual-Detector Slow Scan |
| 02 | [Fixed-Wavenumber Discovery and Recovery](C:/Users/Chris/Documents/GitHub/Control_System/tmp/experiment_task_prompts_20260909/02_fixed_wavenumber_kinetics.md) | Fixed-Wavenumber Kinetics | Dual-Detector Fixed-Wavenumber Kinetics |
| 03 | [Nanosecond Stroboscopic Reconstruction](C:/Users/Chris/Documents/GitHub/Control_System/tmp/experiment_task_prompts_20260909/03_nanosecond_stroboscopy.md) | Nanosecond Stroboscopy | Dual-Detector Nanosecond Stroboscopy |
| 04 | [Microsecond Stroboscopic Reconstruction](C:/Users/Chris/Documents/GitHub/Control_System/tmp/experiment_task_prompts_20260909/04_microsecond_stroboscopy.md) | Microsecond Stroboscopy | Dual-Detector Microsecond Stroboscopy |
| 05 | [Repeated Rapid-Scan Phase-Delay Reconstruction](C:/Users/Chris/Documents/GitHub/Control_System/tmp/experiment_task_prompts_20260909/05_repeated_rapid_scan.md) | Repeated Rapid-Scan Phase Delay | Dual-Detector Repeated Rapid-Scan Phase Delay |
| 06 | [Single-Pump Rapid Scan and Logarithmic Scan Bursts](C:/Users/Chris/Documents/GitHub/Control_System/tmp/experiment_task_prompts_20260909/06_single_pump_scan_burst.md) | Single-Pump Scan Bursts | Dual-Detector Single-Pump Scan Bursts |

The existing Phase Scan and Dual-Detector Phase Scan tabs implement the Single Scan Phase-Delay method (§8.4 / RT-Mb-R-S / ARC-RT-MB-SSP). Keep them as the reference and regression target rather than starting another task to rebuild them.

The five principal reconstruction architectures in §8 leave four new reconstruction tasks after excluding that existing method. The other two prompts cover the mandatory initial Slow Scan (§7) and supporting Fixed-Wavenumber Discovery/Recovery (§2 and §16.2). Fixed-wavenumber discovery is a supporting method, not an invented sixth principal reconstruction architecture.

Condition coverage:
- Slow Scan: separately identified RT HRP–CO, RT MbCO, 77 K HRP–CO and 77 K MbCO initial/state-verification spectra.
- Fixed-Wavenumber Kinetics: local discovery and selected-band recovery; no invented ARC identity.
- Nanosecond Stroboscopy: RT-HRP-G, RT-Mb-G, 77K-HRP-G-F, and the ns branch of 77K-Mb-G-F.
- Microsecond Stroboscopy: RT-Mb-R-K and the µs branch of 77K-Mb-G-F.
- Repeated Rapid-Scan Phase Delay: RT-HRP-NG.
- Single-Pump Scan Bursts: 77K-HRP-G-S and 77K-Mb-G-S.
Protein and temperature are condition profiles within a method. This produces 12 new top-level experiment tabs while preserving the existing two phase-scan tabs.

All prompts carry the same development boundaries, detector-normalization rules, app interaction requirements, data preservation and acceptance expectations. Separate namespaces and stable host interfaces remove routine shared-file edits and cross-experiment imports. Shared infrastructure is an intentional platform dependency; scientific calibration/reset/sample-state prerequisites also remain. Parallel development does not mean simultaneous control of the same physical apparatus: the host must enforce exclusive ownership across tabs and processes.

The intended routine experience is to load the required blank/sample, select the condition/settings, review the preliminary result and explicitly start. That becomes a commissioned workflow only after the relevant installed-system capabilities and calibration are available. The prompts require complete software and simulated verification without inventing optical time zero, nanosecond resolution, automatic thermal reset, position hardware, or normalization calibration. Physical actions that the installed apparatus cannot automate remain explicit.

No experiment tasks have been started and no application code or instrument settings have been changed by preparing these briefs.
