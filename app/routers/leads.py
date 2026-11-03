from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal, get_db
from ..enrichment.service import enriquecer_lead
from ..models import Lead, Prescore, Role, Stage, Task, TaskType, User
from ..security import get_current_user, require_staff
from ..services import alerts, funnel
from ..services import leads as svc
from ..templating import flash, render
from ..utils import now_local, only_digits, parse_brl, today_local, validate_cpf

router = APIRouter(prefix="/leads")
log = logging.getLogger(__name__)

ORIGENS = ["Indicação", "Carteira própria", "Prospecção ativa", "Instagram", "Evento", "Parceiro", "Outro"]


def _enrich_bg(lead_id: int, user_id: int, bureau: bool) -> None:
    db = SessionLocal()
    try:
        lead = db.get(Lead, lead_id)
        if lead:
            enriquecer_lead(db, lead, user_id, incluir_bureau=bureau)
            if lead.stage == Stage.NOVO:
                lead.stage = Stage.TRIAGEM
                lead.stage_changed_at = now_local()
                db.commit()
    except Exception:  # noqa: BLE001
        log.exception("enriquecimento em background")
    finally:
        db.close()


def _get_lead(db: Session, lead_id: int, user: User) -> Lead:
    lead = db.get(Lead, lead_id)
    if not lead or not svc.pode_ver(lead, user):
        raise HTTPException(404, "Lead não encontrado.")
    return lead


def _parse_socios(form) -> list[dict]:
    nomes = form.getlist("socio_nome")
    cpfs = form.getlist("socio_cpf")
    out = []
    for n, c in zip(nomes, cpfs):
        c = only_digits(c)
        if c:
            out.append({"nome": (n or "").strip(), "cpf": c})
    return out


@router.get("")
def listar(request: Request, etapa: str | None = None, q: str | None = None, captador: int | None = None,
           prescore: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = svc.query_visiveis(user)
    if etapa:
        query = query.where(Lead.stage == etapa)
    if prescore:
        query = query.where(Lead.prescore == prescore)
    if captador and user.is_staff:
        query = query.where(Lead.captador_id == captador)
    if q:
        like = f"%{q.strip()}%"
        query = query.where((Lead.razao_social.ilike(like)) | (Lead.nome_fantasia.ilike(like))
                            | (Lead.cnpj.like(f"%{only_digits(q)}%" if only_digits(q) else like))
                            | (Lead.contato_nome.ilike(like)))
    leads = db.scalars(query.order_by(Lead.last_activity_at.desc())).all()
    captadores = db.scalars(select(User).where(User.role == Role.CAPTADOR).order_by(User.name)).all() if user.is_staff else []
    return render(request, "leads/list.html", user=user, leads=leads, etapa=etapa or "", q=q or "",
                  captador=captador, prescore=prescore or "", captadores=captadores,
                  alertas={l.id: alerts.alertas_do_lead(l) for l in leads})


@router.get("/novo")
def novo(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    captadores = db.scalars(select(User).where(User.role == Role.CAPTADOR, User.active.is_(True)).order_by(User.name)).all() if user.is_staff else []
    return render(request, "leads/new.html", user=user, origens=ORIGENS, captadores=captadores)


@router.post("/novo")
async def criar(request: Request, bg: BackgroundTasks, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    form = await request.form()
    cnpj = only_digits(form.get("cnpj"))
    captador = user
    if user.is_staff and form.get("captador_id"):
        captador = db.get(User, int(form.get("captador_id"))) or user
    socios = _parse_socios(form)
    for s in socios:
        if not validate_cpf(s["cpf"]):
            flash(request, f"CPF inválido para o sócio {s['nome'] or ''}.", "erro")
            return RedirectResponse("/leads/novo", status_code=303)
    consent = form.get("lgpd_consent") == "on"
    if socios and not consent:
        flash(request, "Para consultar o CPF dos sócios é obrigatório registrar o aceite LGPD do cliente.", "erro")
        return RedirectResponse("/leads/novo", status_code=303)
    try:
        lead = svc.registrar_lead(
            db, captador, cnpj,
            contato_nome=(form.get("contato_nome") or "").strip() or None,
            contato_telefone=(form.get("contato_telefone") or "").strip() or None,
            contato_email=(form.get("contato_email") or "").strip().lower() or None,
            origem=(form.get("origem") or "").strip() or None,
            observacao=(form.get("observacao") or "").strip() or None,
            valor_pretendido=parse_brl(form.get("valor_pretendido")),
            socios_cpf=socios or None,
            lgpd_consent=consent,
            lgpd_consent_at=now_local() if consent else None,
            lgpd_consent_by=(form.get("lgpd_consent_by") or "").strip() or None,
            lgpd_consent_meio=(form.get("lgpd_consent_meio") or "").strip() or None,
        )
    except svc.DuplicateLead as e:
        flash(request, str(e), "erro")
        if svc.pode_ver(e.lead, user):
            return RedirectResponse(f"/leads/{e.lead.id}", status_code=303)
        return RedirectResponse("/leads/novo", status_code=303)
    except svc.LeadError as e:
        flash(request, str(e), "erro")
        return RedirectResponse("/leads/novo", status_code=303)
    bg.add_task(_enrich_bg, lead.id, user.id, True)
    flash(request, "Lead registrado. Consultando Receita Federal e bureaus, a página atualiza em instantes.")
    return RedirectResponse(f"/leads/{lead.id}", status_code=303)


@router.get("/{lead_id}")
def detalhe(request: Request, lead_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = _get_lead(db, lead_id, user)
    pode_cobrar, motivo_cobranca = funnel.pode_cobrar(lead)
    tarefas = sorted([t for t in lead.tasks], key=lambda t: (t.done, t.due_date or today_local()))
    return render(request, "leads/detail.html", user=user, lead=lead, bancos=settings.BANCOS,
                  alertas=alerts.alertas_do_lead(lead), pode_cobrar=pode_cobrar, motivo_cobranca=motivo_cobranca,
                  tarefas=tarefas, hoje=today_local(), origens=ORIGENS,
                  banks_by_name={b.banco: b for b in lead.banks},
                  captadores=db.scalars(select(User).where(User.role == Role.CAPTADOR, User.active.is_(True))
                                        .order_by(User.name)).all() if user.is_staff else [])


@router.post("/{lead_id}/captador")
def trocar_captador(request: Request, lead_id: int, captador_id: int = Form(...),
                    user: User = Depends(require_staff), db: Session = Depends(get_db)):
    """Atribui o lead a um captador (conta no ranking e nas comissões dele)."""
    from datetime import timedelta
    lead = _get_lead(db, lead_id, user)
    novo = db.get(User, captador_id)
    if not novo or novo.role != Role.CAPTADOR:
        flash(request, "Captador inválido.", "erro")
        return RedirectResponse(f"/leads/{lead.id}", status_code=303)
    antigo = lead.captador.name if lead.captador else "-"
    lead.captador_id = novo.id
    lead.owner_until = today_local() + timedelta(days=settings.OWNERSHIP_DAYS)
    for t in lead.tasks:
        if not t.done and t.tipo in (TaskType.POSICAO, TaskType.DOCS):
            t.assigned_to_id = novo.id
    for d in lead.disbursements:
        if not d.comissao_paga:
            d.captador_id = novo.id
    svc.registrar_contato(db, lead, user, f"Lead atribuído a {novo.name} (antes: {antigo}) por {user.name}.", "nota")
    flash(request, f"Lead agora é de {novo.name}.")
    return RedirectResponse(f"/leads/{lead.id}", status_code=303)


@router.post("/{lead_id}/contato")
def contato(request: Request, lead_id: int, descricao: str = Form(...), tipo: str = Form("contato"),
            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = _get_lead(db, lead_id, user)
    if tipo not in ("contato", "nota", "posicao"):
        tipo = "nota"
    svc.registrar_contato(db, lead, user, descricao.strip(), tipo)
    if tipo == "posicao":
        for t in lead.tasks:
            if t.tipo == TaskType.POSICAO and not t.done:
                t.done = True
                t.done_at = now_local()
        db.commit()
        flash(request, "Posição registrada e tarefa concluída.")
    else:
        flash(request, "Registrado." + (" Posse do lead renovada." if tipo == "contato" and user.id == lead.captador_id else ""))
    return RedirectResponse(f"/leads/{lead.id}", status_code=303)


@router.post("/{lead_id}/editar")
async def editar(request: Request, lead_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = _get_lead(db, lead_id, user)
    form = await request.form()
    for campo in ("contato_nome", "contato_telefone", "contato_email", "origem", "observacao"):
        v = (form.get(campo) or "").strip()
        setattr(lead, campo, v or None)
    lead.valor_pretendido = parse_brl(form.get("valor_pretendido"))
    if user.is_staff:
        lead.docs_pendentes = form.get("docs_pendentes") == "on"
        lead.docs_obs = (form.get("docs_obs") or "").strip() or None
    lead.last_activity_at = now_local()
    db.commit()
    flash(request, "Dados atualizados.")
    return RedirectResponse(f"/leads/{lead.id}", status_code=303)


@router.post("/{lead_id}/lgpd")
async def lgpd(request: Request, lead_id: int, bg: BackgroundTasks, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    lead = _get_lead(db, lead_id, user)
    form = await request.form()
    socios = _parse_socios(form)
    for s in socios:
        if not validate_cpf(s["cpf"]):
            flash(request, f"CPF inválido para o sócio {s['nome'] or ''}.", "erro")
            return RedirectResponse(f"/leads/{lead.id}", status_code=303)
    consent = form.get("lgpd_consent") == "on"
    if socios and not consent:
        flash(request, "Registre o aceite LGPD do cliente para consultar o CPF dos sócios.", "erro")
        return RedirectResponse(f"/leads/{lead.id}", status_code=303)
    lead.socios_cpf = socios or None
    if consent and not lead.lgpd_consent:
        lead.lgpd_consent_at = now_local()
    lead.lgpd_consent = consent
    lead.lgpd_consent_by = (form.get("lgpd_consent_by") or "").strip() or None
    lead.lgpd_consent_meio = (form.get("lgpd_consent_meio") or "").strip() or None
    db.commit()
    if socios and consent:
        bg.add_task(_enrich_bg, lead.id, user.id, True)
        flash(request, "Consentimento registrado. Consultando os sócios, a página atualiza em instantes.")
    else:
        flash(request, "Consentimento atualizado.")
    return RedirectResponse(f"/leads/{lead.id}", status_code=303)


@router.post("/{lead_id}/enriquecer")
def reenriquecer(request: Request, lead_id: int, bg: BackgroundTasks, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    lead = _get_lead(db, lead_id, user)
    bg.add_task(_enrich_bg, lead.id, user.id, user.is_staff)  # captador refaz só as fontes gratuitas (sem gastar crédito)
    flash(request, "Consulta em andamento. Recarregue a página em instantes.")
    return RedirectResponse(f"/leads/{lead.id}", status_code=303)


@router.post("/{lead_id}/triagem")
def triagem(request: Request, lead_id: int, decisao: str = Form(...), obs: str = Form(""),
            user: User = Depends(require_staff), db: Session = Depends(get_db)):
    lead = _get_lead(db, lead_id, user)
    try:
        funnel.decidir_triagem(db, lead, user, decisao, obs.strip())
        flash(request, f"Triagem registrada: {decisao}.")
    except funnel.FunnelError as e:
        flash(request, str(e), "erro")
    return RedirectResponse(f"/leads/{lead.id}", status_code=303)


@router.post("/{lead_id}/etapa")
def etapa(request: Request, lead_id: int, nova: str = Form(...), obs: str = Form(""),
          user: User = Depends(require_staff), db: Session = Depends(get_db)):
    lead = _get_lead(db, lead_id, user)
    try:
        funnel.mudar_etapa(db, lead, user, nova, obs.strip())
        flash(request, "Etapa atualizada.")
    except funnel.FunnelError as e:
        flash(request, str(e), "erro")
    return RedirectResponse(f"/leads/{lead.id}", status_code=303)


@router.post("/{lead_id}/tarifa")
def tarifa(request: Request, lead_id: int, recebida_em: str = Form(...),
           user: User = Depends(require_staff), db: Session = Depends(get_db)):
    """Confirmação manual do pagamento da tarifa (v1)."""
    from datetime import date
    lead = _get_lead(db, lead_id, user)
    ok, msg = funnel.pode_cobrar(lead)
    if not ok:
        flash(request, msg, "erro")
        return RedirectResponse(f"/leads/{lead.id}", status_code=303)
    lead.tarifa_recebida = True
    lead.tarifa_recebida_em = date.fromisoformat(recebida_em)
    svc.registrar_contato(db, lead, user, f"Tarifa recebida em {lead.tarifa_recebida_em:%d/%m/%Y}.", "nota")
    flash(request, "Recebimento da tarifa confirmado.")
    return RedirectResponse(f"/leads/{lead.id}", status_code=303)


@router.post("/{lead_id}/tarefa")
def nova_tarefa(request: Request, lead_id: int, titulo: str = Form(...), tipo: str = Form(TaskType.OUTRO),
                due_date: str = Form(""), assigned_to_id: int | None = Form(None),
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from datetime import date
    lead = _get_lead(db, lead_id, user)
    alvo = assigned_to_id if (user.is_staff and assigned_to_id) else user.id
    db.add(Task(lead_id=lead.id, assigned_to_id=alvo, created_by_id=user.id, tipo=tipo, titulo=titulo.strip(),
                due_date=date.fromisoformat(due_date) if due_date else None))
    db.commit()
    flash(request, "Tarefa criada.")
    return RedirectResponse(f"/leads/{lead.id}", status_code=303)
