"""Pré-score EMG (verde / amarelo / vermelho) com fatores explicados.

O pré-score é orientativo: NÃO descarta leads. A decisão de triagem é humana (Guilherme/Eduarda).
Faixas iniciais (calibrar com casos reais nos primeiros 30 dias):
  verde    >= 65 pontos
  amarelo  40 a 64
  vermelho < 40, ou empresa com situação cadastral diferente de ATIVA
"""
from __future__ import annotations

from ..models import Prescore

BASE = 50
VERDE_MIN = 65
AMARELO_MIN = 40


def _f(label: str, pontos: int, detalhe: str = "") -> dict:
    nivel = "bom" if pontos > 0 else ("ruim" if pontos < 0 else "neutro")
    return {"label": label, "pontos": pontos, "detalhe": detalhe, "nivel": nivel}


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def calcular(cadastral: dict | None, bureau: dict | None) -> tuple[str, int, list[dict]]:
    """cadastral = saída de cadastral.consultar_cnpj; bureau = {"pj": {...}, "socios": [...]} (resumos)."""
    fatores: list[dict] = []
    pontos = BASE
    forcar_vermelho = False

    if not cadastral:
        fatores.append(_f("Dados cadastrais", 0, "não foi possível consultar a Receita Federal"))
    else:
        situacao = (cadastral.get("situacao") or "").upper()
        if situacao == "ATIVA":
            fatores.append(_f("Situação cadastral", 5, "ATIVA"))
            pontos += 5
        elif situacao:
            fatores.append(_f("Situação cadastral", -40, f"{situacao} (não ativa)"))
            pontos -= 40
            forcar_vermelho = True
        else:
            fatores.append(_f("Situação cadastral", 0, "não informada"))

        idade = _num(cadastral.get("idade_anos"))
        if idade is None:
            fatores.append(_f("Tempo de empresa", 0, "não informado"))
        elif idade >= 5:
            fatores.append(_f("Tempo de empresa", 15, f"{idade:.1f} anos"))
            pontos += 15
        elif idade >= 2:
            fatores.append(_f("Tempo de empresa", 5, f"{idade:.1f} anos"))
            pontos += 5
        elif idade >= 1:
            fatores.append(_f("Tempo de empresa", 0, f"{idade:.1f} anos"))
        else:
            fatores.append(_f("Tempo de empresa", -15, f"{idade:.1f} ano(s), empresa nova; avaliar sócios"))
            pontos -= 15

        porte = (cadastral.get("porte") or "").upper()
        mei = cadastral.get("mei")
        if mei is True:
            fatores.append(_f("Porte", -10, "MEI"))
            pontos -= 10
        elif "DEMAIS" in porte or "MEDIO" in porte or "MÉDIO" in porte or "GRANDE" in porte:
            fatores.append(_f("Porte", 10, porte.title()))
            pontos += 10
        elif "EPP" in porte or "PEQUENO" in porte:
            fatores.append(_f("Porte", 5, porte))
            pontos += 5
        elif porte:
            fatores.append(_f("Porte", 0, porte))
        else:
            fatores.append(_f("Porte", 0, "não informado"))

        capital = _num(cadastral.get("capital_social"))
        if capital is None:
            fatores.append(_f("Capital social", 0, "não informado"))
        elif capital >= 100_000:
            fatores.append(_f("Capital social", 10, f"R$ {capital:,.0f}".replace(",", ".")))
            pontos += 10
        elif capital >= 20_000:
            fatores.append(_f("Capital social", 5, f"R$ {capital:,.0f}".replace(",", ".")))
            pontos += 5
        elif capital < 5_000:
            fatores.append(_f("Capital social", -5, f"R$ {capital:,.0f}".replace(",", ".")))
            pontos -= 5
        else:
            fatores.append(_f("Capital social", 0, f"R$ {capital:,.0f}".replace(",", ".")))

        qsa = cadastral.get("qsa") or []
        fatores.append(_f("Quadro societário", 0, f"{len(qsa)} sócio(s)" if qsa else "não informado"))

    # ---- bureau PJ
    pj = (bureau or {}).get("pj") or {}
    for chave, label, peso_ruim, peso_bom in (
        ("protestos", "Protestos (CNPJ)", -20, 5),
        ("negativacao", "Negativações (CNPJ)", -20, 5),
        ("certidao", "Débitos federais / PGFN (CNPJ)", -10, 5),
    ):
        r = pj.get(chave)
        if not r:
            fatores.append(_f(label, 0, "não consultado"))
            continue
        if r.get("consta") is True:
            extra = 0
            if r.get("quantidade"):
                extra = -min(10, int(r["quantidade"]) * 2)
            fatores.append(_f(label, peso_ruim + extra, r.get("texto", "consta")))
            pontos += peso_ruim + extra
        elif r.get("consta") is False:
            fatores.append(_f(label, peso_bom, r.get("texto", "nada consta")))
            pontos += peso_bom
        else:
            fatores.append(_f(label, 0, r.get("texto", "sem leitura automática; conferir o retorno bruto")))

    # ---- bureau sócios (só com consentimento LGPD)
    socios = (bureau or {}).get("socios") or []
    for s in socios:
        nome = s.get("nome") or "Sócio"
        for chave, label, peso_ruim, peso_bom in (
            ("protestos", "Protestos", -10, 3),
            ("negativacao", "Negativações", -10, 3),
            ("divida_ativa", "Dívida ativa", -5, 2),
        ):
            r = s.get(chave)
            if not r:
                continue
            if r.get("consta") is True:
                fatores.append(_f(f"{label} ({nome})", peso_ruim, r.get("texto", "consta")))
                pontos += peso_ruim
            elif r.get("consta") is False:
                fatores.append(_f(f"{label} ({nome})", peso_bom, r.get("texto", "nada consta")))
                pontos += peso_bom
            else:
                fatores.append(_f(f"{label} ({nome})", 0, r.get("texto", "sem leitura automática")))
    if not socios:
        fatores.append(_f("Consulta dos sócios (CPF)", 0, "não realizada (precisa de aceite LGPD e CPF dos sócios)"))

    pontos = max(0, min(100, pontos))
    if forcar_vermelho or pontos < AMARELO_MIN:
        cor = Prescore.VERMELHO
    elif pontos >= VERDE_MIN:
        cor = Prescore.VERDE
    else:
        cor = Prescore.AMARELO
    return cor, pontos, fatores
