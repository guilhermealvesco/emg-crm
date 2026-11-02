"""Alertas calculados na leitura (sem precisar de fila) e rotina diária de tarefas automáticas."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import BankStatus, Lead, Stage, Task, TaskType, User
from ..utils import days_since, now_local, today_local

ETAPAS_ATIVAS = [s for s in Stage.ORDER if s not in (Stage.COMISSAO_PAGA,)]


def alertas_do_lead(lead: Lead) -> list[dict]:
    """Lista de alertas {nivel: 'alto'|'medio', texto, tipo} para um lead."""
    out: list[dict] = []
    if lead.stage in (Stage.PERDIDO, Stage.COMISSAO_PAGA):
        return out
    d_mov = days_since(lead.last_activity_at)
    if d_mov is not None and d_mov >= settings.ALERTA_SEM_MOVIMENTO:
        out.append({"nivel": "alto" if d_mov >= 2 * settings.ALERTA_SEM_MOVIMENTO else "medio",
                    "tipo": "parado", "texto": f"Sem movimentação há {d_mov} dias"})
    d_ctt = days_since(lead.last_contact_at)
    if d_ctt is not None and d_ctt >= settings.ALERTA_SEM_FOLLOWUP:
        out.append({"nivel": "alto", "tipo": "followup", "texto": f"Sem follow-up com o cliente há {d_ctt} dias"})
    if lead.docs_pendentes and lead.stage in (Stage.DOCS, Stage.COBRANCA):
        out.append({"nivel": "medio", "tipo": "docs", "texto": "Documentação pendente"})
    if lead.stage in (Stage.BANCOS, Stage.RETORNO):
        base = lead.stage_changed_at or lead.created_at
        d_banco = days_since(base) or 0
        faltam = [b.banco for b in lead.banks if b.status == BankStatus.NAO_ENVIADO]
        if faltam and d_banco >= settings.ALERTA_BANCO_NAO_ENVIADO:
            out.append({"nivel": "medio", "tipo": "banco",
                        "texto": "Falta enviar para " + ", ".join(faltam) + f" (há {d_banco} dias na etapa)"})
    if lead.stage == Stage.RETORNO and not any(b.status == BankStatus.RETORNO_BOM for b in lead.banks):
        bons = [b for b in lead.banks if b.status == BankStatus.ENVIADO]
        if not bons:
            out.append({"nivel": "medio", "tipo": "retorno", "texto": "Só retornos ruins até agora; avaliar se segue"})
    if lead.owner_until and lead.stage in (Stage.NOVO, Stage.TRIAGEM):
        d = (lead.owner_until - today_local()).days
        if 0 <= d <= 10:
            out.append({"nivel": "medio", "tipo": "posse", "texto": f"Posse do lead vence em {d} dia(s); registre um contato"})
    return out


def leads_com_alerta(db: Session, user: User) -> list[tuple[Lead, list[dict]]]:
    q = select(Lead).where(Lead.stage.in_(ETAPAS_ATIVAS))
    if not user.is_staff:
        q = q.where(Lead.captador_id == user.id)
    res = []
    for lead in db.scalars(q).all():
        al = alertas_do_lead(lead)
        if al:
            res.append((lead, al))
    res.sort(key=lambda x: (-sum(1 for a in x[1] if a["nivel"] == "alto"), -len(x[1])))
    return res


def rotina_diaria(db: Session) -> dict:
    """Gera tarefas automáticas de 'dar posição' ao cliente para leads ativos sem posição há N dias.
    Idempotente: não duplica tarefa aberta do mesmo tipo para o mesmo lead."""
    criadas = 0
    limite = now_local() - timedelta(days=settings.POSICAO_CLIENTE_DIAS)
    leads = db.scalars(select(Lead).where(Lead.stage.in_([Stage.BANCOS, Stage.RETORNO, Stage.COBRANCA,
                                                           Stage.DOCS, Stage.LIBERACAO]))).all()
    for lead in leads:
        ultima = lead.last_posicao_at or lead.stage_changed_at or lead.created_at
        if ultima > limite:
            continue
        aberta = db.scalar(select(Task.id).where(Task.lead_id == lead.id, Task.tipo == TaskType.POSICAO,
                                                 Task.done.is_(False)).limit(1))
        if aberta:
            continue
        db.add(Task(lead_id=lead.id, assigned_to_id=lead.captador_id, tipo=TaskType.POSICAO, auto=True,
                    titulo=f"Dar posição ao cliente {lead.nome} (mesmo sem novidade)",
                    descricao="Rotina semanal: avisar o cliente que o processo segue em andamento.",
                    due_date=today_local()))
        criadas += 1
    db.commit()
    return {"tarefas_posicao_criadas": criadas}
