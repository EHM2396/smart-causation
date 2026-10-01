"""Validación de correos al registrar/crear usuarios."""
from __future__ import annotations

import pytest

from core.correo import email_valido, normalizar_email


@pytest.mark.parametrize("email", [
    "auditoria@salamancayasociados.com",
    "auditoria@salamancayasociados.com.co",
    "Dayana.Perez+ciolix@Empresa.CO",
    "  usuario@empresa.net  ",
    "a_b-c@sub.dominio-uno.org",
])
def test_correos_validos(email):
    assert email_valido(email)


@pytest.mark.parametrize("email", [
    "auditoria@salamancayasociados",   # caso real: le falta la extensión
    "auditoria@salamancayasociados.",
    "auditoria@.com",
    "auditoria@salamanca..com",
    "auditoria.salamanca.com",
    "@empresa.com",
    "usuario@empresa.c",
    "usuario@empresa.123",
    "usu ario@empresa.com",
    "usuario@-empresa.com",
    "",
])
def test_correos_invalidos(email):
    assert not email_valido(email)


def test_normalizar_email():
    assert normalizar_email("  Usuario@Empresa.COM ") == "usuario@empresa.com"
