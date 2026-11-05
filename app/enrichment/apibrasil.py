"""Cliente APIBrasil (consultas por crédito).

Gateway: POST {APIBRASIL_URL}/consulta/{servico}/credits
Body:    {"tipo": "<tipo>", "cnpj"|"cpf": "<documento>", "homolog": true|false}
Header:  Authorization: Bearer <token>

Com APIBRASIL_HOMOLOG=true o gateway responde dados de homologação e não debita créditos.
A estrutura exata de cada retorno varia por fornecedor; por isso o módulo guarda o JSON bruto
e extrai um resumo tolerante (contagens, valores e flags de "consta/nada consta").
"""
from __future__ import annotations

import re
from typing import Any

import httpx

from ..config import settings
from ..utils import only_digits

TIMEOUT = 45.0


class APIBrasilError(Exception):
    pass


def _service_for(tipo: str, doc: str) -> str:
    return "cnpj" if len(doc) == 14 else "cpf"


def consultar(tipo: str, documento: str, homolog: bool | None = None) -> dict:
    """Executa uma consulta por crédito. Retorna {"ok", "tipo", "homolog", "data"|"error", "status"}."""
    if not settings.APIBRASIL_TOKEN:
        return {"ok": False, "tipo": tipo, "error": "APIBRASIL_TOKEN não configurado"}
    doc = only_digits(documento)
    servico = _service_for(tipo, doc)
    body: dict[str, Any] = {"tipo": tipo, servico: doc,
                            "homolog": settings.APIBRASIL_HOMOLOG if homolog is None else homolog}
    url = f"{settings.APIBRASIL_URL}/consulta/{servico}/credits"
    headers = {"Authorization": f"Bearer {settings.APIBRASIL_TOKEN}", "Content-Type": "application/json",
               "Accept": "application/json"}
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.post(url, json=body, headers=headers)
    except httpx.HTTPError as e:
        return {"ok": False, "tipo": tipo, "error": f"falha de rede: {e}"}
    try:
        data = r.json()
    except ValueError:
        data = {"raw_text": r.text[:2000]}
    if r.status_code >= 400:
        msg = data.get("message") if isinstance(data, dict) else None
        return {"ok": False, "tipo": tipo, "status": r.status_code, "error": msg or f"HTTP {r.status_code}", "data": data}
    # alguns envelopes trazem "error": true mesmo com 200
    if isinstance(data, dict) and data.get("error") in (True, "true"):
        return {"ok": False, "tipo": tipo, "status": r.status_code, "error": data.get("message") or "erro na consulta",
                "data": data}
    return {"ok": True, "tipo": tipo, "homolog": body["homolog"], "status": r.status_code, "data": data}


# ----------------------------------------------------------------- resumo tolerante
_NEG_WORDS = re.compile(r"(nada\s*consta|n[aã]o\s*consta|n[aã]o\s*(foram|foi)\s*encontrad|sem\s*(registro|ocorr|protesto|pend|restri)|inexistente)",
                        re.I)
_POS_WORDS = re.compile(r"(\bconsta[m]?\b|registrad)", re.I)
_COUNT_KEYS = re.compile(r"(quantidade|qtd|total|numero|número|count|registros|ocorrencias|ocorrências)", re.I)
_VALUE_KEYS = re.compile(r"(valor|value|montante|amount)", re.I)
_SCORE_KEYS = re.compile(r"(score|pontuacao|pontuação)", re.I)


def _walk(obj: Any, path: str = ""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, obj


def resumir(resultado: dict) -> dict:
    """Resumo heurístico: {"consta": bool|None, "quantidade": int|None, "valor": float|None, "score": int|None, "texto": str}."""
    if not resultado.get("ok"):
        return {"consta": None, "quantidade": None, "valor": None, "score": None,
                "texto": f"indisponível ({resultado.get('error', 'erro')})"}
    data = resultado.get("data")
    consta: bool | None = None
    quantidade: int | None = None
    valor: float | None = None
    score: int | None = None
    lista_itens = 0
    for path, v in _walk(data):
        key = path.split(".")[-1].split("[")[0]
        if isinstance(v, str):
            if _NEG_WORDS.search(v):
                consta = False if consta is None else consta
            elif _POS_WORDS.search(v) and not _NEG_WORDS.search(v) and key.lower() not in ("tipo", "type"):
                consta = True
        if isinstance(v, bool):
            if _POS_WORDS.search(key) or key.lower() in ("consta", "possui", "restricao", "restrição"):
                consta = v if v else (consta if consta else False)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if _COUNT_KEYS.search(key) and (quantidade is None or v > quantidade) and v < 100000:
                quantidade = int(v)
            elif _VALUE_KEYS.search(key) and (valor is None or v > valor):
                valor = float(v)
            elif _SCORE_KEYS.search(key) and 0 <= v <= 1000:
                score = int(v)
    # lista de títulos/protestos/pendências dentro do payload
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                for k2, v2 in v.items():
                    if isinstance(v2, list) and re.search(r"(protesto|pend|titulo|título|restri|negativ|ocorr)", k2, re.I):
                        lista_itens += len(v2)
            if isinstance(v, list) and re.search(r"(protesto|pend|titulo|título|restri|negativ|ocorr)", k, re.I):
                lista_itens += len(v)
    if lista_itens and (quantidade is None or lista_itens > quantidade):
        quantidade = lista_itens
    if consta is None and quantidade is not None:
        consta = quantidade > 0
    if quantidade and quantidade > 0:
        consta = True
    partes = []
    if consta is True:
        partes.append("consta")
    elif consta is False:
        partes.append("nada consta")
    else:
        partes.append("sem leitura automática")
    if quantidade is not None:
        partes.append(f"{quantidade} registro(s)")
    if valor:
        partes.append(f"valor ~ R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    if score is not None:
        partes.append(f"score {score}")
    if resultado.get("homolog"):
        partes.append("[homologação]")
    return {"consta": consta, "quantidade": quantidade, "valor": valor, "score": score, "texto": ", ".join(partes)}


# ----------------------------------------------------------------- leitura estruturada
CATEGORIAS = {
    "protestos": "protesto(s)",
    "negativacoes": "negativação(ões)",
    "chequesSemFundo": "cheque(s) sem fundo",
    "acoesJudiciais": "ação(ões) judicial(is)",
    "recuperacoesJudiciaisFalencia": "recuperação judicial/falência",
}


def _find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find_key(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_key(v, key)
            if r is not None:
                return r
    return None


def _soma_valores(itens) -> float:
    total = 0.0
    for it in itens or []:
        if isinstance(it, dict):
            for k, v in it.items():
                if re.search(r"valor", k, re.I):
                    try:
                        total += float(str(v).replace(".", "").replace(",", ".")) if isinstance(v, str) else float(v)
                    except (TypeError, ValueError):
                        pass
                    break
    return total


def ler_pendencias(resultado: dict) -> dict:
    """Leitura do retorno de pendências financeiras (detalhamento-negativo e similares).
    Retorna {"consta", "quantidade", "valor", "detalhes": {categoria: n}, "texto", "estruturado"}."""
    if not resultado.get("ok"):
        return {"consta": None, "quantidade": None, "valor": None, "detalhes": {}, "estruturado": False,
                "texto": f"indisponível ({resultado.get('error', 'erro')})"}
    data = resultado.get("data") or {}
    corpo = data.get("data") if isinstance(data, dict) and isinstance(data.get("data"), dict) else data
    pf = _find_key(corpo, "pendenciaFinanceira")
    detalhes, valor = {}, 0.0
    fonte = pf if isinstance(pf, dict) else corpo
    achou = False
    for k in CATEGORIAS:
        itens = fonte.get(k) if isinstance(fonte, dict) else None
        if itens is None:
            itens = _find_key(corpo, k)
        if isinstance(itens, list):
            achou = True
            detalhes[k] = len(itens)
            valor += _soma_valores(itens)
    total = None
    for k in ("totalPendencia", "totalPendencias"):
        v = _find_key(corpo, k)
        if isinstance(v, (int, float)):
            total = int(v)
            achou = True
            break
    possui = _find_key(corpo, "possuiPendencias")
    if achou or isinstance(possui, bool):
        qtd = sum(detalhes.values())
        if total is not None:
            qtd = max(qtd, total)
        consta = qtd > 0 or possui is True
        if consta:
            partes = [f"{n} {CATEGORIAS[k]}" for k, n in detalhes.items() if n]
            texto = ", ".join(partes) or f"{qtd} pendência(s)"
            if valor:
                texto += f", total ~ R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            texto = "nada consta"
        if resultado.get("homolog"):
            texto += " [homologação]"
        return {"consta": consta, "quantidade": qtd, "valor": valor or None, "detalhes": detalhes,
                "estruturado": True, "texto": texto}
    r = resumir(resultado)
    r.update({"detalhes": {}, "estruturado": False})
    return r
