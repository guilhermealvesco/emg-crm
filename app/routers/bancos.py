"""Matriz de bancos: fila da operação (Eduarda), pensada para preencher rápido no celular."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import BankStatus, Lead, Stage, User
from ..security import require_staff
from ..services import banks as svc
from ..templating import flash, render
from ..utils import days_since, parse_brl

router = APIRouter(prefix="/bancos")


@router.get("")
def fila(request: Request, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    leads = db.scalars(select(Lead).where(Lead.stage.in_([Stage.BANCOS, Stage.RETORNO, Stage.COBRANCA, Stage.DOCS]))
                       .order_by(Lead.stage_changed_at.asc())).all()
    pendentes, aguardando, concluidos = [], [], []
    for l in leads:
        faltam = [b for b in l.banks if b.status == BankStatus.NAO_ENVIADO]
        enviados = [b for b in l.banks if b.status == BankStatus.ENVIADO]
        if faltam:
            pendentes.append((l, faltam, days_since(l.stage_changed_at) or 0))
        elif enviados:
            aguardando.append((l, enviados, days_since(l.stage_changed_at) or 0))
        else:
            concluidos.append(l)
    pendentes.sort(key=lambda x: -x[2])
    return render(request, "bancos/fila.html", user=user, pendentes=pendentes, aguardando=aguardando,
                  concluidos=concluidos, bancos=settings.BANCOS)


@router.post("/{lead_id}/{banco}")
def atualizar(request: Request, lead_id: int, banco: str, status: str = Form(...), valor_estimado: str = Form(""),
              observacao: str = Form(""), gerente: str = Form(""), voltar: str = Form(""),
              user: User = Depends(require_staff), db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead or banco not in settings.BANCOS:
        raise HTTPException(404)
    try:
        svc.atualizar_banco(db, lead, user, banco, status, parse_brl(valor_estimado), observacao, gerente)
        flash(request, f"{banco}: {BankStatus.LABELS.get(status, status)}.")
    except svc.BankError as e:
        flash(request, str(e), "erro")
    return RedirectResponse(voltar or f"/leads/{lead.id}", status_code=303)


@router.post("/{lead_id}/{banco}/rapido")
def rapido(request: Request, lead_id: int, banco: str, status: str = Form(...),
           user: User = Depends(require_staff), db: Session = Depends(get_db)):
    """Um toque: muda só o status (usado nos botões da fila no celular)."""
    lead = db.get(Lead, lead_id)
    if not lead or banco not in settings.BANCOS:
        raise HTTPException(404)
    try:
        svc.atualizar_banco(db, lead, user, banco, status)
    except svc.BankError as e:
        flash(request, str(e), "erro")
    return RedirectResponse("/bancos", status_code=303)
