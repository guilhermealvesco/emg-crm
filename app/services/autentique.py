"""Cliente Autentique (GraphQL v2): criar documento com selfie, consultar e baixar o PDF assinado.

Docs: https://docs.autentique.com.br/api
- createDocument em multipart (graphql-multipart-request-spec): operations + map + file
- sandbox: true não consome créditos
- security_verifications: [{"type": "LIVE"}] = documento + selfie + prova de vida
- webhook: cadastrar no painel (Developer) apontando para {PUBLIC_URL}/webhooks/autentique; assinatura HMAC-SHA256
  do corpo bruto no header X-Autentique-Signature.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

import httpx

from ..config import settings

TIMEOUT = 60.0

CREATE_MUTATION = """
mutation CreateDocumentMutation($document: DocumentInput!, $signers: [SignerInput!]!, $file: Upload!) {
  createDocument(sandbox: %s, document: $document, signers: $signers, file: $file) {
    id name sandbox created_at
    signatures { public_id name email action { name } link { short_link } }
  }
}
"""

DOCUMENT_QUERY = """
query ($id: UUID!) {
  document(id: $id) {
    id name signed_count rejected_count created_at
    files { original signed certified }
    signatures { public_id name email signed { created_at } rejected { created_at } }
  }
}
"""


class AutentiqueError(Exception):
    pass


def _headers() -> dict:
    if not settings.AUTENTIQUE_TOKEN:
        raise AutentiqueError("AUTENTIQUE_TOKEN não configurado no .env")
    return {"Authorization": f"Bearer {settings.AUTENTIQUE_TOKEN}"}


def criar_documento(pdf_path: Path, nome: str, signatario_email: str, signatario_nome: str,
                    signatario_cpf: str | None = None, sandbox: bool | None = None) -> dict:
    """Cria o documento e envia para assinatura. Retorna {"id", "sandbox", "link", "raw"}."""
    sb = settings.AUTENTIQUE_SANDBOX if sandbox is None else sandbox
    signer: dict = {"email": signatario_email, "action": "SIGN", "name": signatario_nome}
    if settings.AUTENTIQUE_VERIFICATION:
        signer["security_verifications"] = [{"type": settings.AUTENTIQUE_VERIFICATION}]
    if signatario_cpf:
        signer["configs"] = {"cpf": signatario_cpf}
    signers = [signer]
    if settings.AUTENTIQUE_SIGNER_EMG_EMAIL:
        signers.append({"email": settings.AUTENTIQUE_SIGNER_EMG_EMAIL, "action": "SIGN"})
    operations = {
        "query": CREATE_MUTATION % ("true" if sb else "false"),
        "variables": {
            "document": {"name": nome, "refusable": True, "sortable": False,
                         "configs": {"notification_finished": True, "notification_signed": True}},
            "signers": signers,
            "file": None,
        },
    }
    data = {"operations": json.dumps(operations), "map": json.dumps({"file": ["variables.file"]})}
    with open(pdf_path, "rb") as fh:
        files = {"file": (pdf_path.name, fh, "application/pdf")}
        try:
            with httpx.Client(timeout=TIMEOUT) as client:
                r = client.post(settings.AUTENTIQUE_URL, headers=_headers(), data=data, files=files)
        except httpx.HTTPError as e:
            raise AutentiqueError(f"falha de rede ao contatar o Autentique: {e}") from e
    try:
        payload = r.json()
    except ValueError as e:
        raise AutentiqueError(f"resposta inválida do Autentique (HTTP {r.status_code}): {r.text[:300]}") from e
    if r.status_code >= 400 or payload.get("errors"):
        raise AutentiqueError(f"Autentique recusou o envio: {json.dumps(payload.get('errors') or payload)[:600]}")
    docd = payload["data"]["createDocument"]
    link = None
    for s in docd.get("signatures") or []:
        if s.get("email") == signatario_email and s.get("link"):
            link = s["link"].get("short_link")
    return {"id": docd["id"], "sandbox": bool(docd.get("sandbox")), "link": link, "raw": docd}


def consultar_documento(doc_id: str) -> dict:
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.post(settings.AUTENTIQUE_URL, headers={**_headers(), "Content-Type": "application/json"},
                            json={"query": DOCUMENT_QUERY, "variables": {"id": doc_id}})
    except httpx.HTTPError as e:
        raise AutentiqueError(f"falha de rede: {e}") from e
    payload = r.json()
    if payload.get("errors"):
        raise AutentiqueError(json.dumps(payload["errors"])[:600])
    return payload["data"]["document"]


def baixar_arquivo(url: str, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            r = client.get(url, headers=_headers())
            if r.status_code >= 400:
                r = client.get(url)  # alguns links são públicos e rejeitam o Bearer
            r.raise_for_status()
    except httpx.HTTPError as e:
        raise AutentiqueError(f"não foi possível baixar o PDF assinado: {e}") from e
    destino.write_bytes(r.content)
    return destino


def verificar_assinatura(raw_body: bytes, header_signature: str | None) -> bool:
    """HMAC-SHA256 do corpo bruto com o secret do webhook. Sem secret configurado, aceita (log avisa)."""
    if not settings.AUTENTIQUE_WEBHOOK_SECRET:
        return True
    if not header_signature:
        return False
    calc = hmac.new(settings.AUTENTIQUE_WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(calc, header_signature.strip())
