"""Página de contrato: gerar PDF, enviar ao Autentique, processar webhook e arquivar o assinado."""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Activity, Contract, ContractStatus, Lead, Stage, User
from ..utils import brl, fmt_cnpj, fmt_cpf, now_local, only_digits, slugify_name, validate_cpf
from . import autentique, commissions, contract_pdf, funnel

log = logging.getLogger(__name__)


class ContractError(Exception):
    pass


def basename_for(razao_social: str) -> str:
    return f"{slugify_name(razao_social)}-Contrato-Consultoria-Credito"


def criar_rascunho(db: Session, lead: Lead, user: User, dados: dict) -> Contract:
    ok, msg = funnel.pode_cobrar(lead)
    if not ok:
        raise ContractError(msg)
    erro = commissions.validar_tarifa(dados.get("tarifa_valor"))
    if erro:
        raise ContractError(erro)
    if not dados.get("forma_pagamento"):
        raise ContractError("Informe a forma de pagamento.")
    if not dados.get("email"):
        raise ContractError("Informe o e-mail do signatário (quem recebe o link de assinatura).")
    cpf = only_digits(dados.get("representante_cpf"))
    if not validate_cpf(cpf):
        raise ContractError("CPF do representante inválido.")
    razao = (dados.get("razao_social") or lead.razao_social or lead.nome or "").strip()
    if not razao:
        raise ContractError("Informe a razão social do cliente.")
    c = Contract(
        lead_id=lead.id, created_by_id=user.id,
        razao_social=razao, nome_fantasia=(dados.get("nome_fantasia") or "").strip() or None,
        cnpj=fmt_cnpj(dados.get("cnpj") or lead.cnpj),
        ie_rg=dados.get("ie_rg") or None, endereco=dados.get("endereco") or None, cep=dados.get("cep") or None,
        cidade_uf=dados.get("cidade_uf") or None, telefone=dados.get("telefone") or None,
        email=dados["email"].strip(), representante=dados.get("representante", "").strip(),
        representante_cpf=fmt_cpf(cpf), tarifa_valor=float(dados["tarifa_valor"]),
        forma_pagamento=dados["forma_pagamento"].strip(), status=ContractStatus.RASCUNHO,
        file_basename=basename_for(razao), sandbox=settings.AUTENTIQUE_SANDBOX,
    )
    if not c.representante:
        raise ContractError("Informe o nome do representante legal.")
    db.add(c)
    db.flush()
    destino = settings.CONTRACTS_DIR / f"{c.id}" / f"{c.file_basename}.pdf"
    contract_pdf.gerar_pdf(c, destino)
    c.pdf_path = str(destino)
    lead.tarifa_valor = c.tarifa_valor
    lead.contato_cpf = cpf
    if lead.stage in (Stage.RETORNO, Stage.BANCOS):
        funnel._set_stage(db, lead, user, Stage.COBRANCA, "Contrato gerado.")
    db.add(Activity(lead_id=lead.id, user_id=user.id, tipo="contrato",
                    descricao=f"Contrato gerado ({c.file_basename}.pdf). Tarifa {brl(c.tarifa_valor)}, {c.forma_pagamento}."))
    db.commit()
    db.refresh(c)
    return c


def enviar(db: Session, contract: Contract, user: User) -> Contract:
    if contract.status not in (ContractStatus.RASCUNHO, ContractStatus.RECUSADO):
        raise ContractError("Este contrato já foi enviado.")
    if not contract.pdf_path or not Path(contract.pdf_path).exists():
        contract_pdf.gerar_pdf(contract, settings.CONTRACTS_DIR / f"{contract.id}" / f"{contract.file_basename}.pdf")
        contract.pdf_path = str(settings.CONTRACTS_DIR / f"{contract.id}" / f"{contract.file_basename}.pdf")
    try:
        res = autentique.criar_documento(Path(contract.pdf_path), contract.file_basename, contract.email,
                                         contract.representante, only_digits(contract.representante_cpf))
    except autentique.AutentiqueError as e:
        contract.error = str(e)
        db.commit()
        raise ContractError(str(e)) from e
    contract.autentique_id = res["id"]
    contract.autentique_link = res.get("link")
    contract.sandbox = res.get("sandbox", settings.AUTENTIQUE_SANDBOX)
    contract.status = ContractStatus.ENVIADO
    contract.sent_at = now_local()
    contract.error = None
    contract.lead.last_activity_at = now_local()
    db.add(Activity(lead_id=contract.lead_id, user_id=user.id, tipo="contrato",
                    descricao=f"Contrato enviado para assinatura ({contract.email})"
                              + (" [sandbox]" if contract.sandbox else "") + "."))
    db.commit()
    db.refresh(contract)
    return contract


def marcar_assinado(db: Session, contract: Contract, signed_url: str | None, origem: str = "webhook") -> Contract:
    if contract.status == ContractStatus.ASSINADO:
        return contract
    contract.status = ContractStatus.ASSINADO
    contract.signed_at = now_local()
    if signed_url:
        destino = settings.CONTRACTS_DIR / f"{contract.id}" / f"{contract.file_basename}-ASSINADO.pdf"
        try:
            autentique.baixar_arquivo(signed_url, destino)
            contract.signed_pdf_path = str(destino)
        except autentique.AutentiqueError as e:
            contract.error = f"assinado, mas o PDF não foi baixado: {e}"
            log.warning("download assinado %s: %s", contract.id, e)
    db.add(Activity(lead_id=contract.lead_id, tipo="contrato",
                    descricao=f"Contrato assinado ({origem})." + (" PDF arquivado." if contract.signed_pdf_path else "")))
    funnel.apos_contrato_assinado(db, contract.lead)
    db.commit()
    db.refresh(contract)
    return contract


def marcar_recusado(db: Session, contract: Contract, motivo: str = "") -> Contract:
    contract.status = ContractStatus.RECUSADO
    db.add(Activity(lead_id=contract.lead_id, tipo="contrato", descricao=f"Contrato recusado pelo signatário. {motivo}"))
    db.commit()
    return contract


def sincronizar(db: Session, contract: Contract) -> Contract:
    """Consulta o Autentique e atualiza o status (botão manual, útil se o webhook falhar)."""
    if not contract.autentique_id:
        raise ContractError("Contrato ainda não foi enviado.")
    d = autentique.consultar_documento(contract.autentique_id)
    sigs = d.get("signatures") or []
    assinados = [s for s in sigs if s.get("signed")]
    recusados = [s for s in sigs if s.get("rejected")]
    if sigs and len(assinados) == len(sigs):
        return marcar_assinado(db, contract, (d.get("files") or {}).get("signed"), origem="sincronização")
    if recusados:
        return marcar_recusado(db, contract)
    return contract


def processar_webhook(db: Session, payload: dict) -> str:
    """Trata document.finished / signature.accepted / signature.rejected. Retorna texto de log."""
    event = payload.get("event") or {}
    etype = event.get("type") or ""
    data = event.get("data") or {}
    obj = data.get("object") if isinstance(data.get("object"), dict) else data
    doc_id = None
    if etype.startswith("document."):
        doc_id = obj.get("id")
    elif etype.startswith("signature."):
        doc_id = obj.get("document")
    if not doc_id:
        return f"evento {etype} sem id de documento"
    contract = db.scalar(select(Contract).where(Contract.autentique_id == doc_id))
    if not contract:
        return f"evento {etype}: documento {doc_id} não pertence ao CRM"
    if etype == "document.finished":
        files = obj.get("files") or {}
        marcar_assinado(db, contract, files.get("signed"))
        return f"contrato {contract.id} assinado"
    if etype == "signature.rejected":
        marcar_recusado(db, contract)
        return f"contrato {contract.id} recusado"
    if etype == "signature.accepted":
        # pode haver mais de um signatário: confirma pelo documento
        try:
            sincronizar(db, contract)
        except (autentique.AutentiqueError, ContractError) as e:
            log.warning("sync após signature.accepted: %s", e)
        return f"assinatura aceita no contrato {contract.id}"
    if etype == "document.updated":
        signed_count = obj.get("signed_count")
        sig_count = obj.get("signatures_count")
        if signed_count and sig_count and signed_count >= sig_count:
            marcar_assinado(db, contract, (obj.get("files") or {}).get("signed"))
            return f"contrato {contract.id} assinado (document.updated)"
    return f"evento {etype} ignorado"
