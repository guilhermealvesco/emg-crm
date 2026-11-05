"""Orquestra o enriquecimento do lead: cadastral (gratuito) + bureau (APIBrasil) + pré-score."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Activity, Lead, Prescore
from ..utils import now_local, only_digits
from . import apibrasil, cadastral, prescore

log = logging.getLogger(__name__)


def _consulta(tipo: str, doc: str) -> dict:
    res = apibrasil.consultar(tipo, doc)
    resumo = apibrasil.ler_pendencias(res)
    resumo.update({"tipo": tipo, "raw": res.get("data"), "ok": res.get("ok", False),
                   "homolog": res.get("homolog", False)})
    return resumo


def _bureau_pj(cnpj: str) -> dict:
    if not settings.APIBRASIL_ENABLED or not settings.APIBRASIL_TIPO_PJ:
        return {}
    return {"pendencias": _consulta(settings.APIBRASIL_TIPO_PJ, cnpj)}


def _bureau_socios(lead: Lead) -> list[dict]:
    if (not settings.APIBRASIL_ENABLED or not settings.APIBRASIL_TIPO_PF or not lead.lgpd_consent
            or not lead.socios_cpf):
        return []
    saida = []
    for s in lead.socios_cpf:
        cpf = only_digits(s.get("cpf"))
        if len(cpf) != 11:
            continue
        saida.append({"nome": s.get("nome") or "Sócio", "cpf_mascarado": f"***.{cpf[3:6]}.{cpf[6:9]}-**",
                      "pendencias": _consulta(settings.APIBRASIL_TIPO_PF, cpf)})
    return saida


def enriquecer_lead(db: Session, lead: Lead, user_id: int | None = None, incluir_bureau: bool = True) -> Lead:
    """Consulta as fontes, grava o resultado e recalcula o pré-score. Nunca levanta exceção para a UI."""
    enr = dict(lead.enrichment or {})
    erro = None
    try:
        cad = cadastral.consultar_cnpj(lead.cnpj)
        enr["cadastral"] = cad
        if cad.get("razao_social"):
            lead.razao_social = cad["razao_social"]
        if cad.get("nome_fantasia"):
            lead.nome_fantasia = cad["nome_fantasia"]
    except cadastral.CadastralError as e:
        erro = str(e)
        log.warning("cadastral %s: %s", lead.cnpj, e)
    except Exception as e:  # noqa: BLE001
        erro = f"erro inesperado na consulta cadastral: {e}"
        log.exception("cadastral")

    if incluir_bureau:
        try:
            enr["bureau"] = {"pj": _bureau_pj(lead.cnpj), "socios": _bureau_socios(lead)}
        except Exception as e:  # noqa: BLE001
            log.exception("bureau")
            erro = (erro + " | " if erro else "") + f"bureau: {e}"

    cor, pontos, fatores = prescore.calcular(enr.get("cadastral"), enr.get("bureau"))
    lead.enrichment = enr
    lead.enrichment_at = now_local()
    lead.enrichment_error = erro
    lead.prescore = cor
    lead.prescore_pontos = pontos
    lead.prescore_fatores = fatores
    db.add(Activity(lead_id=lead.id, user_id=user_id, tipo="sistema",
                    descricao=f"Enriquecimento executado. Pré-score: {Prescore.LABELS[cor]} ({pontos} pts)."
                              + (f" Aviso: {erro}" if erro else "")))
    db.commit()
    db.refresh(lead)
    return lead
