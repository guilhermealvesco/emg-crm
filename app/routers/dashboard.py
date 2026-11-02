from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import BankStatus, Lead, Stage, Task, User
from ..security import get_current_user, require_staff
from ..services import alerts, disbursements
from ..templating import render
from ..utils import today_local

router = APIRouter()


@router.get("/")
def home(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    hoje = today_local()
    tarefas = db.scalars(select(Task).where(Task.assigned_to_id == user.id, Task.done.is_(False))
                         .order_by(Task.due_date.asc().nulls_last(), Task.created_at.desc()).limit(12)).all()
    leads_q = select(Lead).where(Lead.stage.notin_([Stage.PERDIDO, Stage.COMISSAO_PAGA]))
    if not user.is_staff:
        leads_q = leads_q.where(Lead.captador_id == user.id)
    leads = db.scalars(leads_q.order_by(Lead.last_activity_at.desc())).all()
    etapas = {s: 0 for s in Stage.ORDER}
    for l in leads:
        etapas[l.stage] = etapas.get(l.stage, 0) + 1
    com_alerta = alerts.leads_com_alerta(db, user)[:8]
    ctx = {"tarefas": tarefas, "leads": leads[:10], "etapas": etapas, "com_alerta": com_alerta, "hoje": hoje,
           "triagem_pendente": sum(1 for l in leads if l.stage == Stage.TRIAGEM)}
    if user.is_staff:
        ctx["resumo"] = disbursements.resumo_geral(db)
        ctx["fila_bancos"] = sum(1 for l in leads if l.stage in (Stage.BANCOS, Stage.RETORNO)
                                 and any(b.status == BankStatus.NAO_ENVIADO for b in l.banks))
        ctx["ranking"] = disbursements.ranking(db)[:5]
    else:
        meus = disbursements.ranking(db)
        ctx["minha_posicao"] = next((r for r in meus if r["captador"].id == user.id), None)
    return render(request, "dashboard.html", user=user, **ctx)


@router.get("/alertas")
def alertas_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return render(request, "alertas.html", user=user, com_alerta=alerts.leads_com_alerta(db, user))


@router.get("/ranking")
def ranking_page(request: Request, inicio: str | None = None, fim: str | None = None,
                 user: User = Depends(require_staff), db: Session = Depends(get_db)):
    di = date.fromisoformat(inicio) if inicio else None
    df = date.fromisoformat(fim) if fim else None
    return render(request, "ranking.html", user=user, ranking=disbursements.ranking(db, di, df),
                  resumo=disbursements.resumo_geral(db), inicio=inicio or "", fim=fim or "")
