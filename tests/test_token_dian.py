"""
El token de la DIAN debe corresponder a la empresa seleccionada.

Sin este control, pegar el token equivocado importa los documentos de OTRA
empresa como si fueran de esta, y quedan mezclados en el historial sin ninguna
señal de que algo salió mal. La DIAN pone el NIT del titular en el parámetro
`rk` de la URL, así que se puede verificar antes de descargar nada.
"""
from __future__ import annotations

import pytest

from services.dian_service import DianError, nit_del_token, nits_equivalentes, solo_digitos

pytestmark = pytest.mark.dian

BASE = "https://catalogo-vpfe.dian.gov.co/User/AuthToken"
TOKEN_OK = f"{BASE}?pk=10910094|1114735357&rk=901694417&token=dd6ce846-aa3a-4d63-ac63-b3ba96fdd359"


# ─── NIT del titular del token ───────────────────────────────────────────────

def test_saca_el_nit_del_parametro_rk():
    assert nit_del_token(TOKEN_OK) == "901694417"


def test_limpia_el_nit_de_separadores():
    url = f"{BASE}?pk=1|2&rk=901.694.417-1&token=abc"
    assert nit_del_token(url) == "9016944171"


@pytest.mark.parametrize("url", [
    "https://otra-web.com/User/AuthToken?pk=1&rk=2&token=3",   # dominio ajeno
    f"{BASE}?pk=1&token=3",                                    # sin rk
    "no-es-una-url",
])
def test_rechaza_urls_que_no_son_un_token_valido(url):
    with pytest.raises(DianError):
        nit_del_token(url)


# ─── Comparación de NIT, tolerando el dígito de verificación ─────────────────
#
# El mismo NIT se escribe de varias formas según de dónde venga: la DIAN manda
# '901694417' y la empresa puede estar guardada como '901694417-1'. Comparar los
# textos tal cual daría "no coinciden" para el mismo contribuyente.

@pytest.mark.parametrize("a,b", [
    ("901694417", "901694417"),
    ("901694417", "901694417-1"),      # uno trae dígito de verificación
    ("901694417-1", "901694417"),
    ("901.694.417", "901694417"),      # separadores de miles
    ("9016944171", "901694417"),
])
def test_nits_que_son_el_mismo(a, b):
    assert nits_equivalentes(a, b) is True


@pytest.mark.parametrize("a,b", [
    ("901694417", "800123456"),        # empresas distintas
    ("901694417", "90169441"),         # le falta un dígito, no es el DV
    ("901694417", ""),                 # sin NIT no se puede afirmar que coincida
    ("", "901694417"),
    (None, "901694417"),
])
def test_nits_que_no_coinciden(a, b):
    assert nits_equivalentes(a, b) is False


def test_no_confunde_nits_que_solo_difieren_en_el_ultimo_digito():
    """'9016944171' y '9016944172' tienen el mismo largo: son NIT distintos, no
    el mismo con otro dígito de verificación."""
    assert nits_equivalentes("9016944171", "9016944172") is False


# ─── Normalización ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("valor,esperado", [
    ("901.694.417-1", "9016944171"),
    ("  901694417  ", "901694417"),
    ("NIT 901694417", "901694417"),
    (None, ""),
    ("", ""),
])
def test_solo_digitos(valor, esperado):
    assert solo_digitos(valor) == esperado
