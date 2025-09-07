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

# Agent Instruction Guide & Development Phases

The application is a **modular monolith**: one backend server and one frontend app, composed of highly independent, self‑contained **mini‑apps** (“modules”)—one per device—plus an **Experiment** module for higher‑level orchestration.

> **Replit testing reality (hardware):** Replit cannot access physical hardware. Therefore, testing focuses on the **frontend→backend→controller dispatch path**. For each UI control (button/change), verify the corresponding backend endpoint is called with the correct payload and that the controller stub executes. Physical I/O calls are implemented but cannot be exercised from Replit. The user will test the provided code on the system physically connected to the devices and give feedback based on their experience. 

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

## Phase Triggers (verbatim commands for Replit)
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

## Notes for Local (non‑Replit) Testing
- Production hardware I/O requires correct drivers/SDKs and a compatible OS (e.g., Windows for some vendor DLLs).  
- While Replit validates **frontend↔backend** correctness, final verification with instruments must be performed on a host connected to the hardware with drivers installed.
