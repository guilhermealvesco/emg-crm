"""Utilitários: datas, CNPJ/CPF, formatação em R$."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime

from .config import settings


def now_local() -> datetime:
    """Horário local (America/Recife) sem tzinfo, para gravar no banco de forma uniforme."""
    return datetime.now(settings.TZ).replace(tzinfo=None)


def today_local() -> date:
    return now_local().date()


def only_digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def validate_cnpj(cnpj: str) -> bool:
    c = only_digits(cnpj)
    if len(c) != 14 or c == c[0] * 14:
        return False

    def dv(base: str, weights: list[int]) -> int:
        s = sum(int(d) * w for d, w in zip(base, weights))
        r = s % 11
        return 0 if r < 2 else 11 - r

    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    w2 = [6] + w1
    d1 = dv(c[:12], w1)
    d2 = dv(c[:12] + str(d1), w2)
    return c[12:] == f"{d1}{d2}"


def validate_cpf(cpf: str) -> bool:
    c = only_digits(cpf)
    if len(c) != 11 or c == c[0] * 11:
        return False
    for n in (9, 10):
        s = sum(int(c[i]) * (n + 1 - i) for i in range(n))
        d = (s * 10) % 11
        d = 0 if d == 10 else d
        if d != int(c[n]):
            return False
    return True


def fmt_cnpj(cnpj: str | None) -> str:
    c = only_digits(cnpj)
    if len(c) != 14:
        return cnpj or ""
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def fmt_cpf(cpf: str | None) -> str:
    c = only_digits(cpf)
    if len(c) != 11:
        return cpf or ""
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"


def mask_cpf(cpf: str | None) -> str:
    c = only_digits(cpf)
    if len(c) != 11:
        return "***"
    return f"***.{c[3:6]}.{c[6:9]}-**"


def brl(value: float | None) -> str:
    if value is None:
        return "R$ 0,00"
    s = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def parse_brl(value: str | None) -> float | None:
    """Aceita '6.000,00', '6000', 'R$ 6.000', '6000.50'."""
    if value is None:
        return None
    v = value.strip().replace("R$", "").replace(" ", "")
    if not v:
        return None
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", v):  # 250.000 = duzentos e cinquenta mil
        v = v.replace(".", "")
    try:
        return float(v)
    except ValueError:
        return None


def slugify_name(name: str) -> str:
    """'Padaria do João LTDA' -> 'Padaria-do-Joao-LTDA' (para nome de arquivo de contrato)."""
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    n = re.sub(r"[^A-Za-z0-9]+", "-", n).strip("-")
    return n or "Cliente"


def fmt_dt(dt: datetime | None, with_time: bool = True) -> str:
    if not dt:
        return ""
    return dt.strftime("%d/%m/%Y %H:%M") if with_time else dt.strftime("%d/%m/%Y")


def fmt_date(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def days_since(dt: datetime | date | None) -> int | None:
    if dt is None:
        return None
    d = dt.date() if isinstance(dt, datetime) else dt
    return (today_local() - d).days


def extenso_reais(valor: float) -> str:
    """Valor por extenso simplificado (até milhões), para o contrato."""
    unidades = ["", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze",
                "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
    dezenas = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
    centenas = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos",
                "oitocentos", "novecentos"]

    def ate_999(n: int) -> str:
        if n == 0:
            return ""
        if n == 100:
            return "cem"
        partes = []
        c, r = divmod(n, 100)
        if c:
            partes.append(centenas[c])
        if r < 20:
            if r:
                partes.append(unidades[r])
        else:
            d, u = divmod(r, 10)
            partes.append(dezenas[d] + (f" e {unidades[u]}" if u else ""))
        return " e ".join(partes)

    inteiro = int(round(valor))
    centavos = int(round((valor - int(valor)) * 100))
    if inteiro == 0:
        texto = "zero reais"
    else:
        milhoes, resto = divmod(inteiro, 1_000_000)
        milhares, cent = divmod(resto, 1000)
        partes = []
        if milhoes:
            partes.append(("um milhão" if milhoes == 1 else f"{ate_999(milhoes)} milhões"))
        if milhares:
            partes.append("mil" if milhares == 1 else f"{ate_999(milhares)} mil")
        if cent:
            partes.append(ate_999(cent))
        texto = " e ".join(partes) + (" real" if inteiro == 1 else " reais")
    if centavos:
        texto += f" e {ate_999(centavos)} centavo{'s' if centavos > 1 else ''}"
    return texto
