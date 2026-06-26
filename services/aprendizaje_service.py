"""
AprendizajeService – capa de aprendizaje y trazabilidad de decisiones.
El aprendizaje está aislado por (usuario_id + empresa_id):
dos usuarios que operen la misma empresa tienen aprendizajes independientes.
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
    db: Session,
    nit: str | None,
    descripcion: str,
    empresa_id: int | None = None,
    usuario_id: int | None = None,
) -> str | None:
    palabras = [p for p in _norm(descripcion).split() if len(p) > 3]

    for palabra in palabras:
        stmt = (
            select(MapeoPUC)
            .where(MapeoPUC.nit == nit, MapeoPUC.keyword == palabra)
            .order_by(MapeoPUC.usos.desc(), MapeoPUC.confianza.desc())
        )
        if empresa_id is not None:
            stmt = stmt.where(MapeoPUC.empresa_id == empresa_id)
        if usuario_id is not None:
            stmt = stmt.where(MapeoPUC.usuario_id == usuario_id)
        row = db.scalar(stmt)
        if row:
            return row.cuenta_puc

    return None


def registrar_mapeo(
    db: Session,
    *,
    nit: str | None,
    descripcion: str,
    cuenta_puc: str,
    empresa_id: int | None = None,
    usuario_id: int | None = None,
) -> None:
    palabras = [p for p in _norm(descripcion).split() if len(p) > 3]
    ahora = datetime.now(timezone.utc)

    for palabra in palabras:
        stmt = select(MapeoPUC).where(
            MapeoPUC.nit == nit,
            MapeoPUC.keyword == palabra,
            MapeoPUC.cuenta_puc == cuenta_puc,
        )
        if empresa_id is not None:
            stmt = stmt.where(MapeoPUC.empresa_id == empresa_id)
        if usuario_id is not None:
            stmt = stmt.where(MapeoPUC.usuario_id == usuario_id)

        row = db.scalar(stmt)
        if row:
            row.usos += 1
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
                empresa_id=empresa_id,
                usuario_id=usuario_id,
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
    empresa_id: int | None = None,
    usuario_id: int | None = None,
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
        empresa_id=empresa_id,
        usuario_id=usuario_id,
    )
    db.add(decision)
    db.flush()
    return decision


def obtener_cod_impuesto(
    db: Session,
    nit: str | None,
    descripcion: str,
    empresa_id: int | None = None,
    usuario_id: int | None = None,
) -> str | None:
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
        if empresa_id is not None:
            stmt = stmt.where(HistorialDecision.empresa_id == empresa_id)
        if usuario_id is not None:
            stmt = stmt.where(HistorialDecision.usuario_id == usuario_id)

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
            if not row.fue_corregida:
                base += 0.25
            score[str(row.cod_impuesto)] += base

        if not score:
            return None
        return max(score, key=score.get)

    return _mejor_codigo(mismo_nit=True) or _mejor_codigo(mismo_nit=False)


# ── Reglas de clasificación (globales, definidas por el admin de plataforma) ───

def aplicar_reglas(db: Session, descripcion: str) -> str | None:
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
