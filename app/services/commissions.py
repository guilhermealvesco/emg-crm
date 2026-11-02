"""Regras de comissão dos captadores (acordadas e distribuídas, não alterar).

- Tarifa de estruturação: tabela R$ 6.000, piso de R$ 5.000 líquidos para a EMG; excedente negociado é 100% do captador.
- Êxito indicação: 3% até R$ 500.000 + 1% sobre o excedente.
- Êxito fechamento completo: 5% até R$ 500.000 + 2% sobre o excedente.
- Comissão paga somente após recebimento efetivo pela EMG, por liberação.
"""
from __future__ import annotations

from ..config import settings
from ..models import ExitoTipo


def comissao_tarifa(tarifa_valor: float | None) -> float:
    """Excedente acima do piso da EMG vai integralmente ao captador."""
    if not tarifa_valor:
        return 0.0
    return round(max(0.0, float(tarifa_valor) - settings.TARIFA_PISO_EMG), 2)


def comissao_exito(valor_liberado: float, exito_tipo: str) -> float:
    pct_base, pct_exc, teto = settings.EXITO_INDICACAO if exito_tipo == ExitoTipo.INDICACAO else settings.EXITO_FECHAMENTO
    v = float(valor_liberado or 0)
    if v <= teto:
        return round(v * pct_base, 2)
    return round(teto * pct_base + (v - teto) * pct_exc, 2)


def calcular(valor_liberado: float, exito_tipo: str, tarifa_valor: float | None, primeira_liberacao: bool) -> dict:
    """A comissão da tarifa é paga uma vez (na primeira liberação do lead)."""
    c_tar = comissao_tarifa(tarifa_valor) if primeira_liberacao else 0.0
    c_ex = comissao_exito(valor_liberado, exito_tipo)
    return {"comissao_tarifa": c_tar, "comissao_exito": c_ex, "comissao_total": round(c_tar + c_ex, 2)}


def validar_tarifa(valor: float | None) -> str | None:
    if valor is None:
        return "Informe o valor da tarifa."
    if valor < settings.TARIFA_PISO_EMG:
        return f"A tarifa não pode ficar abaixo do piso de R$ {settings.TARIFA_PISO_EMG:,.0f} líquidos para a EMG.".replace(",", ".")
    return None
