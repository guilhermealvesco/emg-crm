"""Dados cadastrais do CNPJ via fontes gratuitas (BrasilAPI, com Minha Receita como fallback).

Retorna sempre um dicionário normalizado:
{
  "fonte": "brasilapi" | "minhareceita",
  "razao_social", "nome_fantasia", "situacao", "situacao_data", "data_abertura", "idade_anos",
  "porte", "natureza_juridica", "capital_social", "cnae_codigo", "cnae_descricao", "cnaes_secundarios": [..],
  "municipio", "uf", "telefone", "email", "simples", "mei",
  "qsa": [{"nome", "qualificacao", "cpf_mascarado", "entrada"}],
  "raw": {...}
}
"""
from __future__ import annotations

from datetime import date

import httpx

from ..config import settings
from ..utils import only_digits, today_local

TIMEOUT = 20.0


class CadastralError(Exception):
    pass


def _idade(data_abertura: str | None) -> float | None:
    if not data_abertura:
        return None
    try:
        d = date.fromisoformat(data_abertura[:10])
    except ValueError:
        return None
    return round((today_local() - d).days / 365.25, 1)


def _from_brasilapi(data: dict) -> dict:
    qsa = []
    for s in data.get("qsa") or []:
        qsa.append({
            "nome": s.get("nome_socio"),
            "qualificacao": s.get("qualificacao_socio"),
            "cpf_mascarado": s.get("cnpj_cpf_do_socio"),
            "entrada": s.get("data_entrada_sociedade"),
        })
    situacao = data.get("descricao_situacao_cadastral")
    return {
        "fonte": "brasilapi",
        "razao_social": data.get("razao_social"),
        "nome_fantasia": data.get("nome_fantasia"),
        "situacao": situacao,
        "situacao_data": data.get("data_situacao_cadastral"),
        "data_abertura": data.get("data_inicio_atividade"),
        "idade_anos": _idade(data.get("data_inicio_atividade")),
        "porte": data.get("porte") or data.get("descricao_porte"),
        "natureza_juridica": data.get("natureza_juridica"),
        "capital_social": data.get("capital_social"),
        "cnae_codigo": data.get("cnae_fiscal"),
        "cnae_descricao": data.get("cnae_fiscal_descricao"),
        "cnaes_secundarios": [c.get("descricao") for c in (data.get("cnaes_secundarios") or []) if c.get("codigo")],
        "municipio": data.get("municipio"),
        "uf": data.get("uf"),
        "telefone": data.get("ddd_telefone_1"),
        "email": data.get("email"),
        "simples": data.get("opcao_pelo_simples"),
        "mei": data.get("opcao_pelo_mei"),
        "qsa": qsa,
        "raw": data,
    }


def _from_minhareceita(data: dict) -> dict:
    qsa = []
    for s in data.get("qsa") or []:
        qsa.append({
            "nome": s.get("nome_socio"),
            "qualificacao": s.get("qualificacao_socio"),
            "cpf_mascarado": s.get("cnpj_cpf_do_socio"),
            "entrada": s.get("data_entrada_sociedade"),
        })
    return {
        "fonte": "minhareceita",
        "razao_social": data.get("razao_social"),
        "nome_fantasia": data.get("nome_fantasia"),
        "situacao": data.get("descricao_situacao_cadastral"),
        "situacao_data": data.get("data_situacao_cadastral"),
        "data_abertura": data.get("data_inicio_atividade"),
        "idade_anos": _idade(data.get("data_inicio_atividade")),
        "porte": data.get("porte"),
        "natureza_juridica": data.get("natureza_juridica"),
        "capital_social": data.get("capital_social"),
        "cnae_codigo": data.get("cnae_fiscal"),
        "cnae_descricao": data.get("cnae_fiscal_descricao"),
        "cnaes_secundarios": [c.get("descricao") for c in (data.get("cnaes_secundarios") or []) if c.get("codigo")],
        "municipio": data.get("municipio"),
        "uf": data.get("uf"),
        "telefone": data.get("ddd_telefone_1"),
        "email": data.get("email"),
        "simples": data.get("opcao_pelo_simples"),
        "mei": data.get("opcao_pelo_mei"),
        "qsa": qsa,
        "raw": data,
    }


def consultar_cnpj(cnpj: str) -> dict:
    """Tenta BrasilAPI e depois Minha Receita. Levanta CadastralError se as duas falharem."""
    c = only_digits(cnpj)
    errors: list[str] = []
    with httpx.Client(timeout=TIMEOUT, headers={"User-Agent": "EMG-CRM/1.0"}) as client:
        try:
            r = client.get(f"{settings.BRASILAPI_URL}/{c}")
            if r.status_code == 200:
                return _from_brasilapi(r.json())
            if r.status_code == 404:
                raise CadastralError("CNPJ não encontrado na Receita Federal.")
            errors.append(f"BrasilAPI HTTP {r.status_code}")
        except CadastralError:
            raise
        except httpx.HTTPError as e:
            errors.append(f"BrasilAPI: {e}")
        try:
            r = client.get(f"{settings.MINHARECEITA_URL}/{c}")
            if r.status_code == 200:
                return _from_minhareceita(r.json())
            if r.status_code == 404:
                raise CadastralError("CNPJ não encontrado na Receita Federal.")
            errors.append(f"MinhaReceita HTTP {r.status_code}")
        except CadastralError:
            raise
        except httpx.HTTPError as e:
            errors.append(f"MinhaReceita: {e}")
    raise CadastralError("Fontes cadastrais indisponíveis: " + "; ".join(errors))
