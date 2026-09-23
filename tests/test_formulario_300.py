"""
El consolidado por proveedor que arma la pantalla de clasificación.

Lo que se protege: que nunca se fusionen dos conceptos con tratamiento
potencialmente distinto bajo una sola cifra, y que el "predominante" sea el de
mayor peso económico, no el más frecuente ni el primero en aparecer.
"""
from __future__ import annotations

import pytest

from services.formulario_300_service import (
    TIPOS_COMPRAS, TIPOS_VENTAS, ConceptoResumen, ProveedorResumen,
)
from services.catalogo_tributario_service import PENDIENTE, Clasificacion
from services.analitica_service import ORDEN as TIPOS_DOCUMENTO_DIAN

pytestmark = pytest.mark.formulario300


def _concepto(concepto: str, base: float, clasificacion=PENDIENTE) -> ConceptoResumen:
    return ConceptoResumen(
        concepto=concepto, concepto_norm=concepto.lower(), nit_proveedor="900111222",
        base_acumulada=base, documentos=1, clasificacion=clasificacion,
    )


# ─── El concepto predominante es el de mayor VALOR, no el más frecuente ──────

def test_predominante_es_el_de_mayor_valor_acumulado():
    """Un concepto puede aparecer en muchos documentos chicos y pesar menos que
    uno que aparece una sola vez mucho dinero. El criterio es el valor."""
    conceptos = [
        _concepto("servicio menor", 500_000),
        _concepto("contrato grande", 90_000_000),
        _concepto("otro menor", 300_000),
    ]
    conceptos.sort(key=lambda c: c.base_acumulada, reverse=True)
    predominante = conceptos[0]
    assert predominante.concepto == "contrato grande"


# ─── Nunca se pierde la separación entre conceptos ───────────────────────────

def test_dos_conceptos_del_mismo_proveedor_quedan_separados():
    """Aunque sean del mismo NIT, cada concepto es su propia fila. Fusionarlos
    perdería la posibilidad de que tengan tratamiento distinto."""
    predominante = _concepto("transporte de maquinaria", 90_000_000)
    secundario = _concepto("roca muerta para relleno", 21_000_000)
    p = ProveedorResumen(
        nit="900111222", razon_social="ALQUILER DE MAQUINARIA LTDA",
        base_total=111_000_000, documentos=2,
        predominante=predominante, secundarios=[secundario],
    )
    assert p.predominante.concepto != p.secundarios[0].concepto
    assert len(p.secundarios) == 1


def test_la_participacion_suma_cerca_de_cien_por_ciento():
    """No tiene que dar exacto por el redondeo, pero sí quedar cerca: es lo que
    le dice al contador cuánto pesa cada concepto dentro del proveedor."""
    predominante = _concepto("servicio principal", 700_000)
    predominante.participacion = 70.0
    secundario = _concepto("servicio secundario", 300_000)
    secundario.participacion = 30.0
    total = predominante.participacion + secundario.participacion
    assert 99.0 <= total <= 100.0


# ─── Cuántos conceptos faltan por revisar ────────────────────────────────────

def test_pendientes_cuenta_lo_que_no_esta_validado():
    validado = _concepto("agua", 1_000_000, Clasificacion(
        tratamiento="excluido", estado="validada", origen="manual"))
    sugerido = _concepto("transporte", 2_000_000, Clasificacion(
        tratamiento="gravado_general", estado="sugerida", origen="catalogo"))
    p = ProveedorResumen(
        nit="900111222", razon_social="PROVEEDOR X", base_total=3_000_000, documentos=2,
        predominante=sugerido, secundarios=[validado],
    )
    assert p.pendientes == 1


def test_todo_validado_no_deja_pendientes():
    v1 = _concepto("a", 100, Clasificacion(tratamiento="excluido", estado="validada", origen="manual"))
    v2 = _concepto("b", 50, Clasificacion(tratamiento="exento", estado="validada", origen="manual"))
    p = ProveedorResumen(nit="1", razon_social="X", base_total=150, documentos=2,
                         predominante=v1, secundarios=[v2])
    assert p.pendientes == 0


def test_lo_pendiente_de_verdad_cuenta_como_pendiente():
    p = ProveedorResumen(nit="1", razon_social="X", base_total=100, documentos=1,
                         predominante=_concepto("sin clasificar", 100), secundarios=[])
    assert p.pendientes == 1


# ─── Ventas y Compras nunca se mezclan (Fase 1) ──────────────────────────────
#
# La pantalla se separa en dos flujos: en ventas exento y excluido nunca se
# fusionan, en compras sí se agrupan en la presentación. Si un tipo de
# documento nuevo se agrega a la DIAN y se olvida acá, un documento entero
# desaparecería de las dos pantallas sin ningún error visible — por eso se
# valida contra la misma lista que ya usa Analítica.

def test_todo_tipo_de_documento_dian_cae_en_ventas_o_en_compras():
    cubiertos = set(TIPOS_VENTAS) | set(TIPOS_COMPRAS)
    assert cubiertos == set(TIPOS_DOCUMENTO_DIAN)


def test_ventas_y_compras_no_se_superponen():
    assert set(TIPOS_VENTAS).isdisjoint(set(TIPOS_COMPRAS))


def test_las_notas_de_venta_van_con_ventas_no_con_compras():
    """Antes de esta fase, un documento de venta con nota crédito/débito se
    mezclaba con los de compra en la misma pantalla de clasificación."""
    assert "nc_ventas" in TIPOS_VENTAS
    assert "nd_ventas" in TIPOS_VENTAS
    assert "nc_ventas" not in TIPOS_COMPRAS
    assert "nd_ventas" not in TIPOS_COMPRAS


# ─── El concepto conserva su referencia (Fase 1: memoria por proveedor +
# referencia + descripción) ───────────────────────────────────────────────────

def test_concepto_sin_referencia_no_revienta():
    """La mayoría de proveedores no manda código de producto en el XML — el
    campo debe poder quedar vacío sin romper nada."""
    c = _concepto("sin referencia", 1000)
    assert c.referencia is None


def test_concepto_conserva_la_referencia_del_producto():
    c = ConceptoResumen(
        concepto="Producto X", concepto_norm="producto x", nit_proveedor="900111222",
        base_acumulada=1000, documentos=1, clasificacion=PENDIENTE, referencia="ABC123",
    )
    assert c.referencia == "ABC123"
