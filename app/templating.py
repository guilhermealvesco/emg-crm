"""Jinja2 + filtros e helpers compartilhados (flash messages, formatação)."""
from __future__ import annotations

from fastapi import Request
from fastapi.templating import Jinja2Templates

from .config import BASE_DIR, settings
from .models import BankStatus, ContractStatus, ExitoTipo, Prescore, Role, Stage, TaskType
from .utils import brl, days_since, fmt_cnpj, fmt_cpf, fmt_date, fmt_dt, mask_cpf

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
env = templates.env
env.filters.update({
    "brl": brl, "cnpj": fmt_cnpj, "cpf": fmt_cpf, "cpf_mask": mask_cpf, "dt": fmt_dt,
    "date": fmt_date, "days": days_since,
    "pct": lambda v: f"{(v or 0):.0f}%",
    "num": lambda v: f"{(v or 0):,.0f}".replace(",", "."),
})
env.globals.update({
    "settings": settings, "Stage": Stage, "BankStatus": BankStatus, "Prescore": Prescore, "TaskType": TaskType,
    "ContractStatus": ContractStatus, "ExitoTipo": ExitoTipo, "Role": Role,
})


def flash(request: Request, message: str, kind: str = "ok") -> None:
    request.session.setdefault("_flash", [])
    request.session["_flash"] = request.session["_flash"] + [{"m": message, "k": kind}]


def pop_flash(request: Request) -> list[dict]:
    msgs = request.session.get("_flash") or []
    if msgs:
        request.session["_flash"] = []
    return msgs


def render(request: Request, name: str, user=None, **ctx):
    ctx.update({"user": user, "flashes": pop_flash(request), "path": request.url.path})
    return templates.TemplateResponse(request, name, ctx)
