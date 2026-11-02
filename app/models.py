"""Modelo de dados do EMG CRM."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .utils import now_local


# ---------------------------------------------------------------- constantes
class Role:
    ADMIN = "admin"          # Guilherme
    OPERACAO = "operacao"    # Eduarda
    CAPTADOR = "captador"
    ALL = (ADMIN, OPERACAO, CAPTADOR)
    LABELS = {ADMIN: "Administrador", OPERACAO: "Operação", CAPTADOR: "Captador"}


class Stage:
    """Funil: Novo → Triagem → Nos bancos → Retorno → Cobrança/contrato → Docs → Liberação → Comissão paga."""
    NOVO = "novo"
    TRIAGEM = "triagem"
    BANCOS = "bancos"
    RETORNO = "retorno"
    COBRANCA = "cobranca"
    DOCS = "docs"
    LIBERACAO = "liberacao"
    COMISSAO_PAGA = "comissao_paga"
    PERDIDO = "perdido"

    ORDER = [NOVO, TRIAGEM, BANCOS, RETORNO, COBRANCA, DOCS, LIBERACAO, COMISSAO_PAGA]
    LABELS = {
        NOVO: "Novo", TRIAGEM: "Triagem", BANCOS: "Nos bancos", RETORNO: "Retorno",
        COBRANCA: "Cobrança / contrato", DOCS: "Docs", LIBERACAO: "Liberação",
        COMISSAO_PAGA: "Comissão paga", PERDIDO: "Perdido",
    }

    @classmethod
    def index(cls, stage: str) -> int:
        return cls.ORDER.index(stage) if stage in cls.ORDER else -1


class BankStatus:
    NAO_ENVIADO = "nao_enviado"
    ENVIADO = "enviado"
    RETORNO_BOM = "retorno_bom"
    RETORNO_RUIM = "retorno_ruim"
    ALL = (NAO_ENVIADO, ENVIADO, RETORNO_BOM, RETORNO_RUIM)
    LABELS = {NAO_ENVIADO: "Não enviado", ENVIADO: "Enviado", RETORNO_BOM: "Retorno bom", RETORNO_RUIM: "Retorno ruim"}


class Prescore:
    VERDE = "verde"
    AMARELO = "amarelo"
    VERMELHO = "vermelho"
    PENDENTE = "pendente"
    LABELS = {VERDE: "Verde", AMARELO: "Amarelo", VERMELHO: "Vermelho", PENDENTE: "Pendente"}


class TaskType:
    POSICAO = "posicao"            # dar posição ao cliente (captador)
    ENVIAR_BANCO = "enviar_banco"  # Eduarda
    DOCS = "docs"
    FOLLOWUP = "followup"
    OUTRO = "outro"
    LABELS = {POSICAO: "Dar posição ao cliente", ENVIAR_BANCO: "Enviar para banco", DOCS: "Documentação",
              FOLLOWUP: "Follow-up", OUTRO: "Outro"}


class ContractStatus:
    RASCUNHO = "rascunho"
    ENVIADO = "enviado"
    ASSINADO = "assinado"
    RECUSADO = "recusado"
    CANCELADO = "cancelado"
    LABELS = {RASCUNHO: "Rascunho", ENVIADO: "Enviado p/ assinatura", ASSINADO: "Assinado",
              RECUSADO: "Recusado", CANCELADO: "Cancelado"}


class ExitoTipo:
    INDICACAO = "indicacao"
    FECHAMENTO = "fechamento"
    LABELS = {INDICACAO: "Indicação (3% + 1%)", FECHAMENTO: "Fechamento completo (5% + 2%)"}


# ---------------------------------------------------------------- tabelas
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(190), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default=Role.CAPTADOR)
    phone: Mapped[str | None] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    leads: Mapped[list["Lead"]] = relationship(back_populates="captador", foreign_keys="Lead.captador_id")

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def is_staff(self) -> bool:
        return self.role in (Role.ADMIN, Role.OPERACAO)


class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[int] = mapped_column(primary_key=True)
    cnpj: Mapped[str] = mapped_column(String(14), unique=True, index=True)  # só dígitos
    razao_social: Mapped[str | None] = mapped_column(String(255))
    nome_fantasia: Mapped[str | None] = mapped_column(String(255))

    contato_nome: Mapped[str | None] = mapped_column(String(120))
    contato_telefone: Mapped[str | None] = mapped_column(String(40))
    contato_email: Mapped[str | None] = mapped_column(String(190))
    contato_cpf: Mapped[str | None] = mapped_column(String(11))  # CPF do representante/sócio (p/ contrato)
    origem: Mapped[str | None] = mapped_column(String(80))
    observacao: Mapped[str | None] = mapped_column(Text)
    valor_pretendido: Mapped[float | None] = mapped_column(Float)

    captador_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    owner_until: Mapped[date] = mapped_column(Date)  # dono até (90 dias, renovável por contato)

    stage: Mapped[str] = mapped_column(String(30), default=Stage.NOVO, index=True)
    stage_changed_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime)   # último contato com o cliente
    last_posicao_at: Mapped[datetime | None] = mapped_column(DateTime)   # última "posição" dada ao cliente
    docs_pendentes: Mapped[bool] = mapped_column(Boolean, default=False)
    docs_obs: Mapped[str | None] = mapped_column(Text)
    motivo_perda: Mapped[str | None] = mapped_column(Text)

    # LGPD: consentimento do cliente para consulta de CPF dos sócios
    lgpd_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    lgpd_consent_at: Mapped[datetime | None] = mapped_column(DateTime)
    lgpd_consent_by: Mapped[str | None] = mapped_column(String(120))  # nome de quem confirmou (cliente)
    lgpd_consent_meio: Mapped[str | None] = mapped_column(String(80))  # whatsapp/email/presencial
    socios_cpf: Mapped[list | None] = mapped_column(JSON)  # [{"nome": .., "cpf": "11 dígitos"}] informados pelo captador

    # enriquecimento + pré-score
    enrichment: Mapped[dict | None] = mapped_column(JSON)
    enrichment_at: Mapped[datetime | None] = mapped_column(DateTime)
    enrichment_error: Mapped[str | None] = mapped_column(Text)
    prescore: Mapped[str] = mapped_column(String(12), default=Prescore.PENDENTE)
    prescore_pontos: Mapped[int | None] = mapped_column(Integer)
    prescore_fatores: Mapped[list | None] = mapped_column(JSON)

    # triagem (decisão humana)
    triagem_decisao: Mapped[str | None] = mapped_column(String(12))  # aprovado / reprovado
    triagem_por_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    triagem_at: Mapped[datetime | None] = mapped_column(DateTime)
    triagem_obs: Mapped[str | None] = mapped_column(Text)

    # cobrança da tarifa (trava do funil)
    tarifa_valor: Mapped[float | None] = mapped_column(Float)
    tarifa_recebida: Mapped[bool] = mapped_column(Boolean, default=False)
    tarifa_recebida_em: Mapped[date | None] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)

    captador: Mapped["User"] = relationship(back_populates="leads", foreign_keys=[captador_id])
    triagem_por: Mapped["User | None"] = relationship(foreign_keys=[triagem_por_id])
    activities: Mapped[list["Activity"]] = relationship(back_populates="lead", cascade="all, delete-orphan",
                                                         order_by="Activity.created_at.desc()")
    banks: Mapped[list["BankSubmission"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    contracts: Mapped[list["Contract"]] = relationship(back_populates="lead", cascade="all, delete-orphan",
                                                        order_by="Contract.created_at.desc()")
    disbursements: Mapped[list["Disbursement"]] = relationship(back_populates="lead", cascade="all, delete-orphan")

    @property
    def nome(self) -> str:
        return self.nome_fantasia or self.razao_social or self.cnpj

    @property
    def stage_label(self) -> str:
        return Stage.LABELS.get(self.stage, self.stage)

    @property
    def prescore_label(self) -> str:
        return Prescore.LABELS.get(self.prescore, self.prescore)


class Activity(Base):
    """Histórico do lead: contatos, notas, mudanças de etapa, eventos do sistema."""
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    tipo: Mapped[str] = mapped_column(String(30))  # contato / nota / etapa / sistema / banco / contrato / posicao
    descricao: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, index=True)

    lead: Mapped["Lead"] = relationship(back_populates="activities")
    user: Mapped["User | None"] = relationship()


class BankSubmission(Base):
    """Matriz de bancos: um registro por lead x banco."""
    __tablename__ = "bank_submissions"
    __table_args__ = (UniqueConstraint("lead_id", "banco", name="uq_lead_banco"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    banco: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default=BankStatus.NAO_ENVIADO)
    valor_estimado: Mapped[float | None] = mapped_column(Float)
    observacao: Mapped[str | None] = mapped_column(Text)
    gerente: Mapped[str | None] = mapped_column(String(120))
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime)
    retorno_em: Mapped[datetime | None] = mapped_column(DateTime)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)

    lead: Mapped["Lead"] = relationship(back_populates="banks")

    @property
    def status_label(self) -> str:
        return BankStatus.LABELS.get(self.status, self.status)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"), index=True)
    assigned_to_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    tipo: Mapped[str] = mapped_column(String(30), default=TaskType.OUTRO)
    titulo: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    done: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime)
    auto: Mapped[bool] = mapped_column(Boolean, default=False)  # gerada pelo sistema
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    lead: Mapped["Lead | None"] = relationship(back_populates="tasks")
    assigned_to: Mapped["User"] = relationship(foreign_keys=[assigned_to_id])

    @property
    def atrasada(self) -> bool:
        return (not self.done) and self.due_date is not None and self.due_date < now_local().date()


class Contract(Base):
    __tablename__ = "contracts"
    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # qualificação do cliente (editável pelo captador)
    razao_social: Mapped[str] = mapped_column(String(255))
    nome_fantasia: Mapped[str | None] = mapped_column(String(255))
    cnpj: Mapped[str] = mapped_column(String(20))
    ie_rg: Mapped[str | None] = mapped_column(String(40))
    endereco: Mapped[str | None] = mapped_column(String(255))
    cep: Mapped[str | None] = mapped_column(String(12))
    cidade_uf: Mapped[str | None] = mapped_column(String(80))
    telefone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str] = mapped_column(String(190))          # e-mail do signatário
    representante: Mapped[str] = mapped_column(String(120))
    representante_cpf: Mapped[str] = mapped_column(String(14))
    # condições (só tarifa e forma de pagamento são editáveis)
    tarifa_valor: Mapped[float] = mapped_column(Float)
    forma_pagamento: Mapped[str] = mapped_column(String(255))
    # estado
    status: Mapped[str] = mapped_column(String(20), default=ContractStatus.RASCUNHO)
    file_basename: Mapped[str] = mapped_column(String(255))  # {Nome-da-Empresa}-Contrato-Consultoria-Credito
    pdf_path: Mapped[str | None] = mapped_column(String(500))
    signed_pdf_path: Mapped[str | None] = mapped_column(String(500))
    autentique_id: Mapped[str | None] = mapped_column(String(120), index=True)
    autentique_link: Mapped[str | None] = mapped_column(String(500))
    sandbox: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    lead: Mapped["Lead"] = relationship(back_populates="contracts")
    created_by: Mapped["User"] = relationship()

    @property
    def status_label(self) -> str:
        return ContractStatus.LABELS.get(self.status, self.status)


class Disbursement(Base):
    """Liberação de crédito registrada. Gera a comissão do captador."""
    __tablename__ = "disbursements"
    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    captador_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    banco: Mapped[str] = mapped_column(String(30))
    valor_liberado: Mapped[float] = mapped_column(Float)
    data_liberacao: Mapped[date] = mapped_column(Date)
    exito_tipo: Mapped[str] = mapped_column(String(20))  # indicacao / fechamento
    honorarios_emg: Mapped[float | None] = mapped_column(Float)  # êxito cobrado do cliente (informativo)
    # comissão calculada
    comissao_tarifa: Mapped[float] = mapped_column(Float, default=0.0)
    comissao_exito: Mapped[float] = mapped_column(Float, default=0.0)
    comissao_total: Mapped[float] = mapped_column(Float, default=0.0)
    # recebimento da EMG e pagamento ao captador
    emg_recebeu: Mapped[bool] = mapped_column(Boolean, default=False)
    emg_recebeu_em: Mapped[date | None] = mapped_column(Date)
    comissao_paga: Mapped[bool] = mapped_column(Boolean, default=False)
    comissao_paga_em: Mapped[date | None] = mapped_column(Date)
    observacao: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    lead: Mapped["Lead"] = relationship(back_populates="disbursements")
    captador: Mapped["User"] = relationship(foreign_keys=[captador_id])


class WebhookEvent(Base):
    """Eventos recebidos (idempotência do webhook do Autentique)."""
    __tablename__ = "webhook_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(30))
    event_id: Mapped[str] = mapped_column(String(120), unique=True)
    event_type: Mapped[str | None] = mapped_column(String(80))
    payload: Mapped[dict | None] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
