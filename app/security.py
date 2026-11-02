"""Autenticação por sessão (cookie assinado) e controle de perfil."""
from __future__ import annotations

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import Role, User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


class LoginRequired(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    uid = request.session.get("uid")
    if not uid:
        raise LoginRequired()
    user = db.get(User, uid)
    if not user or not user.active:
        request.session.clear()
        raise LoginRequired()
    return user


def require_staff(user: User = Depends(get_current_user)) -> User:
    """Guilherme (admin) ou Eduarda (operação)."""
    if not user.is_staff:
        raise HTTPException(status_code=403, detail="Acesso restrito à operação.")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador.")
    return user
