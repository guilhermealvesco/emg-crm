"""Configuração central do EMG CRM. Tudo vem do ambiente (.env na VPS)."""
from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "sim", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Settings:
    # --- app ---
    APP_NAME = "EMG CRM"
    ENV = _env("APP_ENV", "dev")
    SECRET_KEY = _env("SECRET_KEY", "troque-esta-chave-no-env")
    DATABASE_URL = _env("DATABASE_URL", f"sqlite:///{BASE_DIR / 'storage' / 'emg.db'}")
    PUBLIC_URL = _env("PUBLIC_URL", "http://localhost:8000").rstrip("/")
    TZ = ZoneInfo(_env("TZ", "America/Recife"))
    STORAGE_DIR = Path(_env("STORAGE_DIR", str(BASE_DIR / "storage")))
    CONTRACTS_DIR = STORAGE_DIR / "contratos"

    # --- regras de negócio (acordadas, não alterar sem decisão do Guilherme) ---
    OWNERSHIP_DAYS = _env_int("OWNERSHIP_DAYS", 90)          # dono do lead por 90 dias
    TARIFA_TABELA = 6000.0                                    # tabela da tarifa de estruturação
    TARIFA_PISO_EMG = 5000.0                                  # piso líquido da EMG
    EXITO_INDICACAO = (0.03, 0.01, 500_000.0)                 # 3% até 500k, 1% excedente
    EXITO_FECHAMENTO = (0.05, 0.02, 500_000.0)                # 5% até 500k, 2% excedente
    BANCOS = ["Itaú", "Santander", "Bradesco", "Caixa", "BNB"]

    # --- alertas (dias) ---
    ALERTA_SEM_MOVIMENTO = _env_int("ALERTA_SEM_MOVIMENTO", 7)
    ALERTA_BANCO_NAO_ENVIADO = _env_int("ALERTA_BANCO_NAO_ENVIADO", 3)
    ALERTA_SEM_FOLLOWUP = _env_int("ALERTA_SEM_FOLLOWUP", 30)
    POSICAO_CLIENTE_DIAS = _env_int("POSICAO_CLIENTE_DIAS", 7)   # tarefa "dar posição" a cada 7 dias

    # --- fontes gratuitas ---
    BRASILAPI_URL = _env("BRASILAPI_URL", "https://brasilapi.com.br/api/cnpj/v1")
    MINHARECEITA_URL = _env("MINHARECEITA_URL", "https://minhareceita.org")

    # --- APIBrasil (consultas por crédito) ---
    APIBRASIL_URL = _env("APIBRASIL_URL", "https://gateway.apibrasil.io/api/v2").rstrip("/")
    APIBRASIL_TOKEN = _env("APIBRASIL_TOKEN", "")
    APIBRASIL_HOMOLOG = _env_bool("APIBRASIL_HOMOLOG", True)   # True = não gasta créditos
    APIBRASIL_ENABLED = _env_bool("APIBRASIL_ENABLED", False)
    # Uma consulta por documento: "detalhamento-negativo" traz protestos, negativações, cheques sem fundo,
    # ações judiciais e recuperação judicial/falência no mesmo retorno. Vazio = desligado.
    APIBRASIL_TIPO_PJ = _env("APIBRASIL_TIPO_PJ", "detalhamento-negativo")
    APIBRASIL_TIPO_PF = _env("APIBRASIL_TIPO_PF", "")  # sócios: desligado até escolher o produto PF
    APIBRASIL_CUSTO_ESTIMADO = _env("APIBRASIL_CUSTO_ESTIMADO", "12,00")

    # --- Autentique ---
    AUTENTIQUE_URL = _env("AUTENTIQUE_URL", "https://api.autentique.com.br/v2/graphql")
    AUTENTIQUE_TOKEN = _env("AUTENTIQUE_TOKEN", "")
    AUTENTIQUE_SANDBOX = _env_bool("AUTENTIQUE_SANDBOX", True)
    AUTENTIQUE_WEBHOOK_SECRET = _env("AUTENTIQUE_WEBHOOK_SECRET", "")
    AUTENTIQUE_VERIFICATION = _env("AUTENTIQUE_VERIFICATION", "LIVE")  # LIVE = doc + selfie + prova de vida
    AUTENTIQUE_SIGNER_EMG_EMAIL = _env("AUTENTIQUE_SIGNER_EMG_EMAIL", "")  # e-mail da EMG que também assina (opcional)

    # --- dados cadastrais da EMG (constam no contrato) ---
    EMG_RAZAO = "EMG SOLUÇÕES EMPRESARIAIS LTDA"
    EMG_FANTASIA = "EM CONSULTORIA EMPRESARIAL"
    EMG_CNPJ = "60.975.099/0001-79"
    EMG_ENDERECO = "Av. República do Líbano, 251, Sala 2501 Torre A, Pina, Recife/PE, CEP 51.110-160"
    EMG_REPRESENTANTE = _env("EMG_REPRESENTANTE", "Flávia")
    EMG_REPRESENTANTE_CPF = _env("EMG_REPRESENTANTE_CPF", "086.447.674-45")
    EMG_EMAIL = _env("EMG_EMAIL", "contato@emfinanceira.com")
    EMG_TELEFONE = _env("EMG_TELEFONE", "(81) 99528-0353")
    EMG_PIX = "CNPJ 60.975.099/0001-79, Banco Bradesco PJ"


settings = Settings()
settings.CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)
