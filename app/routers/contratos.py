from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Contract, Lead, User
from ..security import get_current_user
from ..services import contracts as svc
from ..services import funnel
from ..services.autentique import AutentiqueError
from ..services.leads import pode_ver
from ..templating import flash, render
from ..utils import fmt_cnpj, parse_brl

router = APIRouter(prefix="/contratos")

FORMAS = ["transferência PIX à vista para a conta da CONTRATADA (CNPJ 60.975.099/0001-79, Banco Bradesco PJ)",
          "boleto bancário à vista", "cartão de crédito em até 12 (doze) parcelas, com os encargos da operadora",
          "transferência PIX em 3 (três) parcelas mensais iguais"]


def _contract(db: Session, cid: int, user: User) -> Contract:
    c = db.get(Contract, cid)
    if not c or not pode_ver(c.lead, user):
        raise HTTPException(404)
    return c


@router.get("")
def listar(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Contract).order_by(Contract.created_at.desc())
    if not user.is_staff:
        q = q.join(Lead).where(Lead.captador_id == user.id)
    return render(request, "contratos/list.html", user=user, contratos=db.scalars(q).all())


@router.get("/novo/{lead_id}")
def novo(request: Request, lead_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead or not pode_ver(lead, user):
        raise HTTPException(404)
    ok, msg = funnel.pode_cobrar(lead)
    if not ok:
        flash(request, msg, "erro")
        return RedirectResponse(f"/leads/{lead.id}", status_code=303)
    cad = (lead.enrichment or {}).get("cadastral") or {}
    raw = cad.get("raw") or {}
    endereco = ", ".join(x for x in [
        f"{raw.get('descricao_tipo_de_logradouro', '')} {raw.get('logradouro', '')}".strip(),
        raw.get("numero"), raw.get("complemento"), raw.get("bairro")] if x) or ""
    sugestao = {
        "razao_social": lead.razao_social or lead.nome, "nome_fantasia": lead.nome_fantasia or "", "cnpj": fmt_cnpj(lead.cnpj),
        "endereco": endereco, "cep": raw.get("cep", ""),
        "cidade_uf": f"{cad.get('municipio', '')}/{cad.get('uf', '')}" if cad.get("municipio") else "",
        "telefone": lead.contato_telefone or "", "email": lead.contato_email or "",
        "representante": lead.contato_nome or "", "representante_cpf": lead.contato_cpf or "",
        "tarifa_valor": lead.tarifa_valor or settings.TARIFA_TABELA,
    }
    return render(request, "contratos/new.html", user=user, lead=lead, s=sugestao, formas=FORMAS,
                  piso=settings.TARIFA_PISO_EMG, tabela=settings.TARIFA_TABELA)


@router.post("/novo/{lead_id}")
async def criar(request: Request, lead_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead or not pode_ver(lead, user):
        raise HTTPException(404)
    form = await request.form()
    dados = {k: (form.get(k) or "").strip() for k in ("razao_social", "nome_fantasia", "cnpj", "ie_rg", "endereco", "cep", "cidade_uf",
                                                      "telefone", "email", "representante", "representante_cpf")}
    dados["tarifa_valor"] = parse_brl(form.get("tarifa_valor"))
    forma = (form.get("forma_pagamento") or "").strip()
    if forma == "outra":
        forma = (form.get("forma_pagamento_outra") or "").strip()
    dados["forma_pagamento"] = forma
    try:
        c = svc.criar_rascunho(db, lead, user, dados)
    except svc.ContractError as e:
        flash(request, str(e), "erro")
        return RedirectResponse(f"/contratos/novo/{lead.id}", status_code=303)
    flash(request, "Contrato gerado. Confira o PDF e envie para assinatura.")
    return RedirectResponse(f"/contratos/{c.id}", status_code=303)


@router.get("/{cid}")
def detalhe(request: Request, cid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _contract(db, cid, user)
    return render(request, "contratos/detail.html", user=user, c=c)


@router.get("/{cid}/pdf")
def pdf(cid: int, assinado: int = 0, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _contract(db, cid, user)
    path = c.signed_pdf_path if assinado else c.pdf_path
    if not path or not Path(path).exists():
        raise HTTPException(404, "PDF não encontrado.")
    nome = f"{c.file_basename}{'-ASSINADO' if assinado else ''}.pdf"
    return FileResponse(path, media_type="application/pdf", filename=nome)


@router.post("/{cid}/enviar")
def enviar(request: Request, cid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _contract(db, cid, user)
    try:
        svc.enviar(db, c, user)
        flash(request, "Enviado para assinatura." + (" (sandbox: não consome créditos)" if c.sandbox else ""))
    except svc.ContractError as e:
        flash(request, f"Não foi possível enviar: {e}", "erro")
    return RedirectResponse(f"/contratos/{c.id}", status_code=303)


@router.post("/{cid}/sincronizar")
def sincronizar(request: Request, cid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _contract(db, cid, user)
    try:
        svc.sincronizar(db, c)
        flash(request, f"Status atualizado: {c.status_label}.")
    except (svc.ContractError, AutentiqueError) as e:
        flash(request, f"Falha ao consultar o Autentique: {e}", "erro")
    return RedirectResponse(f"/contratos/{c.id}", status_code=303)


@router.post("/{cid}/cancelar")
def cancelar(request: Request, cid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _contract(db, cid, user)
    if c.status == "assinado":
        flash(request, "Contrato assinado não pode ser cancelado aqui.", "erro")
    else:
        c.status = "cancelado"
        db.commit()
        flash(request, "Contrato cancelado no CRM. Se já foi enviado, exclua também no painel do Autentique.")
    return RedirectResponse(f"/contratos/{c.id}", status_code=303)
