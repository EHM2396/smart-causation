"""
Cálculo del dígito de verificación para documentos de identificación colombianos.

La fórmula corresponde al algoritmo oficial DIAN para NIT y aplica también
para cédula de ciudadanía (tipo 13) según el formato Siigo.
"""

from __future__ import annotations
import re


# Pesos según el estándar DIAN, aplicados de izquierda a derecha sobre 15 dígitos
_PESOS_DIAN = [71, 67, 59, 53, 47, 43, 41, 37, 29, 23, 19, 17, 13, 7, 3]

# Tipos de identificación que usan dígito de verificación en Siigo
_TIPOS_CON_DV = {31, 13}


def calcular_dv(nit: str | int, tipo_identificacion: int | None = 31) -> int | None:
    """
    Calcula el dígito de verificación (DV) para un NIT o cédula colombiana.

    Args:
        nit: número de identificación (solo dígitos; se limpian guiones y espacios).
        tipo_identificacion: código DIAN del tipo de documento (31=NIT, 13=CC).
                             Si no aplica, retorna None.

    Returns:
        Dígito de verificación (0-9) o None si el tipo no usa DV.
    """
    if tipo_identificacion not in _TIPOS_CON_DV:
        return None

    digits = re.sub(r"[^\d]", "", str(nit))
    if not digits:
        return None

    padded = digits.zfill(15)
    total = sum(int(padded[i]) * _PESOS_DIAN[i] for i in range(15))
    remainder = total % 11
    return remainder if remainder < 2 else 11 - remainder


def inferir_tipo_identificacion(scheme_id: str, tipo_proveedor: str) -> int:
    """
    Infiere el código DIAN de tipo de identificación a partir del schemeID
    del XML UBL 2.1 o del tipo de persona.

    Args:
        scheme_id: atributo schemeID del CompanyID en el XML (ej. "31", "13", "22").
        tipo_proveedor: 'juridica' | 'natural'

    Returns:
        Código DIAN (entero).
    """
    try:
        code = int(scheme_id)
        if code in {11, 12, 13, 21, 22, 31, 33, 41, 42, 43, 47, 50, 89, 91}:
            return code
    except (ValueError, TypeError):
        pass
    # Fallback por tipo de persona
    return 31 if tipo_proveedor == "juridica" else 13
