"""Liberações de crédito, comissões e ranking dos captadores."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Activity, Disbursement, ExitoTipo, Lead, Role, Stage, User
from ..utils import brl, now_local
from . import commissions, funnel


class DisbursementError(Exception):
    pass


def registrar_liberacao(db: Session, lead: Lead, user: User, banco: str, valor: float, data_liberacao: date,
                        exito_tipo: str, honorarios_emg: float | None = None, observacao: str | None = None) -> Disbursement:
    if exito_tipo not in (ExitoTipo.INDICACAO, ExitoTipo.FECHAMENTO):
        raise DisbursementError("Tipo de êxito inválido.")
    if not valor or valor <= 0:
        raise DisbursementError("Informe o valor liberado.")
    primeira = len(lead.disbursements) == 0
    calc = commissions.calcular(valor, exito_tipo, lead.tarifa_valor, primeira)
    d = Disbursement(lead_id=lead.id, captador_id=lead.captador_id, banco=banco, valor_liberado=valor,
                     data_liberacao=data_liberacao, exito_tipo=exito_tipo, honorarios_emg=honorarios_emg,
                     observacao=observacao, created_by_id=user.id, **calc)
    db.add(d)
    db.add(Activity(lead_id=lead.id, user_id=user.id, tipo="sistema",
                    descricao=f"Liberação registrada: {banco}, {brl(valor)} ({ExitoTipo.LABELS[exito_tipo]}). "
                              f"Comissão calculada: {brl(calc['comissao_total'])}."))
    funnel.apos_liberacao(db, lead, user)
    db.commit()
    db.refresh(d)
    return d


def marcar_recebimento(db: Session, d: Disbursement, user: User, recebido_em: date) -> Disbursement:
    d.emg_recebeu = True
    d.emg_recebeu_em = recebido_em
    db.add(Activity(lead_id=d.lead_id, user_id=user.id, tipo="sistema",
                    descricao=f"EMG recebeu os honorários da liberação {d.banco} {brl(d.valor_liberado)} em {recebido_em:%d/%m/%Y}."))
    db.commit()
    return d


def marcar_comissao_paga(db: Session, d: Disbursement, user: User, paga_em: date) -> Disbursement:
    if not d.emg_recebeu:
        raise DisbursementError("A comissão só pode ser paga após o recebimento efetivo pela EMG.")
    d.comissao_paga = True
    d.comissao_paga_em = paga_em
    db.add(Activity(lead_id=d.lead_id, user_id=user.id, tipo="sistema",
                    descricao=f"Comissão de {brl(d.comissao_total)} paga ao captador em {paga_em:%d/%m/%Y}."))
    funnel.apos_comissao_paga(db, d.lead, user)
    db.commit()
    return d


def ranking(db: Session, inicio: date | None = None, fim: date | None = None) -> list[dict]:
    """Métricas por captador: leads, aproveitamento na triagem, fechamentos, volume liberado, comissões."""
    captadores = db.scalars(select(User).where(User.role == Role.CAPTADOR, User.active.is_(True))).all()
    out = []
    for c in captadores:
        q = select(Lead).where(Lead.captador_id == c.id)
        if inicio:
            q = q.where(Lead.created_at >= inicio)
        if fim:
            q = q.where(Lead.created_at <= fim)
        leads = db.scalars(q).all()
        total = len(leads)
        triados = [l for l in leads if l.triagem_decisao]
        aprovados = [l for l in leads if l.triagem_decisao == "aprovado"]
        contratos = [l for l in leads if any(ct.status == "assinado" for ct in l.contracts)]
        libs = db.scalars(select(Disbursement).where(Disbursement.captador_id == c.id)).all()
        if inicio:
            libs = [d for d in libs if d.data_liberacao >= inicio]
        if fim:
            libs = [d for d in libs if d.data_liberacao <= fim]
        volume = sum(d.valor_liberado for d in libs)
        com_total = sum(d.comissao_total for d in libs)
        com_paga = sum(d.comissao_total for d in libs if d.comissao_paga)
        com_pend = sum(d.comissao_total for d in libs if not d.comissao_paga)
        out.append({
            "captador": c, "leads": total, "triados": len(triados), "aprovados": len(aprovados),
            "aproveitamento": (len(aprovados) / len(triados) * 100) if triados else 0.0,
            "contratos": len(contratos), "liberacoes": len(libs), "volume": volume,
            "comissao_total": com_total, "comissao_paga": com_paga, "comissao_pendente": com_pend,
            "leads_ativos": sum(1 for l in leads if l.stage not in (Stage.PERDIDO, Stage.COMISSAO_PAGA)),
        })
    out.sort(key=lambda r: (-r["volume"], -r["contratos"], -r["aprovados"], -r["leads"]))
    for i, r in enumerate(out, 1):
        r["posicao"] = i
    return out


def resumo_geral(db: Session) -> dict:
    etapas = {s: 0 for s in Stage.LABELS}
    for stage, n in db.execute(select(Lead.stage, func.count(Lead.id)).group_by(Lead.stage)).all():
        etapas[stage] = n
    libs = db.scalars(select(Disbursement)).all()
    return {
        "etapas": etapas,
        "total_leads": sum(etapas.values()),
        "volume_liberado": sum(d.valor_liberado for d in libs),
        "comissao_pendente": sum(d.comissao_total for d in libs if not d.comissao_paga),
        "comissao_paga": sum(d.comissao_total for d in libs if d.comissao_paga),
        "a_receber_emg": sum(1 for d in libs if not d.emg_recebeu),
    }
