**Wishlist / Backlog**

- PicoScope acquisition:
  - Implement block and streaming modes (ps5000aRunBlock / buffers).
  - Channel range auto‑setup and per‑channel offset.
  - Waveform visualization (basic canvas) and CSV export.
- MIRcat:
  - Full tune/sweep/step/multi‑spectral flows with validation from TOML ranges.
  - Safety interlock state reflect + temperature trend.
- Zurich HF2LI:
  - Core control (frequency, time constant, input range) and demod readout.
  - Data streaming bridge for Experiment page.
- Quantum Composers 9524:
  - Complete serial protocol mapping; per‑channel templates.
  - Saved presets for Nd:YAG sequences.
- Arduino MUX:
  - Position map editor; homing/limits support.
- Experiment Orchestrator:
  - Recipe runner to coordinate MIRcat tuning, QC pulses, PicoScope capture, HF2LI readout.
  - Progress UI + log export.
- State Provider:
  - Migrate device views to global providers/hooks so Experiment can consume live state.
- CI / DevX:
  - Add lint/format tasks and simple integration smoke tests.
  - Provide example `.env` for environment variables (e.g., `<DEVICE>_SDK_PATH`).

