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
    PENDIENTE, Clasificacion, _vigente_en, normalizar_concepto, sugerir_tipo_item,
    sugerir_iva_descontable, sugerir_tratamiento_por_tarifa,
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


def test_una_clasificacion_sin_tipo_item_no_esta_confirmado():
    """El valor por defecto no puede leerse como una confirmación del
    contador: nadie tocó ese campo todavía."""
    c = Clasificacion(tratamiento="excluido", estado="validada", origen="manual")
    assert c.tipo_item is None
    assert c.tipo_item_confirmado is False


def test_una_clasificacion_sin_iva_descontable_no_esta_confirmado():
    c = Clasificacion(tratamiento="gravado_general", estado="validada", origen="manual")
    assert c.iva_descontable is None
    assert c.iva_descontable_confirmado is False


# ─── Sugerencia bien vs. servicio (Fase 1, versión simplificada) ─────────────
#
# Andrés fue explícito: nada de un algoritmo tributario complejo, solo
# palabras clave de la descripción, editable en un clic, y "pendiente" —
# nunca un valor inventado— cuando hay ambigüedad real.

@pytest.mark.parametrize("descripcion,esperado", [
    # Los tres ejemplos exactos que dio Andrés en su respuesta.
    ("Servicio de mantenimiento preventivo de aire acondicionado", "servicio"),
    ("Computador portátil Lenovo ThinkPad", "bien"),
    ("Honorarios profesionales de asesoría contable", "servicio"),
    ("Compra de computadores", "bien"),
    ("Servicio de mantenimiento de equipos", "servicio"),
])
def test_sugiere_bien_o_servicio_por_palabras_clave(descripcion, esperado):
    assert sugerir_tipo_item(descripcion) == esperado


@pytest.mark.parametrize("vacio", [None, "", "   "])
def test_sin_descripcion_no_hay_sugerencia(vacio):
    assert sugerir_tipo_item(vacio) is None


def test_servicio_gana_cuando_el_texto_menciona_tambien_un_bien():
    """"Servicio de mantenimiento de computadores" es un servicio, aunque
    mencione un bien físico como objeto de la actividad."""
    assert sugerir_tipo_item("Servicio de mantenimiento de computadores") == "servicio"


def test_texto_sin_ninguna_palabra_clave_queda_sin_sugerencia():
    assert sugerir_tipo_item("Referencia XYZ-123") is None


# ─── IVA descontable (Fase 2, versión simplificada) ──────────────────────────
#
# Andrés: nada de motor de reglas ni prorrateo todavía. Solo una sugerencia
# simple a partir del tratamiento ya clasificado.

@pytest.mark.parametrize("tratamiento", ["gravado_general", "gravado_5"])
def test_gravado_se_sugiere_descontable(tratamiento):
    assert sugerir_iva_descontable(tratamiento) == "descontable"


@pytest.mark.parametrize("tratamiento", ["exento", "excluido", "no_gravado"])
def test_sin_iva_se_sugiere_no_descontable(tratamiento):
    """Si la operación no tuvo IVA, no hay nada que descontar."""
    assert sugerir_iva_descontable(tratamiento) == "no_descontable"


def test_especial_no_se_sugiere_requiere_revision_caso_por_caso():
    assert sugerir_iva_descontable("especial") is None


def test_sin_tratamiento_todavia_no_hay_sugerencia_de_iva():
    """Sin saber el tratamiento de IVA no se puede opinar si es descontable."""
    assert sugerir_iva_descontable(None) is None


# ─── Tratamiento obvio por la tarifa (evita "pendientes" falsos en compras
# gravadas normales, ahora que la pantalla las muestra también) ──────────────

def test_tarifa_5_sugiere_gravado_5():
    assert sugerir_tratamiento_por_tarifa(5.0) == ("gravado_5", "tarifa")


@pytest.mark.parametrize("pct", [19.0, 8.0, 4.0])
def test_cualquier_otra_tarifa_no_cero_sugiere_gravado_general(pct):
    assert sugerir_tratamiento_por_tarifa(pct) == ("gravado_general", "tarifa")


def test_tarifa_cero_sigue_sin_sugerencia_automatica():
    """La ambigüedad real (exento/excluido/no gravado) es justo al 0% — ahí
    nunca se adivina, sigue haciendo falta el catálogo o el contador."""
    assert sugerir_tratamiento_por_tarifa(0.0) is None


def test_sin_tarifa_conocida_no_hay_sugerencia():
    assert sugerir_tratamiento_por_tarifa(None) is None
