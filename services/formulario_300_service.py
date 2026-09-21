"""
El consolidado que ve el contador para clasificar operaciones a tarifa 0%.

La regla de presentación, confirmada por Andrés: "resumen primero, detalle bajo
demanda". El eje es el PROVEEDOR (el NIT predice el tratamiento mejor que el
texto de la descripción — un mismo proveedor de maquinaria factura acarreos
gravados aunque diga "transporte"), y dentro de cada proveedor se muestra el
concepto predominante por valor acumulado, con los secundarios de tratamiento
distinto siempre separados.

Lo que este archivo NUNCA hace: agrupar dos conceptos que puedan tener
tratamiento distinto bajo una sola cifra. Eso perdería información que el
Formulario 300 necesita, y es justamente lo que la especificación prohíbe.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.auth import Empresa, Usuario
from db.models.contabilidad import DocumentoDian
from services.catalogo_tributario_service import (
    Clasificacion, buscar_en_catalogo, clasificar, normalizar_concepto,
    registrar_cambio, nueva_version,
)
from db.models.tributario import CatalogoTributario, ClasificacionEmpresa


@dataclass
class ConceptoResumen:
    concepto: str
    concepto_norm: str
    nit_proveedor: str
    base_acumulada: float
    documentos: int
    clasificacion: Clasificacion
    # % del total del proveedor que representa este concepto — es lo que decide
    # cuál es el "predominante" y cuáles quedan de segundo plano en la pantalla.
    participacion: float = 0.0


@dataclass
class ProveedorResumen:
    nit: str
    razon_social: str
    base_total: float
    documentos: int
    predominante: ConceptoResumen
    secundarios: list[ConceptoResumen] = field(default_factory=list)

    @property
    def pendientes(self) -> int:
        """Cuántos conceptos de este proveedor todavía no tienen una
        clasificación validada — es la cifra que le dice al contador cuánto
        trabajo le queda con este proveedor."""
        todos = [self.predominante, *self.secundarios]
        return sum(1 for c in todos if c.clasificacion.requiere_revision)


def resumen_por_proveedor(
    db: Session,
    *,
    empresa_ids: list[int],
    desde: date,
    hasta: date,
    tarifa: float = 0.0,
    cuenta_id: int | None = None,
) -> list[ProveedorResumen]:
    """Proveedores con operaciones a la `tarifa` dada, con sus conceptos
    clasificados y ordenados por peso económico.

    Se usa la fecha de EMISIÓN de cada documento para resolver el tratamiento
    vigente en ese momento — no la de hoy. Un documento de marzo se clasifica
    con la norma de marzo, aunque hoy rija una distinta.
    """
    if not empresa_ids:
        return []

    docs = db.execute(
        select(DocumentoDian).where(
            DocumentoDian.empresa_id.in_(empresa_ids),
            DocumentoDian.fecha_emision >= desde,
            DocumentoDian.fecha_emision <= hasta,
        )
    ).scalars().all()

    # (nit, concepto_norm) → acumulador. El nit es el eje; el concepto separa
    # dentro de él sin fusionar nada.
    acumulado: dict[tuple[str, str], dict] = {}

    for doc in docs:
        if not doc.items_json:
            continue
        try:
            items = json.loads(doc.items_json)
        except ValueError:
            continue

        nit = (doc.nit_contraparte or "").strip()
        if not nit:
            continue
        fecha_doc = doc.fecha_emision or hasta

        for it in items:
            pct = it.get("porcentaje")
            try:
                pct = float(pct) if pct is not None else None
            except (TypeError, ValueError):
                pct = None
            if pct is None or round(pct, 2) != round(tarifa, 2):
                continue

            concepto = str(it.get("descripcion") or "").strip()
            if not concepto:
                continue
            norm = normalizar_concepto(concepto)
            if not norm:
                continue

            base = float(it.get("base") or 0)
            clave = (nit, norm)
            acc = acumulado.setdefault(clave, {
                "concepto": concepto, "concepto_norm": norm, "nit": nit,
                "razon_social": doc.razon_social or "", "base": 0.0, "documentos": 0,
                "fecha_referencia": fecha_doc,
            })
            acc["base"] += base
            acc["documentos"] += 1
            # Se clasifica con la fecha del documento más ANTIGUO del grupo: si
            # una norma cambió a mitad de periodo, es la fecha más conservadora
            # la que decide qué tratamiento mostrar como sugerencia por defecto.
            if fecha_doc < acc["fecha_referencia"]:
                acc["fecha_referencia"] = fecha_doc
            if not acc["razon_social"] and doc.razon_social:
                acc["razon_social"] = doc.razon_social

    if not acumulado:
        return []

    conceptos_por_nit: dict[str, list[ConceptoResumen]] = {}
    razon_social_por_nit: dict[str, str] = {}

    for (nit, _norm), acc in acumulado.items():
        clas = clasificar(
            db, empresa_id=empresa_ids[0] if len(empresa_ids) == 1 else _empresa_de(db, empresa_ids, nit),
            concepto=acc["concepto"], fecha=acc["fecha_referencia"],
            nit_tercero=nit, cuenta_id=cuenta_id,
        )
        cr = ConceptoResumen(
            concepto=acc["concepto"], concepto_norm=acc["concepto_norm"], nit_proveedor=nit,
            base_acumulada=round(acc["base"], 2), documentos=acc["documentos"], clasificacion=clas,
        )
        conceptos_por_nit.setdefault(nit, []).append(cr)
        razon_social_por_nit[nit] = acc["razon_social"]

    proveedores: list[ProveedorResumen] = []
    for nit, conceptos in conceptos_por_nit.items():
        base_total = sum(c.base_acumulada for c in conceptos)
        for c in conceptos:
            c.participacion = round((c.base_acumulada / base_total) * 100, 1) if base_total else 0.0
        conceptos.sort(key=lambda c: c.base_acumulada, reverse=True)

        proveedores.append(ProveedorResumen(
            nit=nit,
            razon_social=razon_social_por_nit.get(nit) or "—",
            base_total=round(base_total, 2),
            documentos=sum(c.documentos for c in conceptos),
            predominante=conceptos[0],
            secundarios=conceptos[1:],
        ))

    proveedores.sort(key=lambda p: p.base_total, reverse=True)
    return proveedores


def _empresa_de(db: Session, empresa_ids: list[int], nit: str) -> int:
    """Cuando se consolidan varias empresas a la vez, cada concepto se clasifica
    con la primera empresa de la lista que tenga ese proveedor — es una
    aproximación razonable para la vista consolidada; el detalle por empresa usa
    siempre su propio empresa_id."""
    fila = db.scalar(
        select(DocumentoDian.empresa_id)
        .where(DocumentoDian.empresa_id.in_(empresa_ids), DocumentoDian.nit_contraparte == nit)
        .limit(1)
    )
    return fila or empresa_ids[0]


# ── Validar una clasificación ────────────────────────────────────────────────

def validar_clasificacion(
    db: Session,
    *,
    empresa: Empresa,
    usuario: Usuario,
    concepto: str,
    tratamiento: str,
    nit_tercero: str | None = None,
    articulo_et: str | None = None,
    norma: str | None = None,
) -> ClasificacionEmpresa:
    """El contador confirma (o corrige) el tratamiento de un concepto para esta
    empresa.

    Si la validación NO está atada a un proveedor puntual (`nit_tercero=None`),
    también enriquece el catálogo de la firma: es una regla general del
    concepto, y las demás empresas de la misma cuenta la ven después como
    sugerencia. Si SÍ está atada a un proveedor, queda como una excepción propia
    de esa relación comercial y no se comparte — generalizarla podría
    equivocarse con otro proveedor que factura el mismo texto por algo distinto.
    """
    norm = normalizar_concepto(concepto)
    ahora = datetime.now(timezone.utc)
    hoy = ahora.date()

    sugerencia = buscar_en_catalogo(db, concepto=concepto, fecha=hoy, cuenta_id=empresa.cuenta_id)
    es_excepcion = sugerencia is not None and sugerencia.tratamiento != tratamiento

    fila = ClasificacionEmpresa(
        empresa_id=empresa.id, nit_tercero=nit_tercero,
        concepto_norm=norm, concepto=concepto, tratamiento=tratamiento,
        origen="manual", estado="validada",
        catalogo_id=sugerencia.id if sugerencia else None,
        es_excepcion=es_excepcion,
        articulo_et=articulo_et, norma=norma,
        validado_por=usuario.id, validado_at=ahora,
    )
    db.add(fila)
    db.flush()

    if nit_tercero is None and empresa.cuenta_id is not None:
        _propagar_al_catalogo_de_la_firma(
            db, cuenta_id=empresa.cuenta_id, empresa_nombre=empresa.nombre,
            concepto=concepto, norm=norm, tratamiento=tratamiento,
            usuario=usuario, articulo_et=articulo_et, norma_texto=norma, hoy=hoy,
        )

    db.commit()
    db.refresh(fila)
    return fila


def _propagar_al_catalogo_de_la_firma(
    db: Session, *, cuenta_id: int, empresa_nombre: str, concepto: str, norm: str,
    tratamiento: str, usuario: Usuario, articulo_et: str | None, norma_texto: str | None, hoy: date,
) -> None:
    vigente = db.scalar(
        select(CatalogoTributario).where(
            CatalogoTributario.concepto_norm == norm,
            CatalogoTributario.cuenta_id == cuenta_id,
            CatalogoTributario.vigencia_hasta.is_(None),
        )
    )
    if vigente is None:
        nueva = CatalogoTributario(
            cuenta_id=cuenta_id, concepto=concepto, concepto_norm=norm,
            tratamiento=tratamiento, articulo_et=articulo_et, fuente_normativa=norma_texto,
            estado="validada", validado_por=usuario.id, validado_at=datetime.now(timezone.utc),
        )
        db.add(nueva)
        db.flush()
        registrar_cambio(
            db, catalogo=nueva, usuario_id=usuario.id, accion="creada",
            detalle=f"Validado por {usuario.nombre} al clasificar {empresa_nombre}", norma=norma_texto,
        )
    elif vigente.tratamiento != tratamiento:
        nueva_version(
            db, anterior=vigente, tratamiento=tratamiento, rige_desde=hoy,
            usuario_id=usuario.id, articulo_et=articulo_et, norma=norma_texto,
            observaciones=f"Cambiado al validar {empresa_nombre}",
        )
    else:
        registrar_cambio(
            db, catalogo=vigente, usuario_id=usuario.id, accion="validada",
            detalle=f"Reconfirmado al clasificar {empresa_nombre}", norma=norma_texto,
        )
