**Architecture Overview**

This project is a modular monolith: a single FastAPI backend and a single React + TypeScript frontend. Each device is an independent module on both sides, wired together via REST and optional WebSocket updates.

**Backend (Python/FastAPI)**
- Entry: `backend/src/main.py` — starts FastAPI, configures CORS, and auto‑registers device routes from `backend/src/modules/*/routes.py`.
- Per‑device module (snake_case): `backend/src/modules/<device>/`
  - `controller.py` — Implements real SDK calls (no stubs). Holds live state and exposes methods like `connect()`, `set_params()`, `start()`, etc.
  - `routes.py` — REST API mapping to controller methods and `/status` endpoint. Exposes `register(app)` for discovery.
  - `sdk/` (optional) — for bundled SDK files if redistribution is allowed/desired.
- Status broadcasting: optional WebSocket on `/ws/{device}` for periodic status snapshots.
- Config: `hardware_configuration.toml` is the single source of truth for connection settings and parameter ranges.

Device SDK Path Resolution (Windows-first pattern, portable)
- Controller must resolve SDK location in this order:
  1. Environment variable `<DEVICE>_SDK_PATH` (e.g., `PICO_SDK_PATH`).
  2. `sdk_path` from `hardware_configuration.toml` (relative paths allowed).
  3. Known OS defaults (e.g., `%ProgramFiles%/Pico Technology/SDK`).
- On Windows call `os.add_dll_directory()` for each candidate before importing the SDK.
- Never hardcode `C:\Users\<name>`.

**Frontend (React/TypeScript/MUI)**
- Entry: `frontend/src/main.tsx` (theme + router), `frontend/src/App.tsx` (routes), `components/global/*` (Navbar, Statusbar).
- Per‑device feature folder (PascalCase): `frontend/src/modules/<Device>/`
  - `api.ts` — Typed API client for the device routes.
  - `*View.tsx` — UI for the device; calls API and optionally subscribes to WebSocket for live status.
- Dashboard: `frontend/src/components/DashboardView.tsx` summarizes device entry points.

**API Conventions**
- `/api/<device>/connect|disconnect|status|...` — explicit verbs; idempotent.
- Mutation endpoints return `{ message, ...status }`.
- Errors return structured HTTP errors; controller sets `last_error` and `last_error_code` when relevant.

**Data/State Flow**
- UI triggers API calls → controller updates state → routes return a snapshot → UI renders → optional WS keeps UI fresh.

**Extending the System**
1. Create a new backend module (`controller.py`, `routes.py`) and register routes via `register(app)`.
2. Add a frontend module (`api.ts`, `*View.tsx`) and a Navbar link.
3. Add config to `hardware_configuration.toml` with ranges and enumerations.
4. Implement SDK path resolution as above. Verify connect/disconnect.

