"""Tope de 4 meses por consulta en los módulos que extraen con el token DIAN
(importador y Analítica)."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.routers.analitica import SincronizarRequest, sincronizar
from api.routers.dian import _validar_rango_consulta
from services import dian_service
from services.dian_service import DianError


def test_un_anio_traido_en_tres_partes_queda_cubierto_completo():
    from datetime import date
    from services.documentos_dian_service import unir_periodos
    partes = [
        (date(2026, 9, 1), date(2026, 12, 31)),
        (date(2026, 1, 1), date(2026, 4, 30)),
        (date(2026, 5, 1), date(2026, 8, 31)),
    ]
    assert unir_periodos(partes) == [(date(2026, 1, 1), date(2026, 12, 31))]


def test_periodos_con_hueco_no_se_unen():
    from datetime import date
    from services.documentos_dian_service import unir_periodos
    partes = [(date(2026, 1, 1), date(2026, 2, 28)), (date(2026, 4, 1), date(2026, 4, 30))]
    assert unir_periodos(partes) == partes


def test_periodos_solapados_o_repetidos_se_unen():
    from datetime import date
    from services.documentos_dian_service import unir_periodos
    partes = [
        (date(2026, 1, 1), date(2026, 3, 31)),
        (date(2026, 2, 1), date(2026, 2, 28)),   # dentro del anterior
        (date(2026, 3, 15), date(2026, 5, 31)),  # se solapa
    ]
    assert unir_periodos(partes) == [(date(2026, 1, 1), date(2026, 5, 31))]


def test_la_regla_vive_en_el_servicio():
    dian_service.validar_rango_consulta("01/01/2026", "30/04/2026")
    with pytest.raises(DianError) as e:
        dian_service.validar_rango_consulta("01/01/2026", "01/05/2026")
    assert e.value.code == "RANGO_INVALIDO"


def test_analitica_rechaza_mas_de_cuatro_meses_antes_de_tocar_la_dian():
    body = SincronizarRequest(
        auth_url="https://catalogo-vpfe.dian.gov.co/User/AuthToken?pk=1&rk=2&token=3",
        empresa_id=1, fecha_desde="01/01/2026", fecha_hasta="31/12/2026",
    )
    # Sin base de datos ni usuario: si validara después, reventaría por otro lado.
    with pytest.raises(HTTPException) as e:
        sincronizar(body, db=None, current_user=None)
    assert e.value.status_code == 400
    assert "4 meses" in e.value.detail


@pytest.mark.parametrize("desde, hasta", [
    ("01/01/2026", "30/04/2026"),   # cuatrimestre completo: justo el máximo
    ("01/09/2026", "30/09/2026"),   # mes actual
    ("15/03/2026", "14/07/2026"),
    ("31/10/2026", "27/02/2027"),   # feb no tiene 31: el tope se ajusta al último día
    ("10/05/2026", "10/05/2026"),   # un solo día
])
def test_rangos_permitidos(desde, hasta):
    _validar_rango_consulta(desde, hasta)


@pytest.mark.parametrize("desde, hasta", [
    ("01/01/2026", "01/05/2026"),   # un día de más
    ("01/01/2026", "31/12/2026"),
    ("15/03/2026", "15/07/2026"),
])
def test_mas_de_cuatro_meses_se_rechaza(desde, hasta):
    with pytest.raises(HTTPException) as e:
        _validar_rango_consulta(desde, hasta)
    assert e.value.status_code == 400
    assert "4 meses" in e.value.detail


def test_rango_invertido_se_rechaza():
    with pytest.raises(HTTPException):
        _validar_rango_consulta("30/04/2026", "01/01/2026")


def test_formato_invalido_se_rechaza():
    with pytest.raises(HTTPException):
        _validar_rango_consulta("2026-01-01", "2026-04-30")
