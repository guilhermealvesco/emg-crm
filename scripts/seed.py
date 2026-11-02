"""Cria as tabelas e os usuários iniciais.

Uso (na VPS, dentro do container ou com o venv ativo):
    python -m scripts.seed
Senhas iniciais vêm do .env (ADMIN_PASSWORD, etc.) ou são geradas e impressas uma única vez.
"""
from __future__ import annotations

import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import Role, User  # noqa: E402
from app.security import hash_password  # noqa: E402

USUARIOS = [
    ("Guilherme", os.environ.get("ADMIN_EMAIL", "guilherme@resolveco.com.br"), Role.ADMIN),
    ("Eduarda", os.environ.get("OPERACAO_EMAIL", "eduarda@emfinanceira.com"), Role.OPERACAO),
    ("Bruno", "bruno@captador.emg", Role.CAPTADOR),
    ("Silas", "silas@captador.emg", Role.CAPTADOR),
    ("Junior", "junior@captador.emg", Role.CAPTADOR),
    ("Italo", "italo@captador.emg", Role.CAPTADOR),
    ("Ely", "ely@captador.emg", Role.CAPTADOR),
]


def main() -> None:
    init_db()
    db = SessionLocal()
    criados = []
    try:
        for nome, email, role in USUARIOS:
            if db.scalar(select(User).where(User.email == email)):
                continue
            senha = os.environ.get(f"{nome.upper()}_PASSWORD") or secrets.token_urlsafe(9)
            db.add(User(name=nome, email=email, role=role, password_hash=hash_password(senha)))
            criados.append((nome, email, senha))
        db.commit()
    finally:
        db.close()
    if criados:
        print("Usuários criados (anote e troque a senha no primeiro acesso):")
        for nome, email, senha in criados:
            print(f"  {nome:<10} {email:<34} senha: {senha}")
    else:
        print("Nenhum usuário novo (todos já existiam).")


if __name__ == "__main__":
    main()
