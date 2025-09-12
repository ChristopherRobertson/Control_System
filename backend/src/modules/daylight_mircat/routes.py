"""
Daylight MIRcat API Routes

REST API endpoints for controlling the Daylight MIRcat QCL laser
"""

from fastapi import APIRouter, HTTPException, FastAPI
from pydantic import BaseModel
from typing import Dict, Any, List
import logging
import json
from pathlib import Path

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

class UserSettings(BaseModel):
    selectQCL: int | None = None
    laserMode: str | None = None
    pulseRate: int | None = None
    pulseWidth: int | None = None
    pulsedCurrent: int | None = None
    cwCurrent: int | None = None
    temperature: float | None = None
    enableParameterLogging: bool | None = None
    disableAudioNotification: bool | None = None
    flashLEDWhenFires: bool | None = None
    processTriggerMode: str | None = None
    internalStepTime: int | None = None
    internalStepDelay: int | None = None
    pulseMode: str | None = None
    wlTrigInterval: float | None = None
    wlTrigStart: float | None = None
    wlTrigStop: float | None = None

# Connection endpoints
@router.post("/connect")
async def connect():
    """Connect to MIRcat device"""
    try:
        # Idempotent: if already connected, treat as success
        if mircat_controller.connected:
            status = await mircat_controller.get_status()
            return {"message": "Already connected", **status}
        success = await mircat_controller.connect()
        if success:
            status = await mircat_controller.get_status()
            return {"message": "Connected to MIRcat successfully", **status}
        else:
            raise HTTPException(status_code=500, detail="Failed to connect to device")
    except Exception as e:
        logger.error(f"Connect error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/disconnect")
async def disconnect():
    """Disconnect from MIRcat device"""
    try:
        # Idempotent: if already disconnected, treat as success
        if not mircat_controller.connected:
            status = await mircat_controller.get_status()
            return {"message": "Already disconnected", **status}
        success = await mircat_controller.disconnect()
        if success:
            status = await mircat_controller.get_status()
            return {"message": "Disconnected from MIRcat successfully", **status}
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
        if mircat_controller.armed:
            status = await mircat_controller.get_status()
            return {"message": "Already armed", **status}
        success = await mircat_controller.arm_laser()
        if success:
            status = await mircat_controller.get_status()
            return {"message": "Laser armed successfully", **status}
        else:
            raise HTTPException(status_code=500, detail="Failed to arm laser")
    except Exception as e:
        logger.error(f"Arm laser error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/disarm")
async def disarm_laser():
    """Disarm the laser"""
    try:
        if not mircat_controller.armed:
            status = await mircat_controller.get_status()
            return {"message": "Already disarmed", **status}
        success = await mircat_controller.disarm_laser()
        if success:
            status = await mircat_controller.get_status()
            return {"message": "Laser disarmed successfully", **status}
        else:
            raise HTTPException(status_code=500, detail="Failed to disarm laser")
    except Exception as e:
        logger.error(f"Disarm laser error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/emission/on")
async def turn_emission_on():
    """Turn laser emission on"""
    try:
        if mircat_controller.emission_on:
            status = await mircat_controller.get_status()
            return {"message": "Emission already on", **status}
        success = await mircat_controller.turn_emission_on()
        if success:
            status = await mircat_controller.get_status()
            return {"message": "Emission turned on successfully", **status}
        else:
            raise HTTPException(status_code=500, detail="Failed to turn emission on")
    except Exception as e:
        logger.error(f"Turn emission on error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/emission/off")
async def turn_emission_off():
    """Turn laser emission off"""
    try:
        if not mircat_controller.emission_on:
            status = await mircat_controller.get_status()
            return {"message": "Emission already off", **status}
        success = await mircat_controller.turn_emission_off()
        if success:
            status = await mircat_controller.get_status()
            return {"message": "Emission turned off successfully", **status}
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
            status = await mircat_controller.get_status()
            return {"message": f"Tuned to {request.wavenumber} cm-1 successfully", **status}
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
            status = await mircat_controller.get_status()
            return {"message": f"Laser mode set to {request.mode} successfully", **status}
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
            status = await mircat_controller.get_status()
            return {"message": "Pulse parameters set successfully", **status}
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
        logger.info(f"Sweep request params: {request.dict()}")
        success = await mircat_controller.start_sweep_scan(
            request.start_wavenumber,
            request.end_wavenumber,
            request.scan_speed,
            request.number_of_scans,
            request.bidirectional_scanning
        )
        if success:
            status = await mircat_controller.get_status()
            return {"message": "Sweep scan started successfully", **status, "parameters": request.dict()}
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
            status = await mircat_controller.get_status()
            return {"message": "Step scan started successfully", **status, "parameters": request.dict()}
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
            status = await mircat_controller.get_status()
            return {"message": "Multispectral scan started successfully", **status, "parameters": request.dict()}
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

@router.post("/scan/step/manual")
async def manual_step_scan():
    try:
        success = await mircat_controller.manual_step()
        if success:
            status = await mircat_controller.get_status()
            return {"message": "Manual step executed", **status}
        else:
            raise HTTPException(status_code=500, detail="Failed to manual step")
    except Exception as e:
        logger.error(f"Manual step error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

def register(app: FastAPI) -> None:
    """Register MIRcat routes with FastAPI app"""
    app.include_router(router)

# User settings persistence
SETTINGS_PATH = (Path(__file__).parent / 'user_settings.json').resolve()

@router.get('/settings')
async def get_user_settings():
    try:
        if SETTINGS_PATH.exists():
            with open(SETTINGS_PATH, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Get settings error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/settings')
async def save_user_settings(payload: UserSettings):
    try:
        # Merge with existing
        data: Dict[str, Any] = {}
        if SETTINGS_PATH.exists():
            with open(SETTINGS_PATH, 'r') as f:
                try:
                    data = json.load(f)
                except Exception:
                    data = {}
        update = {k: v for k, v in payload.dict().items() if v is not None}
        data.update(update)
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_PATH, 'w') as f:
            json.dump(data, f)
        # Optionally apply hardware-affecting settings now
        # Apply hardware-affecting settings as appropriate
        if payload.laserMode is not None:
            await mircat_controller.set_laser_mode(payload.laserMode)
        # Only set pulse params when in Pulsed mode
        try:
            effective_mode = payload.laserMode if payload.laserMode is not None else mircat_controller.laser_mode
            if effective_mode == 'Pulsed' and payload.pulseRate is not None and payload.pulseWidth is not None:
                await mircat_controller.set_pulse_parameters(payload.pulseRate, payload.pulseWidth, payload.pulsedCurrent)
        except Exception as e:
            logger.warning(f"Applying pulse params skipped/failed: {e}")
        # Apply trigger-related settings when provided
        try:
            await mircat_controller.apply_trigger_settings(data)
        except Exception as e:
            logger.warning(f"Trigger settings apply failed: {e}")
        status = await mircat_controller.get_status()
        return {"message": "Settings saved", **status, "settings": data}
    except Exception as e:
        logger.error(f"Save settings error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/clear-error')
async def clear_error():
    try:
        await mircat_controller.clear_error()
        status = await mircat_controller.get_status()
        return {"message": "Error cleared", **status}
    except Exception as e:
        logger.error(f"Clear error failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
