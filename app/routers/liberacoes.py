from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Disbursement, ExitoTipo, Lead, User
from ..security import get_current_user, require_staff
from ..services import disbursements as svc
from ..services.leads import pode_ver
from ..templating import flash, render
from ..utils import parse_brl, today_local

router = APIRouter(prefix="/liberacoes")


@router.get("")
def listar(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Disbursement).order_by(Disbursement.data_liberacao.desc())
    if not user.is_staff:
        q = q.where(Disbursement.captador_id == user.id)
    libs = db.scalars(q).all()
    return render(request, "liberacoes/list.html", user=user, libs=libs, hoje=today_local(),
                  total_volume=sum(d.valor_liberado for d in libs),
                  total_pendente=sum(d.comissao_total for d in libs if not d.comissao_paga))


@router.get("/nova/{lead_id}")
def nova(request: Request, lead_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404)
    bons = [b for b in lead.banks if b.status == "retorno_bom"]
    return render(request, "liberacoes/new.html", user=user, lead=lead, bancos=settings.BANCOS, bons=bons,
                  hoje=today_local(), piso=settings.TARIFA_PISO_EMG)


@router.post("/nova/{lead_id}")
def criar(request: Request, lead_id: int, banco: str = Form(...), valor: str = Form(...), data_liberacao: str = Form(...),
          exito_tipo: str = Form(...), honorarios_emg: str = Form(""), observacao: str = Form(""),
          user: User = Depends(require_staff), db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404)
    try:
        d = svc.registrar_liberacao(db, lead, user, banco, parse_brl(valor) or 0, date.fromisoformat(data_liberacao),
                                    exito_tipo, parse_brl(honorarios_emg), observacao.strip() or None)
        flash(request, f"Liberação registrada. Comissão do captador: {d.comissao_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    except svc.DisbursementError as e:
        flash(request, str(e), "erro")
        return RedirectResponse(f"/liberacoes/nova/{lead.id}", status_code=303)
    return RedirectResponse(f"/leads/{lead.id}", status_code=303)


@router.post("/{did}/recebido")
def recebido(request: Request, did: int, em: str = Form(...), user: User = Depends(require_staff),
             db: Session = Depends(get_db)):
    d = db.get(Disbursement, did)
    if not d:
        raise HTTPException(404)
    svc.marcar_recebimento(db, d, user, date.fromisoformat(em))
    flash(request, "Recebimento da EMG registrado.")
    return RedirectResponse(f"/leads/{d.lead_id}", status_code=303)


@router.post("/{did}/comissao-paga")
def comissao_paga(request: Request, did: int, em: str = Form(...), user: User = Depends(require_staff),
                  db: Session = Depends(get_db)):
    d = db.get(Disbursement, did)
    if not d:
        raise HTTPException(404)
    try:
        svc.marcar_comissao_paga(db, d, user, date.fromisoformat(em))
        flash(request, "Comissão marcada como paga.")
    except svc.DisbursementError as e:
        flash(request, str(e), "erro")
    return RedirectResponse(f"/leads/{d.lead_id}", status_code=303)
