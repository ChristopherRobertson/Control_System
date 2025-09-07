"""
PicoScope 5244D API Routes

REST API endpoints for controlling the PicoScope 5244D MSO oscilloscope
"""

from fastapi import APIRouter, HTTPException, FastAPI
from pydantic import BaseModel
from typing import Dict, Any
import logging

from .controller import PicoScope5244DController

logger = logging.getLogger(__name__)

# Create router with prefix for this device
router = APIRouter(prefix="/api/picoscope_5244d", tags=["picoscope_5244d"])

# Global controller instance
picoscope_controller = PicoScope5244DController()

# Request/Response Models
class ChannelConfigRequest(BaseModel):
    channel: str
    config: Dict[str, Any]

class TimebaseConfigRequest(BaseModel):
    config: Dict[str, Any]

class TriggerConfigRequest(BaseModel):
    config: Dict[str, Any]

# Connection endpoints
@router.post("/connect")
async def connect():
    """Connect to PicoScope device"""
    try:
        success = await picoscope_controller.connect()
        if success:
            return {"message": "Connected to PicoScope successfully", "connected": True}
        else:
            raise HTTPException(status_code=500, detail="Failed to connect to device")
    except Exception as e:
        logger.error(f"Connect error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/disconnect")
async def disconnect():
    """Disconnect from PicoScope device"""
    try:
        success = await picoscope_controller.disconnect()
        if success:
            return {"message": "Disconnected from PicoScope successfully", "connected": False}
        else:
            raise HTTPException(status_code=500, detail="Failed to disconnect from device")
    except Exception as e:
        logger.error(f"Disconnect error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Acquisition control endpoints
@router.post("/start")
async def start_acquisition():
    """Start data acquisition"""
    try:
        success = await picoscope_controller.start_acquisition()
        if success:
            return {"message": "Acquisition started successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to start acquisition")
    except Exception as e:
        logger.error(f"Start acquisition error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/stop")
async def stop_acquisition():
    """Stop data acquisition"""
    try:
        success = await picoscope_controller.stop_acquisition()
        if success:
            return {"message": "Acquisition stopped successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to stop acquisition")
    except Exception as e:
        logger.error(f"Stop acquisition error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auto-setup")
async def auto_setup():
    """Perform auto setup"""
    try:
        success = await picoscope_controller.auto_setup()
        if success:
            return {"message": "Auto setup completed successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to perform auto setup")
    except Exception as e:
        logger.error(f"Auto setup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Configuration endpoints
@router.post("/channel")
async def set_channel_config(request: ChannelConfigRequest):
    """Configure oscilloscope channel"""
    try:
        success = await picoscope_controller.set_channel_config(request.channel, request.config)
        if success:
            return {"message": f"Channel {request.channel} configured successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to configure channel")
    except Exception as e:
        logger.error(f"Channel config error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/timebase")
async def set_timebase_config(request: TimebaseConfigRequest):
    """Configure timebase settings"""
    try:
        success = await picoscope_controller.set_timebase_config(request.config)
        if success:
            return {"message": "Timebase configured successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to configure timebase")
    except Exception as e:
        logger.error(f"Timebase config error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/trigger")
async def set_trigger_config(request: TriggerConfigRequest):
    """Configure trigger settings"""
    try:
        success = await picoscope_controller.set_trigger_config(request.config)
        if success:
            return {"message": "Trigger configured successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to configure trigger")
    except Exception as e:
        logger.error(f"Trigger config error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Status endpoints
@router.get("/status")
async def get_status():
    """Get current device status"""
    try:
        status = await picoscope_controller.get_status()
        return status
    except Exception as e:
        logger.error(f"Get status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def register(app: FastAPI) -> None:
    """Register PicoScope routes with FastAPI app"""
    app.include_router(router)