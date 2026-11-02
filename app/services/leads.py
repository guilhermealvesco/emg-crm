"""Entrada de leads e regra de dono (90 dias, renovável por novo contato registrado)."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Activity, BankSubmission, Lead, Stage, User
from ..utils import now_local, only_digits, today_local, validate_cnpj


class LeadError(Exception):
    pass


class DuplicateLead(LeadError):
    def __init__(self, lead: Lead, mensagem: str):
        super().__init__(mensagem)
        self.lead = lead


def _owner_until():
    return today_local() + timedelta(days=settings.OWNERSHIP_DAYS)


def registrar_lead(db: Session, captador: User, cnpj: str, **campos) -> Lead:
    """Cria o lead ou arbitra a duplicidade.

    - CNPJ já cadastrado com dono vigente: recusa (informa até quando o dono vigora).
    - CNPJ já cadastrado com dono expirado e lead parado antes de 'Nos bancos': transfere para o novo captador.
    - CNPJ já cadastrado com dono expirado mas em etapa avançada: mantém com o dono original (o trabalho já andou).
    """
    c = only_digits(cnpj)
    if not validate_cnpj(c):
        raise LeadError("CNPJ inválido.")
    existente = db.scalar(select(Lead).where(Lead.cnpj == c))
    hoje = today_local()
    if existente:
        if existente.captador_id == captador.id:
            raise DuplicateLead(existente, "Você já cadastrou este CNPJ. Registre um contato no lead para renovar a posse.")
        if existente.owner_until >= hoje:
            raise DuplicateLead(existente, f"Este CNPJ já pertence a outro captador até {existente.owner_until:%d/%m/%Y}.")
        if Stage.index(existente.stage) >= Stage.index(Stage.BANCOS) and existente.stage != Stage.PERDIDO:
            raise DuplicateLead(existente, "Este CNPJ já está em andamento com a EMG (etapa avançada). Fale com a operação.")
        # posse expirada e lead parado: transfere
        antigo = existente.captador.name if existente.captador else "captador anterior"
        existente.captador_id = captador.id
        existente.owner_until = _owner_until()
        existente.last_activity_at = now_local()
        existente.last_contact_at = now_local()
        for k, v in campos.items():
            if v not in (None, "") and hasattr(existente, k):
                setattr(existente, k, v)
        if existente.stage == Stage.PERDIDO:
            existente.stage = Stage.NOVO
            existente.stage_changed_at = now_local()
        db.add(Activity(lead_id=existente.id, user_id=captador.id, tipo="sistema",
                        descricao=f"Posse expirada: lead transferido de {antigo} para {captador.name}."))
        db.commit()
        db.refresh(existente)
        return existente

    lead = Lead(cnpj=c, captador_id=captador.id, owner_until=_owner_until(), stage=Stage.NOVO,
                last_contact_at=now_local(), **campos)
    db.add(lead)
    db.flush()
    for banco in settings.BANCOS:
        db.add(BankSubmission(lead_id=lead.id, banco=banco))
    db.add(Activity(lead_id=lead.id, user_id=captador.id, tipo="sistema",
                    descricao=f"Lead registrado por {captador.name}. Posse até {lead.owner_until:%d/%m/%Y}."))
    db.commit()
    db.refresh(lead)
    return lead


def registrar_contato(db: Session, lead: Lead, user: User, descricao: str, tipo: str = "contato") -> Activity:
    """Registra contato/nota. Contato do captador renova a posse por mais 90 dias."""
    act = Activity(lead_id=lead.id, user_id=user.id, tipo=tipo, descricao=descricao)
    db.add(act)
    agora = now_local()
    lead.last_activity_at = agora
    if tipo in ("contato", "posicao"):
        lead.last_contact_at = agora
        if tipo == "posicao":
            lead.last_posicao_at = agora
        if user.id == lead.captador_id:
            novo = _owner_until()
            if novo > lead.owner_until:
                lead.owner_until = novo
    db.commit()
    db.refresh(lead)
    return act


def pode_ver(lead: Lead, user: User) -> bool:
    return user.is_staff or lead.captador_id == user.id


def query_visiveis(user: User):
    q = select(Lead)
    if not user.is_staff:
        q = q.where(Lead.captador_id == user.id)
    return q
