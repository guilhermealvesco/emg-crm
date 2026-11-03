"""Testes das regras de negócio e do fluxo completo (sem rede: fontes externas simuladas)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TEST_DB = ROOT / "storage" / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["APIBRASIL_ENABLED"] = "true"
os.environ["APIBRASIL_TOKEN"] = "fake"
os.environ["AUTENTIQUE_TOKEN"] = "fake"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.enrichment import apibrasil, cadastral  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services import autentique, commissions  # noqa: E402

CNPJ_OK = "11222333000181"  # dígito verificador válido


@pytest.fixture(scope="module")
def client():
    if TEST_DB.exists():
        TEST_DB.unlink()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add_all([
        models.User(name="Guilherme", email="admin@emg", role=models.Role.ADMIN, password_hash=hash_password("senha123")),
        models.User(name="Eduarda", email="op@emg", role=models.Role.OPERACAO, password_hash=hash_password("senha123")),
        models.User(name="Bruno", email="bruno@emg", role=models.Role.CAPTADOR, password_hash=hash_password("senha123")),
        models.User(name="Silas", email="silas@emg", role=models.Role.CAPTADOR, password_hash=hash_password("senha123")),
    ])
    db.commit()
    db.close()
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def fake_external(monkeypatch):
    def fake_cnpj(cnpj):
        return {"fonte": "fake", "razao_social": "PADARIA DO JOAO LTDA", "nome_fantasia": "Padaria do João",
                "situacao": "ATIVA", "situacao_data": "2010-01-01", "data_abertura": "2012-03-10", "idade_anos": 14.6,
                "porte": "DEMAIS", "natureza_juridica": "206-2 Sociedade Empresária Limitada", "capital_social": 250000.0,
                "cnae_codigo": 1091101, "cnae_descricao": "Fabricação de produtos de panificação",
                "cnaes_secundarios": [], "municipio": "RECIFE", "uf": "PE", "telefone": "81 3333", "email": None,
                "simples": True, "mei": False,
                "qsa": [{"nome": "JOAO SILVA", "qualificacao": "Sócio-Administrador", "cpf_mascarado": "***123456**", "entrada": "2012-03-10"}],
                "raw": {"logradouro": "RUA A", "numero": "10", "bairro": "CENTRO", "cep": "50000000", "descricao_tipo_de_logradouro": "RUA"}}
    monkeypatch.setattr(cadastral, "consultar_cnpj", fake_cnpj)

    def fake_consulta(tipo, documento, homolog=None):
        if "protesto" in tipo:
            return {"ok": True, "tipo": tipo, "homolog": True, "data": {"response": {"mensagem": "Nao constam protestos", "protestos": []}}}
        return {"ok": True, "tipo": tipo, "homolog": True, "data": {"response": {"pendencias": [{"valor": 1200.0}], "quantidade": 1}}}
    monkeypatch.setattr(apibrasil, "consultar", fake_consulta)

    monkeypatch.setattr(autentique, "criar_documento",
                        lambda *a, **k: {"id": "DOC123", "sandbox": True, "link": "https://assina.ae/x", "raw": {}})
    monkeypatch.setattr(autentique, "baixar_arquivo", lambda url, destino: destino.write_bytes(b"%PDF-1.4 fake") or destino)


def login(client, email):
    client.cookies.clear()
    r = client.post("/login", data={"email": email, "password": "senha123"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"


# ---------------------------------------------------------------- regras puras
def test_comissao_tarifa():
    assert commissions.comissao_tarifa(6000) == 1000.0
    assert commissions.comissao_tarifa(5000) == 0.0
    assert commissions.comissao_tarifa(8500) == 3500.0


def test_comissao_exito():
    assert commissions.comissao_exito(300_000, "indicacao") == 9_000.0
    assert commissions.comissao_exito(800_000, "indicacao") == 15_000 + 3_000
    assert commissions.comissao_exito(300_000, "fechamento") == 15_000.0
    assert commissions.comissao_exito(800_000, "fechamento") == 25_000 + 6_000


def test_resumo_apibrasil():
    r = apibrasil.resumir({"ok": True, "data": {"response": {"mensagem": "Nao constam protestos", "protestos": []}}})
    assert r["consta"] is False
    r = apibrasil.resumir({"ok": True, "data": {"response": {"pendencias": [{"valor": 100}, {"valor": 50}], "quantidade": 2}}})
    assert r["consta"] is True and r["quantidade"] == 2
    r = apibrasil.resumir({"ok": False, "error": "x"})
    assert r["consta"] is None


# ---------------------------------------------------------------- fluxo completo
def test_fluxo_completo(client):
    login(client, "bruno@emg")
    r = client.post("/leads/novo", data={"cnpj": "11.222.333/0001-81", "contato_nome": "João", "contato_telefone": "81 9",
                                         "contato_email": "joao@padaria.com", "origem": "Indicação", "valor_pretendido": "300.000",
                                         "socio_nome": "Joao Silva", "socio_cpf": "529.982.247-25", "lgpd_consent": "on",
                                         "lgpd_consent_by": "João", "lgpd_consent_meio": "WhatsApp"}, follow_redirects=False)
    assert r.status_code == 303, r.text
    lead_url = r.headers["location"]
    lead_id = int(lead_url.rsplit("/", 1)[1])

    # enriquecimento rodou em background (TestClient executa as background tasks)
    db = SessionLocal()
    lead = db.get(models.Lead, lead_id)
    assert lead.enrichment_at is not None
    assert lead.razao_social == "PADARIA DO JOAO LTDA"
    assert lead.prescore in ("verde", "amarelo", "vermelho")
    assert lead.stage == models.Stage.TRIAGEM
    assert lead.enrichment["bureau"]["socios"][0]["cpf_mascarado"].startswith("***")
    assert len(lead.banks) == 5
    db.close()

    r = client.get(lead_url)
    assert r.status_code == 200 and "Padaria do João" in r.text and "Pré-score" in r.text

    # duplicidade: outro captador não consegue registrar o mesmo CNPJ
    login(client, "silas@emg")
    r = client.post("/leads/novo", data={"cnpj": CNPJ_OK}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/leads/novo"
    r = client.get(lead_url)
    assert r.status_code == 404  # não vê lead do outro

    # captador não pode fazer triagem
    login(client, "bruno@emg")
    r = client.post(f"/leads/{lead_id}/triagem", data={"decisao": "aprovado"}, follow_redirects=False)
    assert r.status_code == 403

    # contrato bloqueado antes do retorno dos bancos
    r = client.get(f"/contratos/novo/{lead_id}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == lead_url

    # operação aprova
    login(client, "op@emg")
    r = client.post(f"/leads/{lead_id}/triagem", data={"decisao": "aprovado", "obs": "sócio forte"}, follow_redirects=False)
    assert r.status_code == 303
    db = SessionLocal()
    lead = db.get(models.Lead, lead_id)
    assert lead.stage == models.Stage.BANCOS and lead.triagem_decisao == "aprovado"
    assert any(t.tipo == "posicao" and t.assigned_to_id == lead.captador_id for t in lead.tasks)
    db.close()

    # ainda não pode cobrar (sem retorno bom)
    r = client.post(f"/leads/{lead_id}/etapa", data={"nova": "cobranca"}, follow_redirects=False)
    db = SessionLocal(); lead = db.get(models.Lead, lead_id); assert lead.stage == models.Stage.BANCOS; db.close()

    # fila dos bancos: marca enviado e retorno bom na Caixa
    r = client.get("/bancos"); assert r.status_code == 200 and "Padaria" in r.text
    client.post(f"/bancos/{lead_id}/Caixa/rapido", data={"status": "enviado"})
    r = client.post(f"/bancos/{lead_id}/Caixa", data={"status": "retorno_bom", "valor_estimado": "250.000", "observacao": "gerente topou", "voltar": lead_url})
    db = SessionLocal(); lead = db.get(models.Lead, lead_id)
    assert lead.stage == models.Stage.RETORNO
    caixa = next(b for b in lead.banks if b.banco == "Caixa")
    assert caixa.status == "retorno_bom" and caixa.valor_estimado == 250000.0
    db.close()

    # agora o captador gera o contrato
    login(client, "bruno@emg")
    r = client.get(f"/contratos/novo/{lead_id}"); assert r.status_code == 200
    r = client.post(f"/contratos/novo/{lead_id}", data={"razao_social": "Padaria do João LTDA", "cnpj": "11.222.333/0001-81",
                                                        "endereco": "Rua A, 10", "cidade_uf": "Recife/PE", "email": "joao@padaria.com",
                                                        "representante": "João Silva", "representante_cpf": "529.982.247-25",
                                                        "tarifa_valor": "4.000", "forma_pagamento": "boleto bancário à vista"},
                    follow_redirects=False)
    assert r.headers["location"].startswith("/contratos/novo")  # abaixo do piso, recusa
    r = client.post(f"/contratos/novo/{lead_id}", data={"razao_social": "Padaria do João LTDA", "cnpj": "11.222.333/0001-81",
                                                        "endereco": "Rua A, 10", "cidade_uf": "Recife/PE", "email": "joao@padaria.com",
                                                        "representante": "João Silva", "representante_cpf": "529.982.247-25",
                                                        "nome_fantasia": "Padaria do João", "tarifa_valor": "6.000,00", "forma_pagamento": "outra", "forma_pagamento_outra": "PIX em 2 (duas) parcelas"},
                    follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/contratos/")
    cid = int(r.headers["location"].rsplit("/", 1)[1])
    db = SessionLocal(); c = db.get(models.Contract, cid)
    assert c.file_basename == "Padaria-do-Joao-LTDA-Contrato-Consultoria-Credito"
    assert Path(c.pdf_path).exists() and Path(c.pdf_path).stat().st_size > 10_000
    assert c.lead.stage == models.Stage.COBRANCA
    db.close()
    r = client.get(f"/contratos/{cid}/pdf"); assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"

    # envia ao Autentique (simulado) e recebe o webhook
    r = client.post(f"/contratos/{cid}/enviar", follow_redirects=False); assert r.status_code == 303
    db = SessionLocal(); c = db.get(models.Contract, cid); assert c.status == "enviado" and c.autentique_id == "DOC123"; db.close()
    payload = {"id": "wh1", "event": {"id": "evt-1", "type": "document.finished",
                                      "data": {"object": {"id": "DOC123", "files": {"signed": "https://x/assinado.pdf"}}}}}
    r = client.post("/webhooks/autentique", json=payload); assert r.status_code == 200
    r = client.post("/webhooks/autentique", json=payload); assert r.json()["status"] == "duplicate"
    db = SessionLocal(); c = db.get(models.Contract, cid)
    assert c.status == "assinado" and c.signed_pdf_path and c.signed_pdf_path.endswith("-ASSINADO.pdf")
    assert c.lead.stage == models.Stage.DOCS and c.lead.docs_pendentes
    db.close()

    # operação: tarifa recebida, liberação, recebimento e comissão
    login(client, "op@emg")
    client.post(f"/leads/{lead_id}/tarifa", data={"recebida_em": "2026-11-05"})
    r = client.post(f"/liberacoes/nova/{lead_id}", data={"banco": "Caixa", "valor": "800.000,00", "data_liberacao": "2026-11-20",
                                                         "exito_tipo": "fechamento"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == lead_url
    db = SessionLocal(); lead = db.get(models.Lead, lead_id)
    d = lead.disbursements[0]
    assert d.comissao_tarifa == 1000.0 and d.comissao_exito == 31_000.0 and d.comissao_total == 32_000.0
    assert lead.stage == models.Stage.LIBERACAO
    db.close()
    # comissão só depois de a EMG receber
    r = client.post(f"/liberacoes/{d.id}/comissao-paga", data={"em": "2026-11-21"}, follow_redirects=False)
    db = SessionLocal(); assert db.get(models.Disbursement, d.id).comissao_paga is False; db.close()
    client.post(f"/liberacoes/{d.id}/recebido", data={"em": "2026-11-21"})
    client.post(f"/liberacoes/{d.id}/comissao-paga", data={"em": "2026-11-22"})
    db = SessionLocal(); lead = db.get(models.Lead, lead_id)
    assert lead.disbursements[0].comissao_paga and lead.stage == models.Stage.COMISSAO_PAGA
    db.close()

    # ranking e páginas
    for url in ("/", "/ranking", "/alertas", "/tarefas", "/contratos", "/liberacoes", "/leads", "/admin/config"):
        login(client, "admin@emg")
        r = client.get(url)
        assert r.status_code == 200, url
    r = client.get("/ranking")
    assert "Bruno" in r.text and "32.000,00" in r.text


def test_posse_expirada_transfere(client):
    from datetime import date, timedelta
    db = SessionLocal()
    silas = db.scalar(__import__("sqlalchemy").select(models.User).where(models.User.email == "silas@emg"))
    lead = models.Lead(cnpj="19131243000197", captador_id=silas.id, owner_until=date.today() - timedelta(days=1),
                       stage=models.Stage.TRIAGEM)
    db.add(lead); db.commit(); lid = lead.id; db.close()
    login(client, "bruno@emg")
    r = client.post("/leads/novo", data={"cnpj": "19.131.243/0001-97", "contato_nome": "Maria"}, follow_redirects=False)
    assert r.headers["location"] == f"/leads/{lid}"
    db = SessionLocal(); lead = db.get(models.Lead, lid)
    assert lead.captador.email == "bruno@emg" and lead.owner_until > date.today()
    db.close()


def test_rotina_diaria_cria_posicao(client):
    from datetime import timedelta
    from app.services.alerts import rotina_diaria
    from app.utils import now_local
    db = SessionLocal()
    lead = db.scalar(__import__("sqlalchemy").select(models.Lead).where(models.Lead.cnpj == "19131243000197"))
    lead.stage = models.Stage.BANCOS
    lead.stage_changed_at = now_local() - timedelta(days=10)
    lead.last_posicao_at = None
    db.commit()
    r = rotina_diaria(db)
    assert r["tarefas_posicao_criadas"] == 1
    assert rotina_diaria(db)["tarefas_posicao_criadas"] == 0  # idempotente
    db.close()


def test_staff_cadastra_para_captador_e_reatribui(client):
    from sqlalchemy import select
    login(client, "op@emg")
    db = SessionLocal()
    bruno = db.scalar(select(models.User).where(models.User.email == "bruno@emg"))
    silas = db.scalar(select(models.User).where(models.User.email == "silas@emg"))
    db.close()
    r = client.post("/leads/novo", data={"cnpj": "60.975.099/0001-79", "captador_id": str(bruno.id)}, follow_redirects=False)
    assert r.status_code == 303
    lid = int(r.headers["location"].rsplit("/", 1)[1])
    db = SessionLocal(); lead = db.get(models.Lead, lid)
    assert lead.captador_id == bruno.id and lead.contato_nome is None
    db.close()
    client.post(f"/leads/{lid}/captador", data={"captador_id": str(silas.id)})
    db = SessionLocal(); assert db.get(models.Lead, lid).captador_id == silas.id; db.close()


def test_homologacao_nao_pontua():
    from app.enrichment import prescore
    cad = {"situacao": "ATIVA", "idade_anos": 3, "porte": "MICRO EMPRESA", "capital_social": 10000, "qsa": []}
    fake = {"consta": True, "quantidade": 5, "texto": "consta", "homolog": True}
    _, pts_h, _ = prescore.calcular(cad, {"pj": {"protestos": fake, "negativacao": fake, "certidao": fake}, "socios": []})
    _, pts_0, _ = prescore.calcular(cad, None)
    assert pts_h == pts_0
