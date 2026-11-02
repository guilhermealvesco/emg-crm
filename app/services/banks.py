"""Matriz de bancos (fila da operação)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Activity, BankStatus, BankSubmission, Lead, Task, TaskType, User
from ..utils import brl, now_local
from . import funnel


class BankError(Exception):
    pass


def atualizar_banco(db: Session, lead: Lead, user: User, banco: str, status: str,
                    valor_estimado: float | None = None, observacao: str | None = None,
                    gerente: str | None = None) -> BankSubmission:
    if status not in BankStatus.ALL:
        raise BankError("Status inválido.")
    sub = next((b for b in lead.banks if b.banco == banco), None)
    if sub is None:
        sub = BankSubmission(lead_id=lead.id, banco=banco)
        db.add(sub)
        db.flush()
    anterior = sub.status
    sub.status = status
    agora = now_local()
    if status == BankStatus.ENVIADO and anterior == BankStatus.NAO_ENVIADO:
        sub.enviado_em = agora
    if status in (BankStatus.RETORNO_BOM, BankStatus.RETORNO_RUIM):
        sub.retorno_em = agora
        if not sub.enviado_em:
            sub.enviado_em = agora
    if status == BankStatus.NAO_ENVIADO:
        sub.enviado_em = None
        sub.retorno_em = None
    if valor_estimado is not None:
        sub.valor_estimado = valor_estimado
    if observacao is not None:
        sub.observacao = observacao.strip() or None
    if gerente is not None:
        sub.gerente = gerente.strip() or None
    sub.updated_by_id = user.id
    lead.last_activity_at = agora
    texto = f"{banco}: {BankStatus.LABELS[anterior]} → {BankStatus.LABELS[status]}"
    if valor_estimado:
        texto += f" ({brl(valor_estimado)})"
    if observacao:
        texto += f". {observacao.strip()}"
    db.add(Activity(lead_id=lead.id, user_id=user.id, tipo="banco", descricao=texto))
    if anterior != status:
        funnel.apos_retorno_banco(db, lead, user, banco, status)
    # fecha a tarefa "enviar aos bancos" quando todos saíram de 'não enviado'
    if all(b.status != BankStatus.NAO_ENVIADO for b in lead.banks):
        for t in lead.tasks:
            if t.tipo == TaskType.ENVIAR_BANCO and not t.done:
                t.done = True
                t.done_at = agora
    db.commit()
    db.refresh(sub)
    return sub
