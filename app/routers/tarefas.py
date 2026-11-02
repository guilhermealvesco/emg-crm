from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Role, Task, TaskType, User
from ..security import get_current_user
from ..services.leads import registrar_contato
from ..templating import flash, render
from ..utils import now_local, today_local

router = APIRouter(prefix="/tarefas")


@router.get("")
def listar(request: Request, todas: int = 0, feitas: int = 0, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    q = select(Task)
    if not (user.is_staff and todas):
        q = q.where(Task.assigned_to_id == user.id)
    q = q.where(Task.done.is_(bool(feitas)))
    tarefas = db.scalars(q.order_by(Task.due_date.asc().nulls_last(), Task.created_at.desc()).limit(200)).all()
    usuarios = db.scalars(select(User).where(User.active.is_(True)).order_by(User.name)).all() if user.is_staff else []
    return render(request, "tarefas/list.html", user=user, tarefas=tarefas, todas=todas, feitas=feitas,
                  hoje=today_local(), usuarios=usuarios)


@router.post("/{task_id}/concluir")
def concluir(request: Request, task_id: int, nota: str = Form(""), voltar: str = Form("/tarefas"),
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t or (t.assigned_to_id != user.id and not user.is_staff):
        raise HTTPException(404)
    t.done = True
    t.done_at = now_local()
    if t.lead:
        tipo = "posicao" if t.tipo == TaskType.POSICAO else ("contato" if t.tipo == TaskType.FOLLOWUP else "nota")
        registrar_contato(db, t.lead, user, f"Tarefa concluída: {t.titulo}." + (f" {nota.strip()}" if nota.strip() else ""), tipo)
    db.commit()
    flash(request, "Tarefa concluída.")
    return RedirectResponse(voltar, status_code=303)


@router.post("/nova")
def nova(request: Request, titulo: str = Form(...), due_date: str = Form(""), assigned_to_id: int | None = Form(None),
         tipo: str = Form(TaskType.OUTRO), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from datetime import date
    alvo = assigned_to_id if (user.is_staff and assigned_to_id) else user.id
    db.add(Task(assigned_to_id=alvo, created_by_id=user.id, tipo=tipo, titulo=titulo.strip(),
                due_date=date.fromisoformat(due_date) if due_date else None))
    db.commit()
    flash(request, "Tarefa criada.")
    return RedirectResponse("/tarefas", status_code=303)
