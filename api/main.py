"""
Fábrica de la aplicación FastAPI.

Arranque:
    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# En producción (ENV=production) solo se muestran WARNING y superiores.
_log_level = logging.WARNING if os.getenv("ENV") == "production" else logging.INFO
logging.basicConfig(level=_log_level)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

# Error reporting — activo solo si GLITCHTIP_DSN está configurado.
_dsn = os.getenv("GLITCHTIP_DSN", "")
if _dsn:
    sentry_sdk.init(
        dsn=_dsn,
        environment=os.getenv("ENV", "development"),
        traces_sample_rate=0.1,
    )

from api.routers import (
    aprendizaje_router,
    auth_router,
    causacion_router,
    consecutivos_router,
    cuentas_router,
    impuestos_router,
    tipos_router,
    terceros_router,
)
from db.models import Base
from db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _apply_migrations()
    yield


def _apply_migrations() -> None:
    """Migraciones incrementales idempotentes (ALTER TABLE IF NOT EXISTS)."""
    from sqlalchemy import text
    migrations = [
        # empresa_id en consecutivos (multi-empresa)
        "ALTER TABLE consecutivos ADD COLUMN IF NOT EXISTS empresa_id INTEGER REFERENCES empresas(id);",
        # empresa_id en facturas_causadas (multi-empresa)
        "ALTER TABLE facturas_causadas ADD COLUMN IF NOT EXISTS empresa_id INTEGER REFERENCES empresas(id);",
    ]
    with engine.begin() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
            except Exception:
                pass


app = FastAPI(
    title="Siigo Contable API",
    description=(
        "Backend para automatización de causación contable. "
        "Procesa facturas electrónicas DIAN y genera archivos de importación SIIGO."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(cuentas_router)
app.include_router(impuestos_router)
app.include_router(tipos_router)
app.include_router(causacion_router)
app.include_router(aprendizaje_router)
app.include_router(consecutivos_router)
app.include_router(terceros_router)


@app.get("/", tags=["Health"])
def health():
    return {"status": "ok", "service": "siigo-contable-api"}
