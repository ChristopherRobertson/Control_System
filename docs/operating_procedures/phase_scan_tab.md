# Phase Scan tab

The **Phase Scan** tab plans the room-temperature MbCO single-scan phase-delay
measurement. Opening the tab, editing controls, and saving a plan never access
hardware. **Start Scan** and **Abort Scan** are visibly disabled until the
acquisition workflow is connected. They do not run a simulation or stop other
tabs' instruments. Existing device Safe Idle and application shutdown controls
remain unchanged.

The intended detector connections follow the
[default wiring](../../instrument/default_wiring_state.md): each signal uses a
female-to-female BNC adapter -> male-to-two-female BNC tee, with sample feeding
HF2LI Signal 1 In (+)/PicoScope CHA and reference feeding HF2LI Signal 2 In (+)/
PicoScope CHB. Both receivers remain connected in normal operation. Planning a
scan does not verify or qualify this physical configuration.

## Controls and derived values

- **Probe Repetition Rate** and **Probe Pulse Width** describe the MIRcat probe,
  not the pump. Their product gives the nominal probe duty cycle. The planner
  checks the existing 30% ceiling; a valid plan does not establish that a
  particular module supports every requested rate, width, speed, or wavenumber.
- **Start Wavenumber**, **Stop Wavenumber**, and **Scan Speed** determine the
  nominal scan duration `T = abs(stop - start) / speed` and scan direction.
- **Phase Delay** is the increment `Δ` in scan-start delay relative to each
  event's pump. The current convention is `0, Δ, 2Δ, ... < T`, giving
  `ceil(T / Δ)` pumped phases. The preview displays this convention explicitly.
- **Rest Period** is the minimum pump-to-pump interval, not an additional sleep
  after a scan. It must accommodate the latest phase delay plus the complete
  scan, and respect the installed 10 Hz pump limit. It does not prove sample
  reset. The duration preview budgets one such slot per record, including
  baselines, without a trailing rest; preparation, return, settling, and
  additional sample recovery can extend the actual duration.
- **Repetitions** repeats the entire set. Each set begins with one unpumped
  baseline, followed by exactly one scan per pumped phase. Matching phases
  across sets are intended to be averaged while preserving all native records;
  the planner itself does not acquire or average data.

For 2000 → 1900 cm⁻¹ at 10,000 cm⁻¹/s, `T = 10 ms`. A 5 µs increment gives
2,000 pumped scans at 0 through 9,995 µs plus one unpumped baseline: **2,001
records per repetition**. Two repetitions therefore plan 4,002 records,
including two baselines and 4,000 pump events. At a 1 s rest interval the
one-repetition cadence budget is about 33 min 20 s before additional overhead.

The baseline has no pump time; it is not the pumped zero-delay record. Phase
counts use exact decimal-input arithmetic, and the preview/export remain
bounded in size for very fine phase increments.

**Save Plan** exports a versioned JSON description with settings, derived
counts, sequence rules, UTC save time, and explicit planning-only status.
Changing a control clears the saved-plan message; it does not change an already
exported plan or enable execution.

## Latest scan plot

The plot displays **Absorption** on the Y-axis and **Wavenumber (cm⁻¹)** on
the X-axis, decreasing from left to right. Each received scan replaces the
previous trace; this display does not average repetitions. Axes scale to the
received data, and invalid samples appear as gaps. Editing planning controls
does not relabel or erase the latest received spectrum.

Before data arrives, the plot shows the requested wavenumber interval and
“Waiting for latest scan,” with no synthetic spectrum. The phase sequence is
available through **Show phase sequence** so the spectrum has more room.
Acquisition integration can supply paired wavenumber/absorption arrays through
`PhaseScanWidget.set_latest_scan(...)`, or emit `latest_scan_received` from a
worker. Absorption must already be computed by the processing layer; the plot
does not interpret detector voltages as absorption or invent a normalization.

## Inputs still needed for acquisition

The timing controls cannot determine QCL coverage and drive current, detector
and acquisition settings, filter response, timing corrections, or safe optical
pump/probe exposure. These belong in an explicitly selected instrument preset
using promoted runtime bundles where applicable. A live workflow also needs
exclusive device ownership, interruptible acquisition, verified finite pump
events, raw-data retention, readiness/reset checks, and safe abort and shutdown.

A signed initial phase offset would extend the current zero-based grid to
scan-before-pump and pump-crossing controls. The plan uses nominal scan timing
only; reconstruction must use measured scan and pump timing.
The phase increment alone does not establish temporal resolution.

The scientific method and control requirements remain in
[EXPERIMENTS.md §10.4](../../EXPERIMENTS.md#104-rt-mb-r-s-supporting-single-scan-phase-delay-reconstruction).
This UI addition does not change qualification, campaign, or promotion status.
