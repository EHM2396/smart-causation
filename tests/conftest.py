"""
Utilidades compartidas por las pruebas.

Estas pruebas son de LÓGICA PURA: no tocan base de datos, ni red, ni la DIAN.
Por eso corren en segundos y se pueden ejecutar en cada cambio sin fricción.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Permite importar core/, services/, api/ al correr pytest desde la raíz del repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ─── Constructor de XML DIAN sintético ────────────────────────────────────────

_NS_INVOICE = (
    'xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
    'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
    'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"'
)
_NS_CREDIT = (
    'xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2" '
    'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
    'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"'
)


def linea_xml(
    descripcion: str,
    base: float,
    *,
    iva_pct: float | None = None,
    iva_valor: float = 0.0,
    otros: list[tuple[str, float, float]] | None = None,
    descuento: float = 0.0,
    tag: str = "InvoiceLine",
    referencia: str | None = None,
) -> str:
    """Una línea de factura.

    `iva_pct=None` → la línea NO trae bloque de IVA (caso "sin tarifa").
    `otros` → lista de (codigo_tributo_dian, valor, porcentaje) p. ej. INC, IBUA.
    """
    partes = [f"<cbc:LineExtensionAmount currencyID='COP'>{base}</cbc:LineExtensionAmount>"]

    if descuento:
        partes.append(
            "<cac:AllowanceCharge>"
            "<cbc:ChargeIndicator>false</cbc:ChargeIndicator>"
            f"<cbc:Amount currencyID='COP'>{descuento}</cbc:Amount>"
            "</cac:AllowanceCharge>"
        )

    if iva_pct is not None:
        partes.append(
            "<cac:TaxTotal><cac:TaxSubtotal>"
            f"<cbc:TaxableAmount currencyID='COP'>{base}</cbc:TaxableAmount>"
            f"<cbc:TaxAmount currencyID='COP'>{iva_valor}</cbc:TaxAmount>"
            f"<cac:TaxCategory><cbc:Percent>{iva_pct}</cbc:Percent>"
            "<cac:TaxScheme><cbc:ID>01</cbc:ID></cac:TaxScheme>"
            "</cac:TaxCategory></cac:TaxSubtotal></cac:TaxTotal>"
        )

    for cod, valor, pct in (otros or []):
        partes.append(
            "<cac:TaxTotal><cac:TaxSubtotal>"
            f"<cbc:TaxableAmount currencyID='COP'>{base}</cbc:TaxableAmount>"
            f"<cbc:TaxAmount currencyID='COP'>{valor}</cbc:TaxAmount>"
            f"<cac:TaxCategory><cbc:Percent>{pct}</cbc:Percent>"
            f"<cac:TaxScheme><cbc:ID>{cod}</cbc:ID></cac:TaxScheme>"
            "</cac:TaxCategory></cac:TaxSubtotal></cac:TaxTotal>"
        )

    sellers_id = (
        f"<cac:SellersItemIdentification><cbc:ID>{referencia}</cbc:ID></cac:SellersItemIdentification>"
        if referencia else ""
    )
    partes.append(f"<cac:Item><cbc:Description>{descripcion}</cbc:Description>{sellers_id}</cac:Item>")
    return f"<cac:{tag}>{''.join(partes)}</cac:{tag}>"


def factura_xml(
    lineas: list[str],
    *,
    numero: str = "SETP001",
    total: float = 0.0,
    nit_emisor: str = "900123456",
    nit_receptor: str = "800999888",
    nota_credito: bool = False,
    customization: str | None = None,
    descuento_global: float = 0.0,
    recargo_global: float = 0.0,
) -> bytes:
    """Arma un XML UBL de la DIAN con la forma que usa el parser."""
    raiz = "CreditNote" if nota_credito else "Invoice"
    ns = _NS_CREDIT if nota_credito else _NS_INVOICE
    cust = f"<cbc:CustomizationID>{customization}</cbc:CustomizationID>" if customization else ""
    tipo_nota = "<cbc:CreditNoteTypeCode>91</cbc:CreditNoteTypeCode>" if nota_credito else ""

    cargos = ""
    if descuento_global:
        cargos += (
            "<cac:AllowanceCharge><cbc:ChargeIndicator>false</cbc:ChargeIndicator>"
            f"<cbc:Amount currencyID='COP'>{descuento_global}</cbc:Amount></cac:AllowanceCharge>"
        )
    if recargo_global:
        cargos += (
            "<cac:AllowanceCharge><cbc:ChargeIndicator>true</cbc:ChargeIndicator>"
            f"<cbc:Amount currencyID='COP'>{recargo_global}</cbc:Amount></cac:AllowanceCharge>"
        )

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<{raiz} {ns}>
  <cbc:ID>{numero}</cbc:ID>
  <cbc:UUID>cufe-de-prueba</cbc:UUID>
  <cbc:IssueDate>2026-09-15</cbc:IssueDate>
  {cust}{tipo_nota}
  <cac:AccountingSupplierParty><cac:Party>
    <cac:PartyTaxScheme><cbc:CompanyID schemeID="31">{nit_emisor}</cbc:CompanyID></cac:PartyTaxScheme>
    <cac:PartyLegalEntity><cbc:RegistrationName>Proveedor de Prueba SAS</cbc:RegistrationName></cac:PartyLegalEntity>
  </cac:Party></cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty><cac:Party>
    <cac:PartyTaxScheme><cbc:CompanyID schemeID="31">{nit_receptor}</cbc:CompanyID></cac:PartyTaxScheme>
    <cac:PartyLegalEntity><cbc:RegistrationName>Cliente de Prueba SAS</cbc:RegistrationName></cac:PartyLegalEntity>
  </cac:Party></cac:AccountingCustomerParty>
  {cargos}
  <cac:LegalMonetaryTotal><cbc:PayableAmount currencyID="COP">{total}</cbc:PayableAmount></cac:LegalMonetaryTotal>
  {''.join(lineas)}
</{raiz}>"""
    return xml.encode("utf-8")


# ─── Fixtures de mapeos contables ─────────────────────────────────────────────

@pytest.fixture
def mapeo_simple():
    """Un ítem: base 100.000 + IVA 19% (19.000). Cuentas de gasto e IVA típicas."""
    return {
        "descripcion": "Producto de prueba",
        "base": 100000.0,
        "valor_impuesto": 19000.0,
        "porcentaje": 19.0,
        "cod_impuesto": "1",
        "es_retencion": False,
        "cuenta_gasto": "519530",
        "cuenta_impuesto_deb": "240820",
        "cuenta_impuesto_cre": "",
        "cuenta_pago": "",
        "cuenta_pago_nombre": "Proveedor de Prueba SAS",
    }


@pytest.fixture
def factura_simple():
    """Factura de 119.000 (100.000 base + 19.000 IVA)."""
    return {
        "numero_dian": "SETP001",
        "cufe": "cufe-de-prueba",
        "fecha": "15/09/2026",
        "nit": "900123456",
        "razon_social": "Proveedor de Prueba SAS",
        "tipo_proveedor": "juridica",
        "total": 119000.0,
        "descuento_global": 0.0,
        "recargo_global": 0.0,
    }


def sumar(movimientos: list[dict]) -> tuple[float, float]:
    """(total_debitos, total_creditos) de un comprobante."""
    deb = sum(float(m["Débito"] or 0) for m in movimientos)
    cre = sum(float(m["Crédito"] or 0) for m in movimientos)
    return round(deb, 2), round(cre, 2)
