"""Funil com travas.

Novo → Triagem → Nos bancos → Retorno → Cobrança/contrato → Docs → Liberação → Comissão paga

Trava principal: a cobrança do cliente (contrato + tarifa) só acontece DEPOIS de haver retorno bom
de pelo menos um banco. Evita estorno e desgaste.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Activity, BankStatus, Lead, Stage, Task, TaskType, User
from ..utils import now_local, today_local


class FunnelError(Exception):
    pass


def tem_retorno_bom(lead: Lead) -> bool:
    return any(b.status == BankStatus.RETORNO_BOM for b in lead.banks)


def tem_algum_retorno(lead: Lead) -> bool:
    return any(b.status in (BankStatus.RETORNO_BOM, BankStatus.RETORNO_RUIM) for b in lead.banks)


def pode_cobrar(lead: Lead) -> tuple[bool, str]:
    """Pode gerar contrato / cobrar tarifa?"""
    if lead.triagem_decisao != "aprovado":
        return False, "O lead ainda não foi aprovado na triagem."
    if not tem_retorno_bom(lead):
        return False, "Trava do funil: só é possível cobrar o cliente depois de um retorno BOM de algum banco."
    return True, ""


def _set_stage(db: Session, lead: Lead, user: User | None, nova: str, obs: str = "") -> None:
    antiga = lead.stage
    lead.stage = nova
    lead.stage_changed_at = now_local()
    lead.last_activity_at = now_local()
    texto = f"Etapa: {Stage.LABELS.get(antiga, antiga)} → {Stage.LABELS.get(nova, nova)}."
    if obs:
        texto += f" {obs}"
    db.add(Activity(lead_id=lead.id, user_id=user.id if user else None, tipo="etapa", descricao=texto))


def mudar_etapa(db: Session, lead: Lead, user: User, nova: str, obs: str = "") -> Lead:
    """Mudança manual de etapa pela operação, respeitando as travas."""
    if nova not in Stage.LABELS:
        raise FunnelError("Etapa inválida.")
    if nova == lead.stage:
        return lead
    if nova == Stage.PERDIDO:
        lead.motivo_perda = obs or lead.motivo_perda
        _set_stage(db, lead, user, nova, obs)
        db.commit()
        return lead
    if nova == Stage.BANCOS and lead.triagem_decisao != "aprovado":
        raise FunnelError("Aprove o lead na triagem antes de enviar aos bancos.")
    if Stage.index(nova) >= Stage.index(Stage.COBRANCA):
        ok, msg = pode_cobrar(lead)
        if not ok:
            raise FunnelError(msg)
    if nova == Stage.LIBERACAO and not lead.disbursements:
        raise FunnelError("Registre a liberação de crédito para avançar a esta etapa.")
    if nova == Stage.COMISSAO_PAGA and not (lead.disbursements and all(d.comissao_paga for d in lead.disbursements)):
        raise FunnelError("Todas as comissões das liberações precisam estar pagas.")
    _set_stage(db, lead, user, nova, obs)
    db.commit()
    db.refresh(lead)
    return lead


def decidir_triagem(db: Session, lead: Lead, user: User, decisao: str, obs: str = "") -> Lead:
    if decisao not in ("aprovado", "reprovado"):
        raise FunnelError("Decisão inválida.")
    lead.triagem_decisao = decisao
    lead.triagem_por_id = user.id
    lead.triagem_at = now_local()
    lead.triagem_obs = obs or None
    db.add(Activity(lead_id=lead.id, user_id=user.id, tipo="sistema",
                    descricao=f"Triagem: {decisao.upper()} por {user.name}." + (f" {obs}" if obs else "")))
    if decisao == "aprovado":
        _set_stage(db, lead, user, Stage.BANCOS, "Aprovado na triagem.")
        # tarefa para a operação enviar aos bancos
        db.add(Task(lead_id=lead.id, assigned_to_id=user.id, created_by_id=user.id, tipo=TaskType.ENVIAR_BANCO,
                    titulo=f"Enviar {lead.nome} aos bancos", due_date=today_local(), auto=True))
        # tarefa para o captador dar posição ao cliente
        db.add(Task(lead_id=lead.id, assigned_to_id=lead.captador_id, created_by_id=user.id, tipo=TaskType.POSICAO,
                    titulo=f"Dar posição ao cliente {lead.nome}: lead aprovado, indo para os bancos",
                    due_date=today_local(), auto=True))
    else:
        lead.motivo_perda = obs or "Reprovado na triagem."
        _set_stage(db, lead, user, Stage.PERDIDO, "Reprovado na triagem.")
        db.add(Task(lead_id=lead.id, assigned_to_id=lead.captador_id, created_by_id=user.id, tipo=TaskType.POSICAO,
                    titulo=f"Dar posição ao cliente {lead.nome}: não seguiremos neste momento",
                    due_date=today_local(), auto=True))
    db.commit()
    db.refresh(lead)
    return lead


def apos_retorno_banco(db: Session, lead: Lead, user: User, banco: str, status: str) -> None:
    """Chamado pela matriz de bancos: avança para Retorno no primeiro retorno e cria tarefa de posição."""
    if status in (BankStatus.RETORNO_BOM, BankStatus.RETORNO_RUIM) and lead.stage == Stage.BANCOS:
        _set_stage(db, lead, user, Stage.RETORNO, f"Primeiro retorno: {banco}.")
    if status == BankStatus.RETORNO_BOM:
        db.add(Task(lead_id=lead.id, assigned_to_id=lead.captador_id, created_by_id=user.id, tipo=TaskType.POSICAO,
                    titulo=f"Dar posição ao cliente {lead.nome}: retorno bom do {banco}, alinhar contrato e tarifa",
                    due_date=today_local(), auto=True))


def apos_contrato_assinado(db: Session, lead: Lead) -> None:
    if Stage.index(lead.stage) < Stage.index(Stage.DOCS) and lead.stage != Stage.PERDIDO:
        _set_stage(db, lead, None, Stage.DOCS, "Contrato assinado (Autentique).")
        lead.docs_pendentes = True
        db.add(Task(lead_id=lead.id, assigned_to_id=lead.captador_id, tipo=TaskType.DOCS,
                    titulo=f"Coletar documentação de {lead.nome} para os bancos", due_date=today_local(), auto=True))


def apos_liberacao(db: Session, lead: Lead, user: User) -> None:
    if Stage.index(lead.stage) < Stage.index(Stage.LIBERACAO) and lead.stage != Stage.PERDIDO:
        _set_stage(db, lead, user, Stage.LIBERACAO, "Liberação registrada.")
    lead.docs_pendentes = False


def apos_comissao_paga(db: Session, lead: Lead, user: User) -> None:
    if lead.disbursements and all(d.comissao_paga for d in lead.disbursements) and lead.stage == Stage.LIBERACAO:
        _set_stage(db, lead, user, Stage.COMISSAO_PAGA, "Todas as comissões pagas.")
