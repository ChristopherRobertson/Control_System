IR Spectroscopy Control Interface

Overview
- Unified control interface for an IR Pump‑Probe Spectroscopy system.
- Backend: Python 3 + FastAPI. Frontend: React + TypeScript (MUI).
- Modular device architecture: MIRcat, PicoScope 5244D, Zurich HF2LI, Quantum Composers 9524, Arduino MUX, Continuum Nd:YAG (TTL via QC 9524).

Quick Start
- Prereqs: Python 3.11+, Node 18+, vendor SDKs (as needed per device).
1) Backend
   - cd backend
   - pip install -r requirements.txt
   - uvicorn src.main:app --reload
   - Health check: http://localhost:8000/health
2) Frontend
   - cd frontend
   - npm install
   - npm run dev
   - Open: http://localhost:5173

Config
- hardware_configuration.toml holds all device connection settings and parameter ranges.
- Avoid user‑profile paths; prefer relative paths and env vars.

SDK Path Resolution (All Devices)
- Controllers resolve SDKs in this order:
  1. Env var <DEVICE>_SDK_PATH (e.g., PICO_SDK_PATH).
  2. sdk_path from hardware_configuration.toml (relative allowed).
  3. OS defaults (e.g., Windows %ProgramFiles%/Pico Technology/SDK).
- Windows: controllers add os.add_dll_directory(<path>) before importing SDKs.

Routes (per device)
- POST /api/<device>/connect — open the device; returns { message, ...status }.
- POST /api/<device>/disconnect — close the device; returns status.
- GET  /api/<device>/status — current snapshot (connection, params, last_error).
- Additional endpoints: channel/timebase/trigger/etc. as appropriate.

WebSocket
- ws://<host>:8000/ws/<device> streams status snapshots used for live indicators.

Troubleshooting
- See TROUBLESHOOTING.md for SDK/DLL, serial ports, and WebSocket guidance.

Contributing
- Follow module conventions (backend/src/modules/<device>, frontend/src/modules/<Device>).
- Implement real SDK calls. No stubbed success in controllers.
- Update ACTION_REQUIRED.md with any missing lab inputs (user tasks only).

License/Distribution
- Internal lab use only. If bundling vendor SDK files, ensure compliance with vendor terms.

