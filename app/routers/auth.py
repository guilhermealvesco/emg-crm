from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user, hash_password, verify_password
from ..templating import flash, render

router = APIRouter()


@router.get("/login")
def login_form(request: Request):
    if request.session.get("uid"):
        return RedirectResponse("/", status_code=303)
    return render(request, "login.html")


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if not user or not user.active or not verify_password(password, user.password_hash):
        flash(request, "E-mail ou senha inválidos.", "erro")
        return RedirectResponse("/login", status_code=303)
    request.session["uid"] = user.id
    return RedirectResponse("/", status_code=303)


@router.get("/logout")
@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/senha")
def senha_form(request: Request, user: User = Depends(get_current_user)):
    return render(request, "senha.html", user=user)


@router.post("/senha")
def senha(request: Request, atual: str = Form(...), nova: str = Form(...), confirma: str = Form(...),
          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(atual, user.password_hash):
        flash(request, "Senha atual incorreta.", "erro")
    elif len(nova) < 8:
        flash(request, "A nova senha precisa ter pelo menos 8 caracteres.", "erro")
    elif nova != confirma:
        flash(request, "A confirmação não confere.", "erro")
    else:
        user.password_hash = hash_password(nova)
        db.commit()
        flash(request, "Senha alterada.")
        return RedirectResponse("/", status_code=303)
    return RedirectResponse("/senha", status_code=303)
