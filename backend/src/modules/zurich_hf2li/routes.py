"""
Zurich Instruments HF2LI API Routes (Phase 1 – live LabOne API)

Expose connection lifecycle and generic node get/set endpoints that map
directly to Zurich Instruments' LabOne Data Server. No simulated
responses are returned: every operation uses real API calls.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Iterable, List, Tuple
import logging

from .controller import ZurichHF2LIController

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/zurich_hf2li", tags=["zurich_hf2li"])
hf2_controller = ZurichHF2LIController()


class NodesGetPayload(BaseModel):
    paths: List[str]


class NodeSetting(BaseModel):
    path: str
    value: Any


class NodesSetPayload(BaseModel):
    settings: List[NodeSetting]


@router.get("/status")
async def status():
    return await hf2_controller.get_status()


@router.post("/connect")
async def connect():
    try:
        if await hf2_controller.connect():
            return {"message": "Connected", **(await hf2_controller.get_status())}
        raise HTTPException(status_code=500, detail=hf2_controller.last_error or "Failed to connect")
    except Exception as e:
        logger.exception("HF2LI connect failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disconnect")
async def disconnect():
    try:
        await hf2_controller.disconnect()
        return {"message": "Disconnected", **(await hf2_controller.get_status())}
    except Exception as e:
        logger.exception("HF2LI disconnect failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/nodes/get")
async def get_nodes(payload: NodesGetPayload):
    try:
        return await hf2_controller.get_nodes(payload.paths)
    except Exception as e:
        logger.exception("HF2LI get nodes failed")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/nodes/set")
async def set_nodes(payload: NodesSetPayload):
    try:
        items: List[Tuple[str, Any]] = [(s.path, s.value) for s in payload.settings]
        return await hf2_controller.set_nodes(items)
    except Exception as e:
        logger.exception("HF2LI set nodes failed")
        raise HTTPException(status_code=400, detail=str(e))


def register(app: FastAPI) -> None:
    app.include_router(router)

