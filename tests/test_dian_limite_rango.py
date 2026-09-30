"""Tope de 4 meses por consulta en el importador DIAN."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.routers.dian import _validar_rango_consulta


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
