"""EMG CRM: aplicação FastAPI."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from .config import BASE_DIR, settings
from .database import SessionLocal, init_db
from .routers import admin, auth, bancos, contratos, dashboard, leads, liberacoes, tarefas, webhooks
from .services import alerts
from .templating import templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("emg")


def _rotina_diaria():
    db = SessionLocal()
    try:
        r = alerts.rotina_diaria(db)
        log.info("rotina diária: %s", r)
    except Exception:  # noqa: BLE001
        log.exception("rotina diária falhou")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler = BackgroundScheduler(timezone=str(settings.TZ))
    scheduler.add_job(_rotina_diaria, "cron", hour=7, minute=15, id="rotina_diaria", replace_existing=True)
    scheduler.start()
    log.info("EMG CRM iniciado (%s)", settings.ENV)
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, session_cookie="emg_session",
                   max_age=60 * 60 * 24 * 30, same_site="lax")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

for r in (auth, dashboard, leads, bancos, tarefas, contratos, liberacoes, admin, webhooks):
    app.include_router(r.router)


@app.exception_handler(StarletteHTTPException)
async def _http_exc(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 303 and exc.headers and "Location" in exc.headers:
        return RedirectResponse(exc.headers["Location"], status_code=303)
    if exc.status_code in (403, 404):
        return templates.TemplateResponse(request, "erro.html",
                                          {"codigo": exc.status_code, "detalhe": exc.detail}, status_code=exc.status_code)
    return HTMLResponse(f"<h1>{exc.status_code}</h1><p>{exc.detail}</p>", status_code=exc.status_code)


@app.get("/health")
def health():
    return {"ok": True, "app": settings.APP_NAME, "env": settings.ENV}
