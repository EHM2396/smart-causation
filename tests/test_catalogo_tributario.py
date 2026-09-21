"""
El conocimiento tributario del motor del Formulario 300.

Lo que se protege acá son las dos reglas que sostienen todo:

  · El catálogo PROPONE, la empresa DISPONE — una clasificación compartida nunca
    se aplica sola, o el error de un usuario se replica a toda la cartera.
  · NADA se sobrescribe — una operación se clasifica con lo que regía en la fecha
    del documento, así un cambio de norma no altera un periodo ya declarado.

Un error acá no rompe nada visiblemente: produce una declaración mal armada.
"""
from __future__ import annotations

from datetime import date

import pytest

from services.catalogo_tributario_service import (
    PENDIENTE, Clasificacion, _vigente_en, normalizar_concepto,
)

pytestmark = pytest.mark.tributario


# ─── Normalización de conceptos ──────────────────────────────────────────────
#
# Hace falta porque en los datos reales el mismo concepto llega escrito de
# varias formas y se clasificaría dos veces.

def test_el_mismo_concepto_con_espacios_de_mas_es_el_mismo():
    """Caso real de producción: estas dos llegaron como conceptos distintos."""
    a = normalizar_concepto("transporte  vibro ingersoll rand 8 ton")
    b = normalizar_concepto("transporte vibro ingersoll rand 8 ton")
    assert a == b


@pytest.mark.parametrize("escrito,esperado", [
    ("ENERGÍA DOMICILIARIO", "energia domiciliario"),
    ("  Aseo  ", "aseo"),
    ("Servicio de Acueducto.", "servicio de acueducto"),
    ("Transporte, carga", "transporte carga"),
    ("ALCANTARILLADO", "alcantarillado"),
])
def test_normaliza_tildes_signos_y_mayusculas(escrito, esperado):
    assert normalizar_concepto(escrito) == esperado


@pytest.mark.parametrize("vacio", [None, "", "   ", "..."])
def test_un_concepto_vacio_no_produce_clave(vacio):
    """Sin texto no hay nada que comparar: mejor vacío que una clave falsa que
    agrupe cosas sin relación."""
    assert normalizar_concepto(vacio) == ""


def test_no_intenta_entender_el_texto():
    """Normalizar es comparar, no interpretar. Dos conceptos con tratamiento
    distinto deben seguir siendo distintos después de normalizar."""
    pasajeros = normalizar_concepto("Transporte público de pasajeros")
    maquinaria = normalizar_concepto("Transporte de maquinaria")
    assert pasajeros != maquinaria


# ─── Vigencias ───────────────────────────────────────────────────────────────
#
# Es lo que impide que reclasificar hacia adelante altere un periodo declarado.

@pytest.mark.parametrize("desde,hasta,fecha,rige", [
    # Excluido hasta junio, gravado desde julio: una operación de marzo sigue
    # cayendo en la versión vieja aunque hoy rija la nueva.
    (date(2026, 1, 1), date(2026, 6, 30), date(2026, 3, 15), True),
    (date(2026, 1, 1), date(2026, 6, 30), date(2026, 8, 15), False),
    (date(2026, 7, 1), None,              date(2026, 8, 15), True),
    (date(2026, 7, 1), None,              date(2026, 3, 15), False),
    # Extremos: sin fechas rige siempre.
    (None, None, date(2020, 1, 1), True),
    (None, date(2026, 6, 30), date(2026, 3, 1), True),
    (date(2026, 1, 1), None, date(2025, 12, 31), False),
])
def test_que_version_rige_en_cada_fecha(desde, hasta, fecha, rige):
    assert _vigente_en(desde, hasta, fecha) is rige


def test_los_limites_de_la_vigencia_estan_incluidos():
    """El primer y el último día cuentan: una factura del 30 de junio todavía
    es del régimen que terminaba ese día."""
    assert _vigente_en(date(2026, 1, 1), date(2026, 6, 30), date(2026, 1, 1)) is True
    assert _vigente_en(date(2026, 1, 1), date(2026, 6, 30), date(2026, 6, 30)) is True


# ─── Qué significa cada estado ───────────────────────────────────────────────

def test_sin_respuesta_queda_pendiente_no_se_inventa():
    """Cuando nadie sabe, se dice. Un tratamiento inventado es peor que uno
    faltante: el faltante se ve, el inventado no."""
    assert PENDIENTE.tratamiento is None
    assert PENDIENTE.estado == "pendiente"
    assert PENDIENTE.requiere_revision is True


@pytest.mark.parametrize("estado,revisar", [
    ("validada", False),   # un contador ya la aprobó
    ("sugerida", True),    # la propuso el catálogo o la IA
    ("manual", True),      # la escribió alguien, pero sin validar
    ("pendiente", True),
])
def test_solo_lo_validado_deja_de_requerir_revision(estado, revisar):
    c = Clasificacion(tratamiento="excluido", estado=estado, origen="catalogo")
    assert c.requiere_revision is revisar


def test_una_clasificacion_carga_su_procedencia():
    """El tratamiento sin su origen no es auditable: el contador tiene que poder
    ver si una cifra sale de una decisión suya o de una sugerencia."""
    c = Clasificacion(
        tratamiento="excluido", estado="validada", origen="catalogo",
        articulo_et="424", norma="Art. 424 ET", catalogo_id=7,
    )
    assert c.articulo_et == "424"
    assert c.norma == "Art. 424 ET"
    assert c.catalogo_id == 7
