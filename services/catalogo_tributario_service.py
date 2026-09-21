"""
El conocimiento tributario del motor del Formulario 300: qué tratamiento de IVA
le corresponde a cada operación, y de dónde salió esa respuesta.

Dos reglas sostienen todo lo de acá:

**El catálogo propone, la empresa dispone.** Un tratamiento validado por el
contador de una empresa se reutiliza como SUGERENCIA en las demás, nunca se
aplica solo. Así el conocimiento se comparte sin que el error de un usuario se
propague a toda la cartera.

**Nada se sobrescribe.** Cuando cambia una norma se cierra la vigencia anterior
y se abre una nueva. Una operación se clasifica con lo que regía en la FECHA DEL
DOCUMENTO, no con lo que rige hoy — por eso un periodo ya declarado sigue dando
lo mismo aunque la norma haya cambiado después.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from db.models.tributario import (
    CatalogoTributario, CatalogoTributarioCambio, ClasificacionEmpresa,
)


# ── Normalización de conceptos ───────────────────────────────────────────────

# Ruido que aparece en las descripciones reales de las facturas y que no aporta
# nada a la clasificación: fechas de servicio, unidades, referencias de obra.
_ESPACIOS = re.compile(r"\s+")
_NO_UTIL = re.compile(r"[^\w\s]", re.UNICODE)


def normalizar_concepto(texto: str | None) -> str:
    """Forma comparable de una descripción de factura.

    Hace falta porque en los datos reales el mismo concepto llega escrito de
    varias maneras: "transporte  vibro ingersoll" y "transporte vibro ingersoll"
    (un espacio de más) se guardaban como dos conceptos distintos y obligaban a
    clasificar dos veces lo mismo.

    Quita tildes, signos y espacios de más, y pasa todo a minúsculas. NO intenta
    entender el texto: eso es trabajo de la clasificación, no de la comparación.
    """
    if not texto:
        return ""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    limpio = _NO_UTIL.sub(" ", sin_tildes.lower())
    return _ESPACIOS.sub(" ", limpio).strip()


# ── Vigencias ────────────────────────────────────────────────────────────────

def _vigente_en(desde: date | None, hasta: date | None, fecha: date) -> bool:
    """¿Esta versión regía en esa fecha? Los extremos abiertos valen: sin
    `desde` rige desde siempre, sin `hasta` sigue vigente."""
    if desde is not None and fecha < desde:
        return False
    if hasta is not None and fecha > hasta:
        return False
    return True


def _filtro_vigencia(modelo, fecha: date):
    """El mismo criterio, pero como condición SQL."""
    return (
        or_(modelo.vigencia_desde.is_(None), modelo.vigencia_desde <= fecha),
        or_(modelo.vigencia_hasta.is_(None), modelo.vigencia_hasta >= fecha),
    )


# ── El resultado de clasificar ───────────────────────────────────────────────

@dataclass(frozen=True)
class Clasificacion:
    """Qué tratamiento aplica y, sobre todo, POR QUÉ.

    El "por qué" no es adorno: el contador tiene que poder ver si una cifra sale
    de una decisión suya, de una sugerencia del catálogo o de que nadie la
    revisó todavía. Un tratamiento sin su procedencia no es auditable.
    """
    tratamiento: str | None      # None cuando no se pudo determinar
    estado: str                  # pendiente | sugerida | validada | manual
    origen: str | None           # catalogo | ia | manual | heredada
    articulo_et: str | None = None
    norma: str | None = None
    catalogo_id: int | None = None
    clasificacion_id: int | None = None
    es_excepcion: bool = False

    @property
    def requiere_revision(self) -> bool:
        """Todo lo que no validó un contador sigue necesitando su ojo."""
        return self.estado != "validada"


PENDIENTE = Clasificacion(tratamiento=None, estado="pendiente", origen=None)


# ── La cadena de resolución ──────────────────────────────────────────────────

def clasificar(
    db: Session,
    *,
    empresa_id: int,
    concepto: str,
    fecha: date,
    nit_tercero: str | None = None,
    cuenta_id: int | None = None,
) -> Clasificacion:
    """Tratamiento que aplica a un concepto, para una empresa, en una fecha.

    Recorre la jerarquía en orden, y se queda con la primera respuesta:

      1. Lo que ESTA empresa decidió para ese proveedor y concepto
      2. Lo que ESTA empresa decidió para el concepto, con cualquier proveedor
      3. Lo que dice el catálogo (propio de la firma primero, luego la semilla)
      4. Nada: queda pendiente

    La `fecha` es la del DOCUMENTO, no la de hoy. Es lo que hace que reclasificar
    hacia adelante no altere un periodo ya declarado.
    """
    norm = normalizar_concepto(concepto)
    if not norm:
        return PENDIENTE

    # 1 y 2 — la decisión de la empresa manda sobre el catálogo compartido.
    # Se prueba primero con el proveedor porque es la más específica: el mismo
    # texto puede significar cosas distintas según quién factura.
    for nit in ([nit_tercero, None] if nit_tercero else [None]):
        fila = db.scalar(
            select(ClasificacionEmpresa)
            .where(
                ClasificacionEmpresa.empresa_id == empresa_id,
                ClasificacionEmpresa.concepto_norm == norm,
                (ClasificacionEmpresa.nit_tercero == nit) if nit
                else ClasificacionEmpresa.nit_tercero.is_(None),
                *_filtro_vigencia(ClasificacionEmpresa, fecha),
            )
            .order_by(ClasificacionEmpresa.validado_at.desc().nulls_last(),
                      ClasificacionEmpresa.id.desc())
            .limit(1)
        )
        if fila is not None:
            return Clasificacion(
                tratamiento=fila.tratamiento,
                estado=fila.estado,
                origen=fila.origen,
                articulo_et=fila.articulo_et,
                norma=fila.norma,
                catalogo_id=fila.catalogo_id,
                clasificacion_id=fila.id,
                es_excepcion=fila.es_excepcion,
            )

    # 3 — el catálogo. Nunca se devuelve como "validada": aunque la entrada del
    # maestro lo esté, para ESTA empresa sigue siendo una sugerencia hasta que su
    # contador la acepte.
    entrada = buscar_en_catalogo(db, concepto=concepto, fecha=fecha, cuenta_id=cuenta_id)
    if entrada is not None:
        return Clasificacion(
            tratamiento=entrada.tratamiento,
            estado="sugerida",
            origen="catalogo",
            articulo_et=entrada.articulo_et,
            norma=entrada.fuente_normativa,
            catalogo_id=entrada.id,
        )

    # 4 — nadie sabe. Se dice, no se inventa.
    return PENDIENTE


def buscar_en_catalogo(
    db: Session, *, concepto: str, fecha: date, cuenta_id: int | None = None,
) -> CatalogoTributario | None:
    """Entrada del catálogo que rige para ese concepto en esa fecha.

    Lo propio de la firma gana sobre la semilla del sistema: si una firma
    corrigió un concepto para su realidad, esa corrección vale más que el
    valor genérico con el que vino cargado.
    """
    norm = normalizar_concepto(concepto)
    if not norm:
        return None

    alcances = [cuenta_id, None] if cuenta_id is not None else [None]
    for alcance in alcances:
        fila = db.scalar(
            select(CatalogoTributario)
            .where(
                CatalogoTributario.concepto_norm == norm,
                (CatalogoTributario.cuenta_id == alcance) if alcance is not None
                else CatalogoTributario.cuenta_id.is_(None),
                *_filtro_vigencia(CatalogoTributario, fecha),
            )
            # Entre varias vigentes, la validada pesa más que la sugerida.
            .order_by(
                (CatalogoTributario.estado == "validada").desc(),
                CatalogoTributario.id.desc(),
            )
            .limit(1)
        )
        if fila is not None:
            return fila
    return None


# ── Escribir en el catálogo ──────────────────────────────────────────────────

def registrar_cambio(
    db: Session, *, catalogo: CatalogoTributario, usuario_id: int | None,
    accion: str, detalle: str | None = None, norma: str | None = None,
) -> CatalogoTributarioCambio:
    """Deja constancia de un movimiento del catálogo.

    Una clasificación tributaria nunca cambia en silencio: si mañana alguien
    pregunta por qué un concepto pasó de excluido a gravado, la respuesta tiene
    que estar acá, con quién y con qué norma.
    """
    cambio = CatalogoTributarioCambio(
        catalogo_id=catalogo.id, usuario_id=usuario_id,
        accion=accion, detalle=detalle, norma=norma,
    )
    db.add(cambio)
    return cambio


def nueva_version(
    db: Session,
    *,
    anterior: CatalogoTributario,
    tratamiento: str,
    rige_desde: date,
    usuario_id: int | None,
    articulo_et: str | None = None,
    norma: str | None = None,
    observaciones: str | None = None,
) -> CatalogoTributario:
    """Cambia el tratamiento de un concepto a partir de una fecha, sin tocar el
    pasado.

    Cierra la vigencia de la versión anterior el día antes de que empiece la
    nueva, y crea la nueva apuntando a ella. Las operaciones ya clasificadas
    conservan lo que regía cuando ocurrieron: eso es lo que evita que un cambio
    de norma altere un periodo ya declarado.
    """
    from datetime import timedelta

    anterior.vigencia_hasta = rige_desde - timedelta(days=1)
    anterior.updated_at = datetime.now(timezone.utc)

    nueva = CatalogoTributario(
        cuenta_id=anterior.cuenta_id,
        concepto=anterior.concepto,
        concepto_norm=anterior.concepto_norm,
        categoria=anterior.categoria,
        tratamiento=tratamiento,
        articulo_et=articulo_et or anterior.articulo_et,
        fuente_normativa=norma or anterior.fuente_normativa,
        observaciones=observaciones,
        vigencia_desde=rige_desde,
        vigencia_hasta=None,
        estado="validada" if usuario_id else "sugerida",
        validado_por=usuario_id,
        validado_at=datetime.now(timezone.utc) if usuario_id else None,
        reemplaza_a=anterior.id,
    )
    db.add(nueva)
    db.flush()

    registrar_cambio(
        db, catalogo=anterior, usuario_id=usuario_id, accion="reemplazada",
        detalle=f"Reemplazada por la versión {nueva.id}: {anterior.tratamiento} → {tratamiento}",
        norma=norma,
    )
    registrar_cambio(
        db, catalogo=nueva, usuario_id=usuario_id, accion="creada",
        detalle=f"Nueva versión de '{anterior.concepto}' vigente desde {rige_desde.isoformat()}",
        norma=norma,
    )
    return nueva
