"""
Router: /cuentas – CRUD + carga masiva del plan de cuentas PUC.
Requiere autenticación; filtra por empresa activa.
"""

from __future__ import annotations

from io import BytesIO
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from sqlalchemy.orm import Session

from api.dependencies import get_empresa_activa
from api.schemas import CuentaCreate, CuentaOpcion, CuentaOut
from db.models.auth import Empresa
from db.session import get_db
from services import cuentas_service

router = APIRouter(prefix="/cuentas", tags=["Cuentas Contables"])

DB = Annotated[Session, Depends(get_db)]
EmpresaActiva = Annotated[Empresa, Depends(get_empresa_activa)]


@router.get("/gasto", response_model=list[CuentaOpcion])
def get_cuentas_gasto(db: DB, empresa: EmpresaActiva):
    return cuentas_service.listar_cuentas_gasto(db, empresa_id=empresa.id)


@router.get("/pago", response_model=list[CuentaOpcion])
def get_metodos_pago(db: DB, empresa: EmpresaActiva):
    return cuentas_service.listar_metodos_pago(db, empresa_id=empresa.id)


@router.get("/sugerencias", response_model=list[dict])
def get_sugerencias(
    descripcion: Annotated[str, Query(min_length=3)],
    db: DB,
    empresa: EmpresaActiva,
    max: int = 3,
):
    return cuentas_service.buscar_cuentas_sugeridas(db, descripcion, max, empresa_id=empresa.id)


@router.get("/plantilla")
def descargar_plantilla(empresa: EmpresaActiva):
    """Descarga un Excel de ejemplo con el formato esperado para importación."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Plan de Cuentas"

    headers = ["codigo", "nombre", "fiscal"]
    ejemplos = [
        ["51050505", "Honorarios servicios profesionales",      "NO"],
        ["51050510", "Asesorías jurídicas",                     "NO"],
        ["51100505", "Arrendamiento oficinas",                  "NO"],
        ["51200505", "Publicidad y propaganda",                 "NO"],
        ["23650500", "Retención en la fuente por pagar",        "NO"],
        ["24080500", "IVA por pagar",                           "NO"],
        ["22050505", "Proveedores nacionales",                  "NO"],
        ["11100501", "Caja general",                            "NO"],
        ["11200501", "Banco cuenta corriente",                  "NO"],
    ]

    header_fill = PatternFill("solid", fgColor="1C6B4A")
    header_font = Font(bold=True, color="FFFFFF")
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_data in ejemplos:
        ws.append(row_data)

    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 45
    ws.column_dimensions["C"].width = 10

    ws.append([])
    nota = ws.cell(row=len(ejemplos) + 3, column=1, value="fiscal: SI o NO (default NO). Usar 8 dígitos para cuentas auxiliares.")
    nota.font = Font(italic=True, color="666666")

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_plan_cuentas.xlsx"},
    )


@router.post("/cargar-excel")
async def cargar_excel(
    db: DB,
    empresa: EmpresaActiva,
    archivo: UploadFile = File(...),
):
    """Importa cuentas PUC desde un Excel. Columnas obligatorias: codigo, nombre. Hace upsert."""
    contenido = await archivo.read()
    try:
        df = pd.read_excel(BytesIO(contenido), dtype=str)
    except Exception as e:
        raise HTTPException(400, f"No se pudo leer el archivo: {e}")

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    for col in ("codigo", "nombre"):
        if col not in df.columns:
            raise HTTPException(400, f"El archivo debe tener una columna '{col}'.")

    insertados = 0
    actualizados = 0
    errores: list[dict] = []

    for idx, row in df.iterrows():
        fila = int(idx) + 2
        codigo = str(row.get("codigo", "")).strip()
        nombre = str(row.get("nombre", "")).strip()

        if not codigo or not nombre or nombre == "nan":
            errores.append({"fila": fila, "error": "Código o nombre vacío"})
            continue

        fiscal_raw = str(row.get("fiscal", "NO")).strip().upper()
        fiscal = fiscal_raw in ("SI", "SÍ", "S", "1", "TRUE", "YES")

        try:
            _, creado = cuentas_service.upsert_cuenta(
                db,
                codigo=codigo,
                nombre=nombre,
                fiscal=fiscal,
                empresa_id=empresa.id,
            )
            if creado:
                insertados += 1
            else:
                actualizados += 1
        except Exception as e:
            errores.append({"fila": fila, "error": str(e)})

    db.commit()
    return {"insertados": insertados, "actualizados": actualizados, "errores": errores}


@router.get("/{codigo}", response_model=CuentaOut)
def get_cuenta(codigo: str, db: DB, empresa: EmpresaActiva):
    cuenta = cuentas_service.buscar_por_codigo(db, codigo, empresa_id=empresa.id)
    if not cuenta:
        raise HTTPException(404, f"Cuenta {codigo!r} no encontrada")
    return cuenta


@router.post("/", response_model=CuentaOut, status_code=201)
def post_cuenta(body: CuentaCreate, db: DB, empresa: EmpresaActiva):
    if cuentas_service.buscar_por_codigo(db, body.codigo, empresa_id=empresa.id):
        raise HTTPException(409, f"El código {body.codigo!r} ya existe")
    cuenta = cuentas_service.crear_cuenta(
        db,
        codigo=body.codigo,
        nombre=body.nombre,
        fiscal=body.fiscal,
        empresa_id=empresa.id,
    )
    db.commit()
    return cuenta
