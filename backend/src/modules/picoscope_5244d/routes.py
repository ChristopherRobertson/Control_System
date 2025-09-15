"""
PicoScope 5244D API Routes — Phase 1 scaffolding
"""

from fastapi import APIRouter, HTTPException, FastAPI
from pydantic import BaseModel
from typing import Dict, Any
import logging

from .controller import PicoScope5244DController

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/picoscope_5244d", tags=["picoscope_5244d"])
picoscope_controller = PicoScope5244DController()


class ChannelConfigRequest(BaseModel):
    channel: str
    config: Dict[str, Any]


class DictConfigRequest(BaseModel):
    config: Dict[str, Any]


@router.post("/connect")
async def connect():
    try:
        await picoscope_controller.connect()
        return {"message": "Connected", **(await picoscope_controller.get_status())}
    except Exception as e:
        logger.exception("Connect error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disconnect")
async def disconnect():
    try:
        await picoscope_controller.disconnect()
        return {"message": "Disconnected", **(await picoscope_controller.get_status())}
    except Exception as e:
        logger.exception("Disconnect error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def status():
    try:
        return await picoscope_controller.get_status()
    except Exception as e:
        logger.exception("Status error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resolution")
async def set_resolution(body: Dict[str, Any]):
    try:
        await picoscope_controller.set_resolution(int(body.get('bits')))
        return {"message": "Resolution updated", **(await picoscope_controller.get_status())}
    except Exception as e:
        logger.exception("Resolution error")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/waveform_count")
async def set_waveform_count(body: Dict[str, Any]):
    try:
        await picoscope_controller.set_waveform_count(int(body.get('count')))
        return {"message": "Waveform count updated", **(await picoscope_controller.get_status())}
    except Exception as e:
        logger.exception("Waveform count error")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/channel")
async def set_channel(req: ChannelConfigRequest):
    try:
        await picoscope_controller.set_channel_config(req.channel, req.config)
        return {"message": f"Channel {req.channel} updated", **(await picoscope_controller.get_status())}
    except Exception as e:
        logger.exception("Channel config error")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/timebase")
async def set_timebase(req: DictConfigRequest):
    try:
        await picoscope_controller.set_timebase_config(req.config)
        return {"message": "Timebase updated", **(await picoscope_controller.get_status())}
    except Exception as e:
        logger.exception("Timebase error")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/trigger")
async def set_trigger(req: DictConfigRequest):
    try:
        await picoscope_controller.set_trigger_config(req.config)
        return {"message": "Trigger updated", **(await picoscope_controller.get_status())}
    except Exception as e:
        logger.exception("Trigger error")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/awg")
async def set_awg(req: DictConfigRequest):
    try:
        await picoscope_controller.set_awg_config(req.config)
        return {"message": "AWG updated", **(await picoscope_controller.get_status())}
    except Exception as e:
        logger.exception("AWG error")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/run")
async def run():
    try:
        await picoscope_controller.run()
        return {"message": "Acquisition started", **(await picoscope_controller.get_status())}
    except Exception as e:
        logger.exception("Run error")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stop")
async def stop():
    try:
        await picoscope_controller.stop()
        return {"message": "Acquisition stopped", **(await picoscope_controller.get_status())}
    except Exception as e:
        logger.exception("Stop error")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/acquire_preview")
async def acquire_preview():
    try:
        result = await picoscope_controller.acquire_preview()
        return {"message": "Preview acquired", "result": result, **(await picoscope_controller.get_status())}
    except Exception as e:
        logger.exception("Acquire preview error")
        raise HTTPException(status_code=400, detail=str(e))


def register(app: FastAPI) -> None:
    app.include_router(router)

@router.post("/channel/zero_offset")
async def zero_offset(body: Dict[str, Any]):
    try:
        ch = str(body.get('channel') or '')
        await picoscope_controller.zero_offset(ch)
        return {"message": f"Zeroed offset for {ch}", **(await picoscope_controller.get_status())}
    except Exception as e:
        logger.exception("Zero offset error")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/autosetup")
async def autosetup():
    try:
        status = await picoscope_controller.auto_setup()
        return {"message": "Auto setup applied", **status}
    except Exception as e:
        logger.exception("Autosetup error")
        raise HTTPException(status_code=400, detail=str(e))
