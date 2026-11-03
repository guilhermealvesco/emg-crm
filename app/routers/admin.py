from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Role, User
from ..security import hash_password, require_admin
from ..services import alerts
from ..templating import flash, render

router = APIRouter(prefix="/admin")


@router.get("/usuarios")
def usuarios(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    lista = db.scalars(select(User).order_by(User.role, User.name)).all()
    return render(request, "admin/users.html", user=user, usuarios=lista, roles=Role.LABELS)


@router.post("/usuarios")
def criar(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...),
          role: str = Form(Role.CAPTADOR), phone: str = Form(""), user: User = Depends(require_admin),
          db: Session = Depends(get_db)):
    email = email.strip().lower()
    if role not in Role.ALL:
        role = Role.CAPTADOR
    if db.scalar(select(User).where(User.email == email)):
        flash(request, "Já existe usuário com esse e-mail.", "erro")
    elif len(password) < 8:
        flash(request, "Senha com pelo menos 8 caracteres.", "erro")
    else:
        db.add(User(name=name.strip(), email=email, password_hash=hash_password(password), role=role,
                    phone=phone.strip() or None))
        db.commit()
        flash(request, f"Usuário {name} criado.")
    return RedirectResponse("/admin/usuarios", status_code=303)


@router.post("/usuarios/{uid}")
def editar(request: Request, uid: int, name: str = Form(...), role: str = Form(...), phone: str = Form(""),
           active: str = Form(""), password: str = Form(""), user: User = Depends(require_admin),
           db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404)
    u.name = name.strip()
    if role in Role.ALL and u.id != user.id:
        u.role = role
    u.phone = phone.strip() or None
    if u.id != user.id:
        u.active = active == "on"
    if password:
        if len(password) < 8:
            flash(request, "Senha com pelo menos 8 caracteres.", "erro")
            return RedirectResponse("/admin/usuarios", status_code=303)
        u.password_hash = hash_password(password)
    db.commit()
    flash(request, "Usuário atualizado.")
    return RedirectResponse("/admin/usuarios", status_code=303)


@router.get("/config")
def config_page(request: Request, user: User = Depends(require_admin)):
    info = {
        "Ambiente": settings.ENV,
        "URL pública": settings.PUBLIC_URL,
        "Banco de dados": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else settings.DATABASE_URL,
        "APIBrasil": ("ativa" if settings.APIBRASIL_ENABLED else "desativada") + (", homologação (sem gastar crédito)" if settings.APIBRASIL_HOMOLOG else ", PRODUÇÃO (gasta crédito)"),
        "APIBrasil token": "configurado" if settings.APIBRASIL_TOKEN else "FALTANDO",
        "Autentique token": "configurado" if settings.AUTENTIQUE_TOKEN else "FALTANDO",
        "Autentique modo": "sandbox (teste)" if settings.AUTENTIQUE_SANDBOX else "PRODUÇÃO",
        "Autentique verificação": settings.AUTENTIQUE_VERIFICATION or "nenhuma",
        "Webhook Autentique": f"{settings.PUBLIC_URL}/webhooks/autentique" + (" (secret configurado)" if settings.AUTENTIQUE_WEBHOOK_SECRET else " (SEM secret: configure AUTENTIQUE_WEBHOOK_SECRET)"),
        "Posse do lead": f"{settings.OWNERSHIP_DAYS} dias",
        "Alertas": f"sem movimento {settings.ALERTA_SEM_MOVIMENTO}d, banco não enviado {settings.ALERTA_BANCO_NAO_ENVIADO}d, sem follow-up {settings.ALERTA_SEM_FOLLOWUP}d, posição a cada {settings.POSICAO_CLIENTE_DIAS}d",
    }
    return render(request, "admin/config.html", user=user, info=info)


@router.post("/rotina")
def rodar_rotina(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    r = alerts.rotina_diaria(db)
    flash(request, f"Rotina executada: {r['tarefas_posicao_criadas']} tarefa(s) de posição criada(s).")
    return RedirectResponse("/admin/config", status_code=303)


@router.post("/recalcular-prescore")
def recalcular_prescore(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    from ..enrichment.prescore import recalcular_lead
    from ..models import Lead
    leads = db.scalars(select(Lead).where(Lead.enrichment.is_not(None))).all()
    for l in leads:
        recalcular_lead(l)
    db.commit()
    flash(request, f"Pré-score recalculado em {len(leads)} lead(s), sem nova consulta.")
    return RedirectResponse("/admin/config", status_code=303)
