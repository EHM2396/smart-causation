"""
Fábrica de la aplicación FastAPI.

Arranque:
    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import (
    aprendizaje_router,
    causacion_router,
    consecutivos_router,
    cuentas_router,
    impuestos_router,
    tipos_router,
)
from db.models import Base
from db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crea las tablas si no existen (útil en desarrollo).
    # En producción usar Alembic: `alembic upgrade head`
    Base.metadata.create_all(bind=engine)
    yield


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
app.include_router(cuentas_router)
app.include_router(impuestos_router)
app.include_router(tipos_router)
app.include_router(causacion_router)
app.include_router(aprendizaje_router)
app.include_router(consecutivos_router)


@app.get("/", tags=["Health"])
def health():
    return {"status": "ok", "service": "siigo-contable-api"}
