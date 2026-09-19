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
) -> tuple[str, bool] | None:
    """Busca la cuenta aprendida para un ítem.

    Devuelve ``(cuenta_puc, es_otro_proveedor)`` o ``None``:
      1. Primero busca el aprendizaje PROPIO del tercero (nit + keyword).
      2. Si no hay, cae al aprendizaje del MISMO ítem en OTRO proveedor
         (solo keyword, dentro de la misma empresa/usuario) → ``es_otro=True``.
    Siempre aislado por (empresa, usuario); nunca cruza entre empresas.
    """
    palabras = [p for p in _norm(descripcion).split() if len(p) > 3]
    if not palabras:
        return None

    def _buscar(por_nit: bool) -> str | None:
        stmt = (
            select(MapeoPUC)
            .where(MapeoPUC.keyword.in_(palabras))
            .order_by(MapeoPUC.usos.desc(), MapeoPUC.confianza.desc())
        )
        if por_nit:
            stmt = stmt.where(MapeoPUC.nit == nit)
        if empresa_id is not None:
            stmt = stmt.where(MapeoPUC.empresa_id == empresa_id)
        if usuario_id is not None:
            stmt = stmt.where(MapeoPUC.usuario_id == usuario_id)
        # Cuenta dominante por keyword (rows ya ordenados por usos/confianza).
        por_kw: dict[str, str] = {}
        for row in db.scalars(stmt).all():
            por_kw.setdefault(row.keyword, row.cuenta_puc)
        # Respetar el orden de las palabras del ítem.
        for palabra in palabras:
            if palabra in por_kw:
                return por_kw[palabra]
        return None

    if nit:
        propio = _buscar(por_nit=True)
        if propio:
            return (propio, False)
    otro = _buscar(por_nit=False)
    if otro:
        return (otro, True)
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


def cargar_reglas(db: Session) -> list:
    """Carga todas las reglas activas una sola vez para procesamiento en lote."""
    return db.scalars(
        select(ReglaClasificacion)
        .where(ReglaClasificacion.activa == True)
        .order_by(ReglaClasificacion.prioridad.desc())
    ).all()


def aplicar_reglas_cargadas(reglas: list, descripcion: str) -> str | None:
    """Aplica reglas ya cargadas a una descripción (sin query DB)."""
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


def obtener_mapeos_batch(
    db: Session,
    items: list[dict],
    empresa_id: int | None = None,
    usuario_id: int | None = None,
) -> dict[str, tuple[str, bool]]:
    """
    Lookup de aprendizaje para múltiples ítems en una sola query.
    Retorna ``{key: (cuenta_puc, es_otro_proveedor)}`` para los ítems con mapeo:
      - Primero el aprendizaje PROPIO del tercero (nit + keyword) → es_otro=False.
      - Si no hay, cae al MISMO ítem aprendido en OTRO proveedor (solo keyword,
        dentro de la misma empresa/usuario) → es_otro=True. Así, si dos proveedores
        distintos traen el mismo ítem, se reutiliza la cuenta ya aprendida.
    Siempre aislado por (empresa, usuario).
    """
    if not items:
        return {}

    item_keywords: dict[str, list[str]] = {}
    all_keywords: set[str] = set()

    for item in items:
        palabras = [p for p in _norm(item["descripcion"]).split() if len(p) > 3]
        item_keywords[item["key"]] = palabras
        all_keywords.update(palabras)

    if not all_keywords:
        return {}

    stmt = (
        select(MapeoPUC)
        .where(MapeoPUC.keyword.in_(all_keywords))
        .order_by(MapeoPUC.usos.desc(), MapeoPUC.confianza.desc())
    )
    if empresa_id is not None:
        stmt = stmt.where(MapeoPUC.empresa_id == empresa_id)
    if usuario_id is not None:
        stmt = stmt.where(MapeoPUC.usuario_id == usuario_id)

    rows = db.scalars(stmt).all()

    # (nit, keyword) -> cuenta (aprendizaje propio) · keyword -> cuenta dominante
    # (cualquier proveedor). Primer resultado gana (rows ya ordenados por usos DESC).
    lookup_nit: dict[tuple, str] = {}
    lookup_kw: dict[str, str] = {}
    for row in rows:
        lookup_nit.setdefault((row.nit, row.keyword), row.cuenta_puc)
        lookup_kw.setdefault(row.keyword, row.cuenta_puc)

    resultados: dict[str, tuple[str, bool]] = {}
    for item in items:
        nit = item.get("nit")
        keywords = item_keywords.get(item["key"], [])
        # Paso 1: aprendizaje propio del tercero.
        cuenta_propia: str | None = None
        if nit:
            for keyword in keywords:
                c = lookup_nit.get((nit, keyword))
                if c:
                    cuenta_propia = c
                    break
        if cuenta_propia:
            resultados[item["key"]] = (cuenta_propia, False)
            continue
        # Paso 2 (fallback): mismo ítem aprendido en otro proveedor.
        for keyword in keywords:
            c = lookup_kw.get(keyword)
            if c:
                resultados[item["key"]] = (c, True)
                break

    return resultados


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
