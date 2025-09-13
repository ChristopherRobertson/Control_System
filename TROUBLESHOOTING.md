**Troubleshooting Guide**

Use these checks when something does not work. Triage from general → device‑specific.

**General**
- **Backend running:** Start FastAPI (`uvicorn backend.src.main:app --reload`). Check `http://localhost:8000/health` returns `{"status":"healthy"}`.
- **Frontend running:** Start Vite (`npm run dev`). Open `http://localhost:5173` unless configured otherwise.
- **CORS:** Backend allows `*` by default; if you changed it, ensure the frontend origin is included.
- **Logs:** Watch the terminal running the backend for stack traces and device errors.
- **Ports in use:** Change ports or stop conflicting processes if 8000/5173 are busy.

**SDK/DLL Loading (Windows)**
- **Bitness:** Python must be 64‑bit if the vendor SDK is 64‑bit.
- **DLL search path:** For Windows SDKs, ensure `os.add_dll_directory(<sdk>\lib)` gets called before importing the SDK. See AGENT_INSTRUCTIONS.md Part 1D (SDK Path Resolution).
- **Environment overrides:** Set `<DEVICE>_SDK_PATH` env var (e.g., `PICO_SDK_PATH`) or update `hardware_configuration.toml` `sdk_path` to a valid location.
- **Permissions:** Install SDKs “for all users” when possible.

**PicoScope (PS5000A)**
- Error opening device: Verify PicoSDK is installed and the USB driver is not in use by PicoScope 6/7 app. Close vendor apps and retry.
- `picosdk` Python import fails: `pip install picosdk` into the same Python environment used by the backend.
- Missing DLLs: Confirm `C:\Program Files\Pico Technology\SDK\lib` exists and is added via `os.add_dll_directory` or set `PICO_SDK_PATH` to the SDK root.

**Daylight MIRcat**
- If using bundled SDK: Ensure `hardware_configuration.toml` `sdk_path` points to `./docs/sdks/daylight_mircat` and files exist.
- If using system SDK: Set `MIRCAT_SDK_PATH` or update `sdk_path` to the install location. Confirm serial COM port and baud match the controller.

**Zurich HF2LI**
- Install LabOne and the Python API. Ensure the device ID and server address are correct. Verify `zhinst` Python package is importable.

**Quantum Composers 9524 (Serial)**
- Port not found: Check Windows Device Manager (COMx) or `ls /dev/tty*` on Linux.
- Permission denied (Linux/macOS): Add user to `dialout` or use `sudo`, or fix udev rules.

**Frontend Symptoms**
- Connect button says Connected but device not in use: Backend stub likely returned success. Implement full SDK calls per AGENT_INSTRUCTIONS.md (no stubs).
- “Only one page shows”: Verify the router in `frontend/src/App.tsx` and Navbar entries. Hard refresh the browser.

**WebSocket**
- If the Waveform/Status does not update, check browser console for WS errors. Frontend points WS to the backend host (`/ws/{device}`). Ensure backend is reachable from the browser host.

**Data/Paths**
- Avoid user‑profile paths in config. Use env vars + relative paths as documented.

