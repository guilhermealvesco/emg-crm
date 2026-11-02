"""Webhook do Autentique. Responde 200 rápido, guarda o evento (idempotência) e processa."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from ..database import SessionLocal
from ..models import WebhookEvent
from ..services import contracts
from ..services.autentique import verificar_assinatura

router = APIRouter(prefix="/webhooks")
log = logging.getLogger(__name__)


def _processar(payload: dict) -> None:
    db = SessionLocal()
    try:
        msg = contracts.processar_webhook(db, payload)
        log.info("autentique webhook: %s", msg)
    except Exception:  # noqa: BLE001
        log.exception("erro ao processar webhook do Autentique")
    finally:
        db.close()


@router.post("/autentique")
async def autentique_webhook(request: Request, bg: BackgroundTasks):
    raw = await request.body()
    if not verificar_assinatura(raw, request.headers.get("x-autentique-signature")):
        log.warning("webhook Autentique com assinatura inválida")
        return JSONResponse({"error": "invalid signature"}, status_code=401)
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except ValueError:
        return JSONResponse({"error": "invalid payload"}, status_code=400)
    event = payload.get("event") or {}
    event_id = event.get("id") or payload.get("id")
    etype = event.get("type")
    db = SessionLocal()
    try:
        if event_id:
            if db.scalar(select(WebhookEvent).where(WebhookEvent.event_id == str(event_id))):
                return {"status": "duplicate"}
            db.add(WebhookEvent(provider="autentique", event_id=str(event_id), event_type=etype, payload=payload))
            db.commit()
    finally:
        db.close()
    bg.add_task(_processar, payload)
    return {"status": "ok"}
