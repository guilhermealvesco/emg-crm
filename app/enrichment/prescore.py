"""Pré-score EMG (verde / amarelo / vermelho) com fatores explicados.

O pré-score é orientativo: NÃO descarta leads. A decisão de triagem é humana (Guilherme/Eduarda).
Faixas iniciais (calibrar com casos reais nos primeiros 30 dias):
  verde    >= 60 pontos
  amarelo  35 a 59
  vermelho < 35, ou empresa com situação cadastral diferente de ATIVA
"""
from __future__ import annotations

from ..models import Prescore

BASE = 50
VERDE_MIN = 60
AMARELO_MIN = 35

# Bureau (régua revista em 05/11/2026: descontos com teto, para não zerar empresa boa com problema pontual)
NADA_CONSTA_PJ = 10
PESOS_PJ = {"protestos": -12, "negativacoes": -12, "chequesSemFundo": -8, "acoesJudiciais": -5}
TETO_PJ = -30            # soma máxima de descontos do CNPJ (fora RJ/falência)
PESO_RJ = -30            # recuperação judicial / falência
PESO_SOCIO = -5          # por categoria com pendência
TETO_SOCIOS = -15        # soma máxima de descontos de todos os sócios
NADA_CONSTA_SOCIO = 3
BONUS_SOCIOS_MAX = 6


def apibrasil_label(k: str) -> str:
    return {"protestos": "Protestos", "negativacoes": "Negativações", "chequesSemFundo": "Cheques sem fundo",
            "acoesJudiciais": "Ações judiciais"}.get(k, k)


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

    # ---- bureau PJ (uma consulta de pendências financeiras)
    pj = (bureau or {}).get("pj") or {}
    r = pj.get("pendencias")
    if not r:
        fatores.append(_f("Pendências financeiras (CNPJ)", 0, "não consultado"))
    elif r.get("homolog"):
        fatores.append(_f("Pendências financeiras (CNPJ)", 0, "modo teste (homologação): dado fictício, não pontua"))
    elif r.get("consta") is False:
        fatores.append(_f("Pendências financeiras (CNPJ)", NADA_CONSTA_PJ, "nada consta"))
        pontos += NADA_CONSTA_PJ
    elif r.get("consta") is True:
        det = r.get("detalhes") or {}
        if det.get("recuperacoesJudiciaisFalencia"):
            fatores.append(_f("Recuperação judicial / falência", PESO_RJ, f"{det['recuperacoesJudiciaisFalencia']} registro(s)"))
            pontos += PESO_RJ
        soma = 0
        itens = []
        for k, peso in PESOS_PJ.items():
            if det.get(k):
                soma += peso
                itens.append(_f(f"{apibrasil_label(k)} (CNPJ)", peso, f"{det[k]} registro(s)"))
        if not itens:  # consta, mas sem detalhe por categoria
            soma = PESOS_PJ["negativacoes"]
            itens.append(_f("Pendências financeiras (CNPJ)", soma, r.get("texto", "consta")))
        if soma < TETO_PJ:
            itens.append(_f("Teto de desconto do bureau (CNPJ)", TETO_PJ - soma, f"desconto limitado a {TETO_PJ}"))
            soma = TETO_PJ
        fatores += itens
        pontos += soma
    else:
        fatores.append(_f("Pendências financeiras (CNPJ)", 0, r.get("texto", "sem leitura automática; conferir o retorno bruto")))

    # ---- bureau sócios (só com consentimento LGPD)
    socios = (bureau or {}).get("socios") or []
    desc_socios = 0
    bonus_socios = 0
    for s_ in socios:
        nome = s_.get("nome") or "Sócio"
        r = s_.get("pendencias")
        if not r:
            continue
        if r.get("homolog"):
            fatores.append(_f(f"Pendências ({nome})", 0, "modo teste (homologação): não pontua"))
        elif r.get("consta") is True:
            det = r.get("detalhes") or {}
            n_cat = sum(1 for k in PESOS_PJ if det.get(k)) or 1
            d = max(TETO_SOCIOS - desc_socios, PESO_SOCIO * n_cat)
            desc_socios += d
            fatores.append(_f(f"Pendências ({nome})", d, r.get("texto", "consta")))
        elif r.get("consta") is False:
            b_ = min(NADA_CONSTA_SOCIO, BONUS_SOCIOS_MAX - bonus_socios)
            bonus_socios += b_
            fatores.append(_f(f"Pendências ({nome})", b_, "nada consta"))
        else:
            fatores.append(_f(f"Pendências ({nome})", 0, r.get("texto", "sem leitura automática")))
    pontos += desc_socios + bonus_socios
    if not socios:
        fatores.append(_f("Consulta dos sócios (CPF)", 0, "não realizada"))

    pontos = max(0, min(100, pontos))
    if forcar_vermelho or pontos < AMARELO_MIN:
        cor = Prescore.VERMELHO
    elif pontos >= VERDE_MIN:
        cor = Prescore.VERDE
    else:
        cor = Prescore.AMARELO
    return cor, pontos, fatores


def recalcular_lead(lead) -> None:
    """Recalcula com os dados já guardados no lead, sem nova consulta (não gasta crédito)."""
    enr = lead.enrichment or {}
    cor, pontos, fatores = calcular(enr.get("cadastral"), enr.get("bureau"))
    lead.prescore, lead.prescore_pontos, lead.prescore_fatores = cor, pontos, fatores
