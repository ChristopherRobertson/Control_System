# AGENT_INSTRUCTIONS.md

## Project Title
Unified Control Interface for IR Pump-Probe Spectroscopy System

## Core Objective
Develop a robust, user‑friendly application to control and synchronize all electronic components of a Pump‑Probe IR Spectroscopy system. The application features a **Python (FastAPI)** backend for hardware control and a modern **React + TypeScript** frontend to create an intuitive GUI with panels for each instrument, plus a sophisticated **Experiment** mode for orchestrating automated data acquisition runs using an **acquire‑then‑display** workflow.

> **Development Mode:** This codebase is intended to remain in a **perpetual development state** for easy duplication, upgrades (e.g., new instruments), and iterative improvement. Prefer extensibility and clean modularity over one‑off shortcuts.

## Core Technologies
- **Backend:** Python 3, **FastAPI** (single API server), hardware control libraries (e.g., `pyserial`, `pyvisa`, vendor SDKs).
- **Frontend:** React + TypeScript (MUI for UI components).
- **Version Control:** Git (single repository).

## Hardware Components
- **Arduino Uno R4 Minima** — MUX controller for sample positioning.  
- **Continuum Surelite Nd:YAG Laser** — Pump source (not computer‑connected; controlled via TTL from Signal Generator).  
- **Daylight MIRcat Laser** — Probe source.  
- **PicoScope 5244D** — Oscilloscope for alignment, calibration, and data collection.  
- **Quantum Composers 9524** — Signal Generator for system synchronization.  
- **Zurich HF2LI** — Lock‑in Amplifier for data collection.

> **Connectivity note:** All devices are USB‑connected **except** the Surelite Nd:YAG (no direct computer control; driven by TTL from the signal generator). Its should still have its own module in the user interface that allows modification of necessary parameters which are directed to the Signal Generator.

---

# AI Agent Instruction Guide & Development Phases

The application is a **modular monolith**: one backend server and one frontend app, composed of highly independent, self‑contained **mini‑apps** (“modules”)—one per device—plus an **Experiment** module for higher‑level orchestration.

> **AI Agent testing reality (hardware):** AI Agent cannot access physical hardware. Therefore, testing focuses on the **frontend→backend→controller dispatch path**. For each UI control (button/change), verify the corresponding backend endpoint is called with the correct payload and that the controller stub executes. Physical I/O calls are implemented but cannot be exercised from AI Agent. The user will test the provided code on the system physically connected to the devices and give feedback based on their experience. 

---

## Phase 0

### STEP 1: Document Analysis
**Goal:** Establish a solid foundation by analyzing existing documentation and preparing configuration scaffolding.

**Method:** Review all files in `/docs` (and subfolders). For each manual/guide/SDK/code sample, extract key info for the associated device:
- Communication protocols (SCPI, serial, TCP/IP, proprietary APIs).
- Connection parameters (COM port, baud, VISA resource, IP/port, driver names).
- Required drivers/SDKs (names, versions, 32/64‑bit).
- Control capabilities (callable functions/commands).
- Input parameters & their valid ranges (utilize screenshots to determine what needs to be included).

You may reorganize `/docs` for clarity (e.g., `/docs/manuals`, `/docs/sdks`, `/docs/screenshots`).

**Create**  
`ACTION_REQUIRED.md`—request any missing information and suggestions on where to find it. This includes valid ranges for input paramaters, DO NOT PUT PLACEHOLDER VALUES.

**Update**
`hardware_configuration.toml` (the configuration for all necessary parameters for the MIRcat has been completed as an example, the remaining devices still need to be completed)  


### STEP 2: Project Setup (Modular Skeleton)

#### Backend (`/backend`)
- **Single entrypoint:** `main.py` (FastAPI).  
- **Modules root:** `/backend/src/modules/`  
- **Per‑device package (snake_case):** `daylight_mircat`, `picoscope_5244d`, `zurich_hf2li`, `quantum_composers_9524`, `arduino_mux`, `continuum_ndyag`  
  Each device directory contains:
  - `__init__.py`
  - `controller.py` — high‑level control (e.g., `arm_laser()`, `set_wavelength()`).
  - `routes.py` — API endpoints for this device (`/api/{device}/...`).  
  - `sdk/` — vendor SDKs/DLLs/libs specific to this device.  
  - `utils.py` or `utils/` — helpers/parsers specific to this device.

##### Module auto‑discovery contract (required)
To ensure robust discovery without import‑time side effects, each module’s `routes.py` **must** expose:
```python
# routes.py
from fastapi import APIRouter, FastAPI

router = APIRouter(prefix="/api/daylight_mircat", tags=["daylight_mircat"])
# ... define @router.get/post/... endpoints here ...

def register(app: FastAPI) -> None:
    app.include_router(router)
```
`/backend/main.py` will iterate subfolders in `/backend/src/modules/`, import `<module>.routes`, and call `register(app)` if present.

#### Frontend (`/frontend`)
- **Single React app** mirroring backend modularity.
- **Modules root:** `/frontend/src/modules/` (PascalCase folders)
  - `DaylightMIRcat`, `PicoScope5244D`, `ZurichHF2LI`, `QuantumComposers9524`, `ArduinoMUX`, `ContinuumNdYAG`
  - Each contains:
    - `*View.tsx` — main composed view for the device.
    - `api.ts` — calls to `/api/{device}/...` endpoints.
    - `*.module.css` — scoped styles.
    - `components/` — reusable pieces scoped to the device.

- **Global UI:** `/frontend/src/components/global/` (e.g., `Navbar.tsx`, `Statusbar.tsx`, `MainLayout.tsx`).  
- **App shell & routing:** `App.tsx`, `main.tsx`, router configured for `/`, `/daylight_mircat`, `/picoscope_5244d`, `/zurich_hf2li`, `/quantum_composers_9524`, `/arduino_mux`, `/continuum_ndyag`.

#### WebSocket specification (global standard)
- **Endpoint:** `ws://<host>:<port>/ws/{device}` (e.g., `/ws/daylight_mircat`)
- **Message shape (server→client):** see original spec.
- **Message shape (client→server):** see original spec.

### STEP 3: Global Instructions
- If a parameter value or range is not stated in the provided documentation, **do not guess**.  
  - Put `USER INPUT REQUIRED` in `hardware_configuration.toml`.  
  - Add a precise request to `ACTION_REQUIRED.md` indicating what is missing and where it might be found.
- **Backend:** FastAPI. **Frontend:** TypeScript + React.
- Commit and push all created/reorganized files to the **main** branch.  
**This concludes Phase 0.**

---

## Phase 1: GUI Development

### Part A: Global GUI Design & Functionality Standards
- **Theme:** Dark mode by default (e.g., bg `#1e1e1e`, surfaces `#2a2a2a`, off‑white text, cyan/blue accents).  
- **Components:** MUI (Material UI), Material Icons.  
- **Layout:** Persistent **Navbar** (top), content area, **Statusbar** (bottom).  
- **UX:**
  - **Buttons:** pressed state; disabled **loading** state for in‑flight backend calls; on completion, show success/failure **toasts** and set the correct post‑action state.
  - **Inputs:** free typing; **validate on blur**; auto‑clamp to nearest valid value; always show helper text with valid range.
  - **Real‑time:** if a device disconnects, disable its controls and surface a clear indicator; status flows over **WebSocket** per spec.

### Part B: UI Skeleton & Component Scaffolding
0) **Providers:** Configure `theme.ts` (MUI dark theme) and a simple `AppContext` for global status/error messages.  
1) **Main layout:** `MainLayout.tsx` renders `Navbar`, routed content, `Statusbar`.  
2) **Navbar & Statusbar:** Use MUI `AppBar/Toolbar` and bottom‑docked bar; NavLinks for Dashboard + each device with active styling.  
3) **Placeholder panels:** Create per‑device `*View.tsx` placeholders (MUI Cards, titles, “Status: Disconnected”). Create a `DashboardView.tsx` with a grid of status cards.  
4) **Routing:** Map `/`→Dashboard, `/daylight_mircat`→`DaylightMIRcatView`, `/picoscope_5244d`→`PicoScope5244DView`, `/zurich_hf2li`→`ZurichHF2LIView`, `/quantum_composers_9524`→`QuantumComposers9524View`, `/arduino_mux`→`ArduinoMUXView`, `/continuum_ndyag`→`ContinuumNdYAGView`.  
5) **Commit message:**  
   `feat(frontend): static UI skeleton with navigation and placeholder panels`

### Part C: Replication of Manufacturer GUIs
0) **Module prep trigger:** “Prepare the <Device> module for development.”  
1) **Screenshot analysis:** Inspect `/docs/screenshots/<Device>/` to enumerate every control. Re‑organize logically.
   - **Top:** Mode Selection (e.g., Tune / Scan).  
   - **Middle:** Parameter Configuration.  
   - **Bottom:** Execution & State (Arm/Disarm, Emission On/Off).  
   Cross‑reference `/docs/manuals/` to map each control to precise commands/API.
2) **Config update:** Populate the `<device>` section in `hardware_configuration.toml` with parameters and **valid ranges**. If unknown, set to `USER INPUT REQUIRED` and add a matching entry in `ACTION_REQUIRED.md`.  
3) **Dependencies:** Identify required Python libs/SDKs; update `/backend/requirements.txt`.  
4) **Backend scaffolding:** In `controller.py`, create placeholder functions for **every** UI control; in `routes.py`, define matching endpoints; add `_broadcast_state_update()` stub.  
5) **Frontend scaffolding:** Replace placeholder content with static MUI controls mirroring the manufacturer UI; define `useState` vars; initialize from `hardware_configuration.toml` via props; ensure `Navbar` link exists.  
6) **Project management:** Clean `ACTION_REQUIRED.md` and set **Next Immediate Step** to implementing this device.  
   **Commit:** `feat(<Device>): scaffold module and config for GUI development`

### Part D: Module Implementation & Finalization (Live Code Edition)
1) **Backend implementation (`controller.py`):**
   - Implement `connect()` / `disconnect()` using `hardware_configuration.toml` and appropriate libraries.  
   - Implement getters/setters with exact command strings/APIs; parse responses; robust error handling.  
   - Implement `_broadcast_state_update()` to push fresh state; call after any successful mutation.
2) **Frontend wiring (`*View.tsx` / `api.ts`):**
   - Implement API calls; wire `onClick/onChange`; show loaders/toasts; enforce validation rules.  
   - Implement WebSocket listener per spec to keep UI in sync.
3) **Sanity check:** Style/architecture review, docstrings for Python, JSDoc for key TS functions; ensure both apps build without syntax errors.
4) **Handoff for live hardware testing:**  
   - Update per‑module README.md with notes and endpoint list.  
   - Update `TROUBLESHOOTING.md` with likely comms issues and fixes.  
   - In `ACTION_REQUIRED.md`, add **Live Hardware Test Plan for <Device>**.  
   - **Commit:** `feat(<Device>): implement full control panel for live testing`

### Part E: Device State Model, Persistence, and Code-Splitting (Generalized for All Devices)

Objective: Make every device module consistent, resilient, and sharable across pages (e.g., Experiment) without coupling to a single view. Code-splitting must not affect state retention.

Principles
- Single source of truth: Keep live device/session state in a top-level store (React Context or Zustand). Pages consume via hooks (e.g., `useDevice(<id>)`).
- Backend persistence: Store durable configuration and experiment definitions server-side; hydrate the client store on load and after mutations.
- Idempotent APIs: Commands like connect, arm, set-params should be safe to retry. Status polling or WebSocket updates reconcile view with reality.
- Toggle actions (single button UI): The UI SHOULD present a single toggle button for actions like Connect/Disconnect and Arm/Disarm. The backend MUST expose explicit, separate verbs (`POST /connect`, `POST /disconnect`, `POST /arm`, `POST /disarm`). Both UI and agents MUST choose which verb to call based on canonical state from `GET /status`, not on button label.
- UI guardrail (required): Disable the toggle button while a request is in flight to prevent rapid double toggles. Re-enable only after a response is received.
- Ownership boundaries:
  - Local UI: transient UI only (dialogs, local inputs).
  - Global store: live device state (connected, status, setpoints, last error). Survives navigation/lazy loading.
  - Backend DB/config: canonical configs and experiment recipes.
- Centralized polling/subscription: The provider handles polling or WS; pages never start their own redundant loops.

Frontend Contract (per device)
- `DeviceProvider` at app root: `<DeviceProvider>{children}</DeviceProvider>` for each device, or a generic `DevicesProvider` that registers all.
- Hook API: `useDevice(deviceId)` returns `{ state, actions }` with:
  - `state`: connected, status, current params, loading, error, timestamps.
  - `actions`: connect, disconnect, refreshStatus, setParams, start/stop ops.
- Lazy pages: Pages can be lazily loaded. Because state lives in providers, unmounting views will not drop device state.

Backend Contract (per device)
- Endpoints: `/api/<device>/{connect,disconnect,status,config,...}`.
- Status model: explicit booleans for connection/armed/emission, plus last_error/code.
- Persistence: `GET/POST /config` saves/loads durable settings. Server is authoritative across sessions.
- Broadcast: Optional WebSocket topic `<device>/state` pushes updates after mutations.

Implementation Steps (repeat for any device)
1) Store scaffolding: Create `frontend/src/state/<device>/context.tsx` with provider + reducer (or Zustand store). Export `use<Device>()` hook.
2) API wrapper: Define `frontend/src/modules/<Device>/api.ts` with typed models and calls.
3) Wire provider at root: Wrap `<App />` in `<DevicesProvider>` (or add per-device providers) in `frontend/src/main.tsx`.
4) Migrate view: Replace component-local state with the shared hook; remove per-page polling.
5) Persistence: On provider mount, load `GET /config` and `GET /status`; on mutations, `POST` then refresh status. Optionally mirror key fields to `localStorage` for UX continuity.
6) Code-splitting: Use `React.lazy` for heavy views; ensure providers are not lazy so state persists across navigation. Configure Vite `manualChunks` to split vendor bundles.
7) Validation: Build and navigate between modules to confirm state continuity and that Experiment page can read device state without MIRcat page mounted.

Notes
- Never keep the only copy of live state inside a page component.
- Favor typed API models; avoid redefining parallel interfaces in views.
- Prefer small, composable stores per device over a single large monolith; aggregate under `DevicesProvider` when convenient.

Deliverables
- Provider + hook per device.
- Updated views to consume shared state.
- Vite config with sensible vendor chunking and lazy-loaded routes or tabs.

Agent Integration
- Action selection: Agents MUST determine actions from canonical state via `GET /status` and invoke explicit verbs (`POST /connect`, `POST /disconnect`, `POST /arm`, `POST /disarm`, `POST /emission/on|off`). Do not infer from button labels or toggle text.
- Idempotency: Treat repeated verb calls as safe no-ops when the device is already in the requested state; return 200 with a clarifying message.
- Snapshot responses: Mutation endpoints SHOULD return the updated status snapshot payload alongside a message. Example: `{ message, ...status }`.
- Error semantics: Reserve non-2xx responses for real faults; return success for “already in target state”. Include `last_error` and `last_error_code` when applicable.

### Part F: Implement Real SDKs (No Stubs) — Generic Procedure

Use this checklisted procedure for any device module to replace placeholders with real hardware SDK calls. Apply the same pattern to oscilloscopes, lasers, signal generators, lock‑ins, and microcontrollers.

1) Prerequisites
- **Drivers/SDK installed:** Verify vendor driver + SDK installation and bitness (64‑bit Python ↔ 64‑bit SDK). Record location in `hardware_configuration.toml` (e.g., `sdk_path`).
- **Connectivity details:** Confirm resource (USB/serial/VISA/TCP/IP), permissions, and any prerequisites (e.g., WinUSB driver, NI‑VISA runtime).
- **Config contract:** Ensure the device section exists in `hardware_configuration.toml` with concrete values (no placeholders). Include `connection_type`, transport‑specific fields (e.g., `port`, `visa_resource`, `ip`, `baud_rate`), and `timeout`.

2) Backend — Replace Stubs With Real Calls
- **No unconditional success:** Remove code that sets state flags (e.g., `self.connected = True`) without an SDK call. Delete or rewrite any `# TODO` stubs that return success.
- **SDK loading:** Load the vendor SDK via official Python package or `ctypes`/`cffi` using the configured `sdk_path`. Fail fast with a clear error if the DLL/.so cannot be loaded.
- **Connect:** Call the vendor open/initialize function. On success, immediately query and store immutable info: `model`, `serial`, `firmware/driver_version`, `transport_details`. Only set `connected = True` when the SDK returns success and a valid handle.
- **Disconnect:** Call the vendor close/shutdown function and clear the handle/state. Always handle idempotently (double close is OK).
- **Status payload:** `get_status()` must return at minimum: `{ connected, acquiring, model, serial, driver_version, transport, last_error, last_error_code }`.
- **Operations:** Implement each controller method to map 1:1 to SDK functions (e.g., channel config, trigger, timebase, emission on/off). Validate inputs against `hardware_configuration.toml` ranges and translate enums to SDK constants.
- **Errors:** Check every SDK return code. On error, set `last_error`/`last_error_code`, log details, and raise an HTTP 4xx/5xx from the route with a concise message.
- **Threading/locks (if needed):** Serialize SDK access if the vendor requires single‑threaded calls; avoid GUI‑blocking waits by using async wrappers where appropriate.
- **No simulation pathway:** Remove or disable any `dry_run`, `simulate`, or mock branches in production code for this device. Tests may mock the SDK via dependency injection, but the shipped controller executes only real calls.

3) Routes — Truthful API Semantics
- **Idempotency:** `POST /connect` returns 200 with status when already connected; it must not flip state without verifying the device handle.
- **Snapshot responses:** Mutation endpoints return `{ message, ...status }` with the real, current status from the controller.
- **Meaningful failures:** Propagate SDK/open/permission errors via HTTP exceptions with clear text and (when available) vendor error codes.

4) Frontend — Reflect Real Hardware State
- **Trust but verify:** Treat the device as connected only if `connected === true` AND `serial` is present in the status.
- **Display device info:** Show `model`, `serial`, and `driver_version` in the header/statusbar.
- **Do not simulate UI state:** Remove any local toggles that imply success without waiting for the API response.
- **Error UX:** Surface backend messages for connection failures and configuration errors.

5) Configuration — Single Source of Truth
- Read all connection parameters from `hardware_configuration.toml`. Do not hardcode ports, VISA strings, or IPs in code.
- Keep per‑device enums/ranges in the TOML; validate user inputs against these on the backend before calling the SDK.

6) Validation Checklist (Device‑Agnostic)
- Connect:
  - SDK/DLL loads from `sdk_path`.
  - Open call returns success; a non‑null/valid handle is stored.
  - `get_status()` shows real `serial` and `model`.
- Operations:
  - Each endpoint triggers exactly one SDK call (or documented sequence) and checks the return code.
  - No `TODO`, `pass`, or unconditional `return True` remain in the controller.
  - Errors are surfaced with vendor code/message.
- Disconnect closes the handle and returns to a clean state.

7) Definition of Done (No Stubs Left)
- All placeholder/simulated code paths removed for the device.
- Controller methods contain only real SDK logic and input validation.
- API routes return truthful status derived from the SDK handle/state.
- Frontend reflects real connection by verifying presence of `serial` and shows device details.
- Documentation updated: required drivers, SDK version, and configuration fields listed in `ACTION_REQUIRED.md`/module README.

---

## Project Root Structure
```
/IR_Spectroscope_Control_Interface
├── .gitignore
├── hardware_configuration.toml
├── README.md
├── AGENT_INSTRUCTIONS.md
├── ACTION_REQUIRED.md
├── ARCHITECTURE.md
├── TROUBLESHOOTING.md
├── WISHLIST.md
│
├── backend/
│   ├── requirements.txt
│   └── src/
│     ├── main.py
│     └── modules/
│         ├── daylight_mircat/
│         ├── picoscope_5244d/
│         ├── zurich_hf2li/
│         ├── quantum_composers_9524/
│         ├── arduino_mux/
│         └── continuum_ndyag/
│
└── frontend/
    ├── package.json
    └── src/
        ├── App.tsx
        ├── main.tsx
        ├── index.css
        ├── components/
        │   └── global/
        │       ├── Navbar.tsx
        │       ├── Statusbar.tsx
        │       └── MainLayout.tsx
        └── modules/
            ├── DaylightMIRcat/
            ├── PicoScope5244D/
            ├── ZurichHF2LI/
            ├── QuantumComposers9524/
            ├── ArduinoMUX/
            └── ContinuumNdYAG/
```

---

## `hardware_configuration.toml` (canonical name)
Use TOML to store connection settings, parameter ranges, and enumerations per device. Completed for MIRcat as example.

---

## `ACTION_REQUIRED.md` (what to ask the user for)
Maintain this as a living checklist. At minimum, request the following per device when not in the docs:

- **Physical connection details:** COM ports / VISA resource strings / IP:port.  
- **Driver versions & links:** Exact driver package names and download sources.  
- **SDK bitness:** 64‑bit (must match Python process).  
- **Parameter ranges:** Verified min/max for each configurable parameter.  
- **Surelite mapping:** Which **Quantum Composers 9524** channel(s) generate the TTLs controlling the Nd:YAG (and any required pulse timing).

Also include a **Next Immediate Steps** section for the current phase/target device, and for Part D add a **Live Hardware Test Plan** checklist enumerating each control to exercise.

---

## Documentation Strategy
- **Layer 1: README.md** — 10,000‑ft overview; quick start.  
- **Layer 2: ARCHITECTURE.md** — “why” of the modular monolith; full directory trees; data‑flow; how to add a new device.  
- **Layer 3: Module‑level README.md** — one in each backend **and** frontend device folder (commands, quirks, endpoints/components).  
- **Layer 4: Code comments & docstrings** — Python docstrings for every controller function; JSDoc for critical TS functions; inline comments for intent.

---

## Phase Triggers (verbatim commands for AI Agent)
- **“Complete Phase 0”**  
- **“Complete Phase 1 – Part B”**  
- **“Prepare the MIRcat module for development”** *(or any device)*  
- **“Complete Part C for MIRcat”** *(or any device)*  
- **“Complete Part D for PicoScope”** *(or any device)*  
- **“Implement full control panel for live testing: <Device>”**

> Use these exact phrases to drive the step‑by‑step buildout.

---

## Quality & Naming Conventions (enforced)
- **Backend module folders:** `snake_case` — `daylight_mircat`, `picoscope_5244d`, `zurich_hf2li`, `quantum_composers_9524`, `arduino_mux`, `continuum_ndyag`.  
- **Frontend feature folders:** `PascalCase` — `DaylightMIRcat`, `PicoScope5244D`, `ZurichHF2LI`, `QuantumComposers9524`, `ArduinoMUX`, `ContinuumNdYAG`.  
- **Routes plugin contract:** each `routes.py` exposes `register(app: FastAPI) -> None`.  
- **WebSocket:** `/ws/{device}` with the schema above.  
- **Config filename (canonical):** `hardware_configuration.toml` used **everywhere**.

---

## Notes for Local (non‑AI Agent) Testing
- Production hardware I/O requires correct drivers/SDKs and a compatible OS (e.g., Windows for some vendor DLLs).  
- While the AI Agent validates **frontend↔backend** correctness, final verification with instruments must be performed on a host connected to the hardware with drivers installed.
