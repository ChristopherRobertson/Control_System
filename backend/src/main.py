"""
FastAPI main application for IR Pump-Probe Spectroscopy Control Interface
"""

import os
import importlib
import importlib.util
import pkgutil
import sys
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI(
    title="IR Spectroscopy Control Interface",
    description="Control interface for IR Pump-Probe Spectroscopy System",
    version="1.0.0"
)

# Configure CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auto-discover and register device modules
modules_path = Path(__file__).parent / "modules"
if modules_path.exists():
    # Ensure 'modules' can be imported as a package for relative imports in submodules
    if str(Path(__file__).parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).parent))
    if 'modules' not in sys.modules:
        spec = importlib.util.spec_from_file_location('modules', modules_path / '__init__.py')
        if spec and spec.loader:
            pkg = importlib.util.module_from_spec(spec)
            sys.modules['modules'] = pkg
            spec.loader.exec_module(pkg)
    for module_info in pkgutil.iter_modules([str(modules_path)]):
        module_name = module_info.name
        try:
            # Import routes as a proper package module to support relative imports
            routes_module = importlib.import_module(f"modules.{module_name}.routes")
            if hasattr(routes_module, 'register'):
                routes_module.register(app)
                print(f"Registered routes for module: {module_name}")
        except Exception as e:
            print(f"Failed to load module {module_name}: {e}")

@app.get("/")
async def root():
    return {"message": "IR Spectroscopy Control Interface API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API is running"}

# WebSocket endpoint for real-time device status updates
@app.websocket("/ws/{device_id}")
async def websocket_endpoint(websocket: WebSocket, device_id: str):
    await websocket.accept()
    # Stream live status for known devices; fall back to echo otherwise
    if device_id == 'daylight_mircat':
        try:
            # Lazy import to avoid circulars
            from modules.daylight_mircat.routes import mircat_controller
            while True:
                status = await mircat_controller.get_status()
                await websocket.send_text(json.dumps({
                    'device': device_id,
                    'type': 'status',
                    'payload': status
                }))
                await asyncio.sleep(0.5)
        except WebSocketDisconnect:
            print(f"WebSocket disconnected for device: {device_id}")
        except Exception as e:
            print(f"WebSocket error for {device_id}: {e}")
    else:
        try:
            while True:
                data = await websocket.receive_text()
                await websocket.send_text(f"Echo from {device_id}: {data}")
        except WebSocketDisconnect:
            print(f"WebSocket disconnected for device: {device_id}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
