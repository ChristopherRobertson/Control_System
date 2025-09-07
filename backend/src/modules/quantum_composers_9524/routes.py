"""
Quantum Composers 9524 API Routes

REST API endpoints for controlling the Quantum Composers 9524 signal generator
"""

from fastapi import APIRouter, HTTPException, FastAPI
from pydantic import BaseModel
from typing import Dict, Any
import logging

from .controller import QuantumComposers9524Controller

logger = logging.getLogger(__name__)

# Create router with prefix for this device
router = APIRouter(prefix="/api/quantum_composers_9524", tags=["quantum_composers_9524"])

# Global controller instance
qc_controller = QuantumComposers9524Controller()

# Request/Response Models
class SystemConfigRequest(BaseModel):
    config: Dict[str, Any]

class ChannelConfigRequest(BaseModel):
    channel: str
    config: Dict[str, Any]

class TriggerConfigRequest(BaseModel):
    config: Dict[str, Any]

class CommandRequest(BaseModel):
    command: str

# Connection endpoints
@router.post("/connect")
async def connect():
    """Connect to Quantum Composers device"""
    try:
        success = await qc_controller.connect()
        if success:
            return {"message": "Connected to Quantum Composers successfully", "connected": True}
        else:
            raise HTTPException(status_code=500, detail="Failed to connect to device")
    except Exception as e:
        logger.error(f"Connect error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/disconnect")
async def disconnect():
    """Disconnect from Quantum Composers device"""
    try:
        success = await qc_controller.disconnect()
        if success:
            return {"message": "Disconnected from Quantum Composers successfully", "connected": False}
        else:
            raise HTTPException(status_code=500, detail="Failed to disconnect from device")
    except Exception as e:
        logger.error(f"Disconnect error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Output control endpoints
@router.post("/start")
async def start_output():
    """Start signal generation"""
    try:
        success = await qc_controller.start_output()
        if success:
            return {"message": "Output started successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to start output")
    except Exception as e:
        logger.error(f"Start output error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/stop")
async def stop_output():
    """Stop signal generation"""
    try:
        success = await qc_controller.stop_output()
        if success:
            return {"message": "Output stopped successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to stop output")
    except Exception as e:
        logger.error(f"Stop output error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Configuration endpoints
@router.post("/system")
async def set_system_config(request: SystemConfigRequest):
    """Configure system settings"""
    try:
        success = await qc_controller.set_system_config(request.config)
        if success:
            return {"message": "System configured successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to configure system")
    except Exception as e:
        logger.error(f"System config error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/channel")
async def set_channel_config(request: ChannelConfigRequest):
    """Configure signal generator channel"""
    try:
        success = await qc_controller.set_channel_config(request.channel, request.config)
        if success:
            return {"message": f"Channel {request.channel} configured successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to configure channel")
    except Exception as e:
        logger.error(f"Channel config error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/external-trigger")
async def set_external_trigger_config(request: TriggerConfigRequest):
    """Configure external trigger settings"""
    try:
        success = await qc_controller.set_external_trigger_config(request.config)
        if success:
            return {"message": "External trigger configured successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to configure external trigger")
    except Exception as e:
        logger.error(f"External trigger config error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/command")
async def send_command(request: CommandRequest):
    """Send command via command terminal"""
    try:
        response = await qc_controller.send_command(request.command)
        return {"message": "Command sent successfully", "response": response}
    except Exception as e:
        logger.error(f"Send command error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Status endpoints
@router.get("/status")
async def get_status():
    """Get current device status"""
    try:
        status = await qc_controller.get_status()
        return status
    except Exception as e:
        logger.error(f"Get status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def register(app: FastAPI) -> None:
    """Register Quantum Composers routes with FastAPI app"""
    app.include_router(router)