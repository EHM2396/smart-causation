"""
Configuración del engine PostgreSQL y fábrica de sesiones.

Variables de entorno esperadas (o archivo .env):
  DATABASE_URL  →  postgresql+psycopg2://user:password@host:5432/dbname

Uso:
    from db.session import get_db

    # En FastAPI (dependencia)
    def endpoint(db: Session = Depends(get_db)):
        ...

    # En scripts / servicios directos
    with SessionLocal() as session:
        ...
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

load_dotenv()

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/siigo_contable",
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,       # detecta conexiones caídas
    pool_size=5,
    max_overflow=10,
    echo=False,               # cambiar a True para debug SQL
)

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,   # evita lazy-load tras commit
)


def get_db():
    """
    Generador de sesión para FastAPI Depends().
    Cierra la sesión automáticamente al terminar el request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
