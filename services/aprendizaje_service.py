"""
AprendizajeService – capa de aprendizaje y trazabilidad de decisiones.

Reemplaza los mapeos aprendidos de db/memory.py (mapeos_puc).
Agrega historial de decisiones y reglas de clasificación versionadas.
"""

from __future__ import annotations

from collections import defaultdict
import re
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.aprendizaje import HistorialDecision, MapeoPUC, ReglaClasificacion


def _norm(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(texto).lower())
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", sin_acentos).strip()


# ── Mapeos PUC aprendidos ──────────────────────────────────────────────────────

def obtener_mapeo(
    db: Session, nit: str | None, descripcion: str
) -> str | None:
    """
    Busca la cuenta PUC más usada para un NIT + keyword de descripción.
    Retorna el código PUC o None si no hay mapeo conocido.
    """
    palabras = [p for p in _norm(descripcion).split() if len(p) > 3]

    for palabra in palabras:
        row = db.scalar(
            select(MapeoPUC)
            .where(
                MapeoPUC.nit == nit,
                MapeoPUC.keyword == palabra,
            )
            .order_by(MapeoPUC.usos.desc(), MapeoPUC.confianza.desc())
        )
        if row:
            return row.cuenta_puc

    return None


def registrar_mapeo(
    db: Session,
    *,
    nit: str | None,
    descripcion: str,
    cuenta_puc: str,
) -> None:
    """
    Registra o refuerza la asociación NIT+keyword → cuenta PUC.
    Incrementa `usos` y ajusta `confianza` si ya existe.
    """
    palabras = [p for p in _norm(descripcion).split() if len(p) > 3]
    ahora = datetime.now(timezone.utc)

    for palabra in palabras:
        row = db.scalar(
            select(MapeoPUC).where(
                MapeoPUC.nit == nit,
                MapeoPUC.keyword == palabra,
                MapeoPUC.cuenta_puc == cuenta_puc,
            )
        )
        if row:
            row.usos += 1
            # Confianza aumenta con los usos: converge a 1 asintóticamente
            row.confianza = min(1.0, float(row.confianza) + 0.05)
            row.ultima_vez = ahora
        else:
            db.add(MapeoPUC(
                nit=nit,
                keyword=palabra,
                cuenta_puc=cuenta_puc,
                descripcion=descripcion[:255],
                usos=1,
                confianza=0.5,
                ultima_vez=ahora,
            ))
    db.flush()


# ── Historial de decisiones ───────────────────────────────────────────────────

def registrar_decision(
    db: Session,
    *,
    numero_dian: str | None,
    nit_proveedor: str | None,
    descripcion_item: str | None,
    cuenta_sugerida: str | None,
    cuenta_aplicada: str | None,
    cod_impuesto: str | None,
    fue_corregida: bool = False,
    origen: str = "manual",
) -> HistorialDecision:
    decision = HistorialDecision(
        numero_dian=numero_dian,
        nit_proveedor=nit_proveedor,
        descripcion_item=descripcion_item,
        cuenta_sugerida=cuenta_sugerida,
        cuenta_aplicada=cuenta_aplicada,
        cod_impuesto=cod_impuesto,
        fue_corregida=fue_corregida,
        origen=origen,
    )
    db.add(decision)
    db.flush()
    return decision


def obtener_cod_impuesto(
    db: Session,
    nit: str | None,
    descripcion: str,
) -> str | None:
    """
    Sugiere un código de impuesto usando historial de decisiones confirmadas.

    Estrategia:
      1. Busca decisiones recientes con cod_impuesto para el mismo NIT.
      2. Puntúa los códigos por coincidencias de keywords de la descripción.
      3. Si no hay señal por NIT, intenta señal global (cualquier proveedor).
    """
    palabras = [p for p in _norm(descripcion).split() if len(p) > 3]
    if not palabras:
        return None

    def _mejor_codigo(mismo_nit: bool) -> str | None:
        stmt = (
            select(HistorialDecision)
            .where(HistorialDecision.cod_impuesto.is_not(None))
            .order_by(HistorialDecision.created_at.desc())
            .limit(500)
        )
        if mismo_nit and nit:
            stmt = stmt.where(HistorialDecision.nit_proveedor == nit)

        rows = db.scalars(stmt).all()
        if not rows:
            return None

        score: dict[str, float] = defaultdict(float)
        for row in rows:
            desc = _norm(row.descripcion_item or "")
            if not desc:
                continue
            hits = sum(1 for p in palabras if p in desc)
            if hits <= 0:
                continue
            base = float(hits)
            # Ligero bonus si no hubo corrección manual
            if not row.fue_corregida:
                base += 0.25
            score[str(row.cod_impuesto)] += base

        if not score:
            return None
        return max(score, key=score.get)

    return _mejor_codigo(mismo_nit=True) or _mejor_codigo(mismo_nit=False)


# ── Reglas de clasificación versionadas ──────────────────────────────────────

def aplicar_reglas(db: Session, descripcion: str) -> str | None:
    """
    Evalúa las reglas activas (ordenadas por prioridad desc.) contra la descripción.
    Retorna la cuenta PUC de la primera regla que coincida, o None.
    """
    reglas = db.scalars(
        select(ReglaClasificacion)
        .where(ReglaClasificacion.activa == True)
        .order_by(ReglaClasificacion.prioridad.desc())
    ).all()

    desc_norm = _norm(descripcion)

    for regla in reglas:
        if regla.tipo == "keyword":
            if _norm(regla.patron) in desc_norm:
                return regla.cuenta_puc
        elif regla.tipo == "regex":
            try:
                if re.search(regla.patron, descripcion, re.IGNORECASE):
                    return regla.cuenta_puc
            except re.error:
                pass

    return None


def crear_regla(
    db: Session,
    *,
    patron: str,
    cuenta_puc: str,
    tipo: str = "keyword",
    prioridad: int = 0,
    version: int = 1,
) -> ReglaClasificacion:
    regla = ReglaClasificacion(
        patron=patron,
        cuenta_puc=cuenta_puc,
        tipo=tipo,
        prioridad=prioridad,
        version=version,
    )
    db.add(regla)
    db.flush()
    return regla
