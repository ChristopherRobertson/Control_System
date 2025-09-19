"""
Quantum Composers 9524 API Routes (Phase 1 – live serial)

Minimal REST endpoints mapping the UI to real device commands via the
controller. No simulated responses are returned.
"""

from fastapi import APIRouter, HTTPException, FastAPI
from pydantic import BaseModel
from typing import Dict, Any
import logging

from .controller import QuantumComposers9524Controller

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quantum_composers_9524", tags=["quantum_composers_9524"])
qc_controller = QuantumComposers9524Controller()


class DictPayload(BaseModel):
    config: Dict[str, Any]


class ChannelPayload(BaseModel):
    channel: str
    config: Dict[str, Any]


class ChannelActionPayload(BaseModel):
    channel: str


class CommandPayload(BaseModel):
    command: str


@router.post("/connect")
async def connect():
    try:
        if qc_controller.connected:
            return {"message": "Already connected", **(await qc_controller.get_status())}
        ok = await qc_controller.connect()
        if not ok:
            raise HTTPException(status_code=500, detail=qc_controller.last_error or "Connect failed")
        return {"message": "Connected", **(await qc_controller.get_status())}
    except Exception as e:
        logger.exception("QC connect error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disconnect")
async def disconnect():
    try:
        await qc_controller.disconnect()
        return {"message": "Disconnected", **(await qc_controller.get_status())}
    except Exception as e:
        logger.exception("QC disconnect error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
async def start():
    try:
        await qc_controller.start_output()
        return {"message": "Output started", **(await qc_controller.get_status())}
    except Exception as e:
        logger.exception("QC start error")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stop")
async def stop():
    try:
        await qc_controller.stop_output()
        return {"message": "Output stopped", **(await qc_controller.get_status())}
    except Exception as e:
        logger.exception("QC stop error")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/system")
async def set_system(payload: DictPayload):
    try:
        await qc_controller.set_system_config(payload.config)
        return {"message": "System updated", **(await qc_controller.get_status())}
    except Exception as e:
        logger.exception("QC system config error")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/channel")
async def set_channel(payload: ChannelPayload):
    try:
        await qc_controller.set_channel_config(payload.channel, payload.config)
        return {"message": f"Channel {payload.channel} updated", **(await qc_controller.get_status())}
    except Exception as e:
        logger.exception("QC channel config error")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/channel/stop")
async def stop_channel(payload: ChannelActionPayload):
    try:
        resp = await qc_controller.stop_channel_output(payload.channel)
        status = await qc_controller.get_status()
        return {"message": f"Channel {payload.channel} stopped", "device_response": resp, **status}
    except Exception as e:
        logger.exception("QC channel stop error")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/external-trigger")
async def set_external_trigger(payload: DictPayload):
    try:
        await qc_controller.set_external_trigger_config(payload.config)
        return {"message": "External trigger updated", **(await qc_controller.get_status())}
    except Exception as e:
        logger.exception("QC external trigger config error")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/command")
async def command(payload: CommandPayload):
    try:
        resp = await qc_controller.send_command(payload.command)
        return {"message": "Command sent", "response": resp}
    except Exception as e:
        logger.exception("QC command error")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status")
async def status():
    try:
        return await qc_controller.get_status()
    except Exception as e:
        logger.exception("QC status error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def config():
    try:
        st = await qc_controller.get_status()
        return {"ranges": st.get("ranges", {}), "device_info": st.get("device_info", {})}
    except Exception as e:
        logger.exception("QC config error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ports")
async def ports():
    try:
        return {"ports": qc_controller.available_ports()}
    except Exception as e:
        logger.exception("QC ports error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health():
    try:
        return qc_controller.probe_open()
    except Exception as e:
        logger.exception("QC health error")
        raise HTTPException(status_code=500, detail=str(e))


def register(app: FastAPI) -> None:
    app.include_router(router)
