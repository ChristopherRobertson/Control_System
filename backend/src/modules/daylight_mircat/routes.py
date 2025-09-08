"""
Daylight MIRcat API Routes

REST API endpoints for controlling the Daylight MIRcat QCL laser
"""

from fastapi import APIRouter, HTTPException, FastAPI
from pydantic import BaseModel
from typing import Dict, Any, List
import logging

from .controller import MIRcatController

logger = logging.getLogger(__name__)

# Create router with prefix for this device
router = APIRouter(prefix="/api/daylight_mircat", tags=["daylight_mircat"])

# Global controller instance
mircat_controller = MIRcatController()

# Request/Response Models
class TuneRequest(BaseModel):
    wavenumber: float

class LaserModeRequest(BaseModel):
    mode: str

class PulseParametersRequest(BaseModel):
    pulse_rate: int
    pulse_width: int

class SweepScanRequest(BaseModel):
    start_wavenumber: float
    end_wavenumber: float
    scan_speed: float
    number_of_scans: int = 1
    bidirectional_scanning: bool = False

class StepScanRequest(BaseModel):
    start_wavenumber: float
    end_wavenumber: float
    step_size: float
    dwell_time: int
    number_of_scans: int = 1

class MultispectralEntry(BaseModel):
    wavenumber: float
    dwell_time: int
    off_time: int

class MultispectralScanRequest(BaseModel):
    wavelength_list: List[MultispectralEntry]
    number_of_scans: int = 1
    keep_laser_on_between_steps: bool = False

# Connection endpoints
@router.post("/connect")
async def connect():
    """Connect to MIRcat device"""
    try:
        success = await mircat_controller.connect()
        if success:
            return {"message": "Connected to MIRcat successfully", "connected": True}
        else:
            raise HTTPException(status_code=500, detail="Failed to connect to device")
    except Exception as e:
        logger.error(f"Connect error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/disconnect")
async def disconnect():
    """Disconnect from MIRcat device"""
    try:
        success = await mircat_controller.disconnect()
        if success:
            return {"message": "Disconnected from MIRcat successfully", "connected": False}
        else:
            raise HTTPException(status_code=500, detail="Failed to disconnect from device")
    except Exception as e:
        logger.error(f"Disconnect error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Laser control endpoints
@router.post("/arm")
async def arm_laser():
    """Arm the laser for operation"""
    try:
        success = await mircat_controller.arm_laser()
        if success:
            return {"message": "Laser armed successfully", "armed": True}
        else:
            raise HTTPException(status_code=500, detail="Failed to arm laser")
    except Exception as e:
        logger.error(f"Arm laser error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/disarm")
async def disarm_laser():
    """Disarm the laser"""
    try:
        success = await mircat_controller.disarm_laser()
        if success:
            return {"message": "Laser disarmed successfully", "armed": False}
        else:
            raise HTTPException(status_code=500, detail="Failed to disarm laser")
    except Exception as e:
        logger.error(f"Disarm laser error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/emission/on")
async def turn_emission_on():
    """Turn laser emission on"""
    try:
        success = await mircat_controller.turn_emission_on()
        if success:
            return {"message": "Emission turned on successfully", "emission_on": True}
        else:
            raise HTTPException(status_code=500, detail="Failed to turn emission on")
    except Exception as e:
        logger.error(f"Turn emission on error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/emission/off")
async def turn_emission_off():
    """Turn laser emission off"""
    try:
        success = await mircat_controller.turn_emission_off()
        if success:
            return {"message": "Emission turned off successfully", "emission_on": False}
        else:
            raise HTTPException(status_code=500, detail="Failed to turn emission off")
    except Exception as e:
        logger.error(f"Turn emission off error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Tuning and configuration endpoints
@router.post("/tune")
async def tune_to_wavenumber(request: TuneRequest):
    """Tune laser to specific wavenumber"""
    try:
        success = await mircat_controller.tune_to_wavenumber(request.wavenumber)
        if success:
            return {
                "message": f"Tuned to {request.wavenumber} cm-1 successfully",
                "wavenumber": request.wavenumber
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to tune laser")
    except Exception as e:
        logger.error(f"Tune error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/mode")
async def set_laser_mode(request: LaserModeRequest):
    """Set laser operation mode"""
    try:
        success = await mircat_controller.set_laser_mode(request.mode)
        if success:
            return {
                "message": f"Laser mode set to {request.mode} successfully",
                "mode": request.mode
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to set laser mode")
    except Exception as e:
        logger.error(f"Set mode error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/pulse-parameters")
async def set_pulse_parameters(request: PulseParametersRequest):
    """Set pulse parameters for pulsed mode"""
    try:
        success = await mircat_controller.set_pulse_parameters(
            request.pulse_rate, 
            request.pulse_width
        )
        if success:
            return {
                "message": "Pulse parameters set successfully",
                "pulse_rate": request.pulse_rate,
                "pulse_width": request.pulse_width
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to set pulse parameters")
    except Exception as e:
        logger.error(f"Set pulse parameters error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Status endpoints
@router.get("/status")
async def get_status():
    """Get current device status"""
    try:
        status = await mircat_controller.get_status()
        return status
    except Exception as e:
        logger.error(f"Get status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config")
async def get_config():
    """Get device configuration parameters"""
    try:
        return mircat_controller.config
    except Exception as e:
        logger.error(f"Get config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Scan endpoints
@router.post("/scan/sweep/start")
async def start_sweep_scan(request: SweepScanRequest):
    """Start sweep scan mode"""
    try:
        success = await mircat_controller.start_sweep_scan(
            request.start_wavenumber,
            request.end_wavenumber,
            request.scan_speed,
            request.number_of_scans,
            request.bidirectional_scanning
        )
        if success:
            return {
                "message": "Sweep scan started successfully",
                "scan_mode": "sweep",
                "parameters": request.dict()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to start sweep scan")
    except Exception as e:
        logger.error(f"Start sweep scan error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/scan/step/start")
async def start_step_scan(request: StepScanRequest):
    """Start step and measure scan mode"""
    try:
        success = await mircat_controller.start_step_scan(
            request.start_wavenumber,
            request.end_wavenumber,
            request.step_size,
            request.dwell_time,
            request.number_of_scans
        )
        if success:
            return {
                "message": "Step scan started successfully",
                "scan_mode": "step",
                "parameters": request.dict()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to start step scan")
    except Exception as e:
        logger.error(f"Start step scan error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/scan/multispectral/start")
async def start_multispectral_scan(request: MultispectralScanRequest):
    """Start multi-spectral scan mode"""
    try:
        # Convert request to list of dictionaries
        wavelength_list = [entry.dict() for entry in request.wavelength_list]
        
        success = await mircat_controller.start_multispectral_scan(
            wavelength_list,
            request.number_of_scans,
            request.keep_laser_on_between_steps
        )
        if success:
            return {
                "message": "Multispectral scan started successfully",
                "scan_mode": "multispectral",
                "parameters": request.dict()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to start multispectral scan")
    except Exception as e:
        logger.error(f"Start multispectral scan error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/scan/stop")
async def stop_scan():
    """Stop any active scan"""
    try:
        success = await mircat_controller.stop_scan()
        if success:
            return {
                "message": "Scan stopped successfully",
                "scan_in_progress": False
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to stop scan")
    except Exception as e:
        logger.error(f"Stop scan error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

def register(app: FastAPI) -> None:
    """Register MIRcat routes with FastAPI app"""
    app.include_router(router)