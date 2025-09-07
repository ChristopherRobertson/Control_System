"""
FastAPI main application for IR Pump-Probe Spectroscopy Control Interface
"""

import os
import importlib
import importlib.util
import pkgutil
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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
    for module_info in pkgutil.iter_modules([str(modules_path)]):
        module_name = module_info.name
        try:
            # Import the module
            spec = importlib.util.spec_from_file_location(
                f"modules.{module_name}.routes",
                modules_path / module_name / "routes.py"
            )
            if spec and spec.loader:
                routes_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(routes_module)
                
                # Register routes if the module has a register function
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
    try:
        while True:
            # Echo for now - will be replaced with actual device status
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