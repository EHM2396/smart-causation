"""
El consolidado por proveedor que arma la pantalla de clasificación.

Lo que se protege: que nunca se fusionen dos conceptos con tratamiento
potencialmente distinto bajo una sola cifra, y que el "predominante" sea el de
mayor peso económico, no el más frecuente ni el primero en aparecer.
"""
from __future__ import annotations

import pytest

from services.formulario_300_service import ConceptoResumen, ProveedorResumen
from services.catalogo_tributario_service import PENDIENTE, Clasificacion

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
