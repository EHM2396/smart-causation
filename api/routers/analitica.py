"""
Router: /analitica – cómo van los costos, gastos e ingresos según los documentos
electrónicos que la DIAN reporta para la empresa.

La fuente son los documentos traídos con el token, no lo que se causó: un informe
tiene que reflejar lo que pasó, no lo que se alcanzó a registrar.

El alcance depende de quién pregunta, sin endpoints separados:
  · causador  → sus propias empresas
  · admin     → todas las empresas de la cuenta

Con `empresa_id` se acota a una sola, siempre dentro de lo que ese usuario puede
ver: si pide una empresa ajena, no se le devuelve nada de ella.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from db.models.auth import Empresa, Usuario
from db.session import get_db, SessionLocal
from services import (
    analitica_service, causacion_service, dian_service, documentos_dian_service,
    informe_analitica_service, informe_pdf_service,
)
from services.dian_service import DianError

router = APIRouter(prefix="/analitica", tags=["Analítica"])

DB = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[Usuario, Depends(get_current_user)]


class SincronizarRequest(BaseModel):
    auth_url: str = Field(..., description="URL completa de AuthToken de la DIAN")
    empresa_id: int
    fecha_desde: str = Field(..., description="DD/MM/YYYY")
    fecha_hasta: str = Field(..., description="DD/MM/YYYY")


def _parse_rango(desde: str | None, hasta: str | None) -> tuple[date, date]:
    """Rango del informe. Por defecto: el año en curso (una serie mensual de un
    solo mes no dice nada)."""
    hoy = date.today()
    try:
        d = date.fromisoformat(desde) if desde else date(hoy.year, 1, 1)
    except ValueError:
        d = date(hoy.year, 1, 1)
    try:
        h = date.fromisoformat(hasta) if hasta else hoy
    except ValueError:
        h = hoy
    if h < d:
        d, h = h, d
    return d, h


def _a_fecha(ddmmyyyy: str) -> date:
    """La DIAN usa DD/MM/YYYY; la base guarda fechas reales."""
    try:
        d, m, y = ddmmyyyy.strip().split("/")
        return date(int(y), int(m), int(d))
    except (ValueError, AttributeError):
        return date.today()


def _empresa_visible(db: Session, usuario: Usuario, empresa_id: int) -> Empresa:
    """La empresa pedida, solo si este usuario puede verla."""
    if empresa_id not in analitica_service.empresas_visibles(db, usuario, usuario.cuenta_id):
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return empresa


@router.get("/resumen")
def resumen(
    db: DB,
    current_user: CurrentUser,
    desde: str | None = None,
    hasta: str | None = None,
    empresa_id: int | None = None,
):
    d, h = _parse_rango(desde, hasta)
    visibles = analitica_service.empresas_visibles(db, current_user, current_user.cuenta_id)

    if empresa_id is not None:
        if empresa_id not in visibles:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")
        visibles = [empresa_id]

    datos = analitica_service.resumen(db, empresa_ids=visibles, desde=d, hasta=h)
    es_admin = current_user.rol in ("org_admin", "admin")

    # Qué periodo se trajo la última vez: sin eso, ver el informe vacío no
    # explica si falta traer o si de verdad no hubo documentos.
    sinc = (
        documentos_dian_service.ultima_sincronizacion(db, empresa_id)
        if empresa_id is not None else None
    )
    return {
        "periodo": {"desde": d.isoformat(), "hasta": h.isoformat()},
        "alcance": "cuenta" if es_admin and empresa_id is None else "empresa",
        "empresas": len(visibles),
        "ultima_sincronizacion": {
            "desde": sinc.fecha_desde.isoformat(),
            "hasta": sinc.fecha_hasta.isoformat(),
            "documentos": sinc.documentos,
            "ejecutado_at": sinc.ejecutado_at.isoformat(),
        } if sinc else None,
        **datos,
    }


@router.get("/informe.xlsx")
def informe_xlsx(
    db: DB,
    current_user: CurrentUser,
    desde: str | None = None,
    hasta: str | None = None,
    empresa_id: int | None = None,
):
    """Descarga el informe del periodo en Excel, para enviarlo fuera de Ciolix."""
    d, h = _parse_rango(desde, hasta)
    visibles = analitica_service.empresas_visibles(db, current_user, current_user.cuenta_id)

    nombre = "Todas las empresas"
    if empresa_id is not None:
        empresa = _empresa_visible(db, current_user, empresa_id)
        visibles = [empresa_id]
        nombre = empresa.nombre

    buffer = informe_analitica_service.generar_xlsx(
        db, empresa_ids=visibles, desde=d, hasta=h, nombre_empresa=nombre,
    )
    archivo = f"ciolix_analitica_{d.isoformat()}_a_{h.isoformat()}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{archivo}"'},
    )


@router.get("/informe.pdf")
def informe_pdf(
    db: DB,
    current_user: CurrentUser,
    desde: str | None = None,
    hasta: str | None = None,
    empresa_id: int | None = None,
):
    """Informe del periodo en PDF, para enviar a un cliente o a la gerencia.

    Lleva el resumen y los gráficos; el detalle documento por documento va en el
    Excel, porque en PDF serían cientos de páginas que nadie abre.
    """
    d, h = _parse_rango(desde, hasta)
    visibles = analitica_service.empresas_visibles(db, current_user, current_user.cuenta_id)

    nombre = "Todas las empresas"
    if empresa_id is not None:
        empresa = _empresa_visible(db, current_user, empresa_id)
        visibles = [empresa_id]
        nombre = empresa.nombre

    buffer = informe_pdf_service.generar_pdf(
        db, empresa_ids=visibles, desde=d, hasta=h, nombre_empresa=nombre,
    )
    archivo = f"ciolix_analitica_{d.isoformat()}_a_{h.isoformat()}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{archivo}"'},
    )


@router.get("/empresas")
def empresas(db: DB, current_user: CurrentUser):
    """Empresas que este usuario puede filtrar en la analítica, con la fecha en
    que se trajo por última vez su información de la DIAN."""
    ids = analitica_service.empresas_visibles(db, current_user, current_user.cuenta_id)
    if not ids:
        return []
    filas = db.execute(
        select(Empresa.id, Empresa.nombre, Empresa.nit)
        .where(Empresa.id.in_(ids), Empresa.activa.is_(True))
        .order_by(Empresa.nombre)
    ).all()
    return [
        {
            "id": i, "nombre": n, "nit": nit,
            "actualizado_at": (
                lambda f: f.isoformat() if f else None
            )(documentos_dian_service.ultima_actualizacion(db, i)),
        }
        for (i, n, nit) in filas
    ]


@router.post("/sincronizar")
def sincronizar(body: SincronizarRequest, db: DB, current_user: CurrentUser):
    """Trae de la DIAN los documentos del rango y los guarda para esta empresa.

    Responde en streaming NDJSON con el progreso real, porque el listado de la
    DIAN no trae montos: hay que descargar y parsear el XML de CADA documento, y
    para un rango largo eso son minutos.

      {"type":"start","total":N}
      {"type":"progress","done":i,"total":N}
      {"type":"done","guardados":k,"errores":j}
      {"type":"error","code":"...","message":"..."}
    """
    empresa = _empresa_visible(db, current_user, body.empresa_id)

    # El token tiene que ser el de esta empresa: si no, se guardarían los
    # documentos de otra como si fueran de ella. Se verifica antes de descargar.
    if empresa.nit:
        try:
            nit_token = dian_service.nit_del_token(body.auth_url)
        except DianError as e:
            raise HTTPException(status_code=400, detail=e.message)
        if not dian_service.nits_equivalentes(nit_token, empresa.nit):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"El token es del NIT {nit_token}, pero la empresa seleccionada "
                    f"es {empresa.nombre} (NIT {empresa.nit}). "
                    "Revisa que hayas copiado el token de la empresa correcta."
                ),
            )

    empresa_id = empresa.id
    usuario_id = current_user.id

    def gen():
        # Sesión propia: el generador sigue vivo después de que termina la
        # petición, y la sesión inyectada ya estaría cerrada.
        sesion = SessionLocal()
        guardados = errores = done = 0
        try:
            try:
                ids = documentos_dian_service.listar_ids(
                    body.auth_url, body.fecha_desde, body.fecha_hasta
                )
            except DianError as e:
                yield json.dumps({"type": "error", "code": e.code, "message": e.message}) + "\n"
                return

            total = sum(len(v) for v in ids.values())
            yield json.dumps({"type": "start", "total": total}) + "\n"
            if total == 0:
                yield json.dumps({"type": "done", "guardados": 0, "errores": 0}) + "\n"
                return

            for origen in documentos_dian_service.ORIGENES:
                if not ids.get(origen):
                    continue
                for _d, _t, id_, xml in dian_service.descargar_xmls_stream(
                    body.auth_url, ids[origen], modo=origen
                ):
                    done += 1
                    if xml is None:  # se saltó por fallo de red
                        errores += 1
                        yield json.dumps({"type": "progress", "done": done, "total": total}) + "\n"
                        continue
                    try:
                        nombre = dian_service.nombre_para_parser(xml, id_)
                        for fac in causacion_service.parsear_archivo(xml, nombre):
                            documentos_dian_service.guardar_documento(
                                sesion, empresa_id=empresa_id, factura=fac, origen=origen
                            )
                            guardados += 1
                        sesion.commit()
                    except Exception:  # noqa: BLE001 — un XML malo no tumba el lote
                        sesion.rollback()
                        errores += 1
                    yield json.dumps({"type": "progress", "done": done, "total": total}) + "\n"

            documentos_dian_service.registrar_sincronizacion(
                sesion, empresa_id=empresa_id, usuario_id=usuario_id,
                desde=_a_fecha(body.fecha_desde), hasta=_a_fecha(body.fecha_hasta),
                documentos=guardados, errores=errores,
            )
            yield json.dumps({"type": "done", "guardados": guardados, "errores": errores}) + "\n"
        except DianError as e:
            yield json.dumps({"type": "error", "code": e.code, "message": e.message}) + "\n"
        finally:
            sesion.close()

    return StreamingResponse(
        gen(),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
