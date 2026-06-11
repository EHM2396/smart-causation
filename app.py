"""
app.py - Causacion contable automatica para SIIGO.
Tabs:
  1. Causacion: flujo de 4 pasos (cargar, mapear, validar, descargar)
  2. Catalogos: editar codigos_impuestos.xlsx y Cuentas_contables.xlsx
"""

import os
import sys

import pandas as pd
import streamlit as st
from sqlalchemy import select

sys.path.insert(0, os.path.dirname(__file__))

from core import exporter, parser, validator
from db.models import Base
from db.models.contabilidad import FacturaCausada, Proveedor
from db.session import SessionLocal, engine
from services import (
    ai_service,
    aprendizaje_service,
    causacion_service,
    consecutivos_service,
    cuentas_service,
    impuestos_service,
    tipos_service,
)

st.set_page_config(
    page_title="Causacion SIIGO",
    page_icon="=D",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Si la app corre sin FastAPI, crea el esquema mínimo en PostgreSQL.
Base.metadata.create_all(bind=engine)

def _init_state():
    defaults = {
        "facturas_parseadas": [],
        "mapeos":             [],
        "movimientos":        [],
        "reporte":            None,
        "paso":               1,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


def _mapear_cuenta_gasto_db(db, nit: str, descripcion: str) -> tuple[str | None, list[dict], str]:
    cuenta_regla = aprendizaje_service.aplicar_reglas(db, descripcion)
    if cuenta_regla:
        return cuenta_regla, [], "regla"

    cuenta_aprendida = aprendizaje_service.obtener_mapeo(db, nit, descripcion)
    if cuenta_aprendida:
        return cuenta_aprendida, [], "aprendido"

    sugerencias = cuentas_service.buscar_cuentas_sugeridas(db, descripcion)
    if sugerencias:
        return None, sugerencias, "sugerido"

    return None, [], "manual"


def _buscar_proveedor_db(db, nit: str | None) -> Proveedor | None:
    nit_limpio = str(nit or "").strip()
    if not nit_limpio:
        return None
    return db.scalar(select(Proveedor).where(Proveedor.nit == nit_limpio))


def _guardar_proveedor_db(db, factura: dict, cuenta_pagar: str) -> None:
    nit = str(factura.get("nit") or "").strip()
    if not nit:
        return

    proveedor = db.scalar(select(Proveedor).where(Proveedor.nit == nit))
    if proveedor is None:
        proveedor = Proveedor(nit=nit)
        db.add(proveedor)

    proveedor.razon_social = factura.get("razon_social", "")
    proveedor.tipo_persona = factura.get("tipo_proveedor", "juridica")
    proveedor.regimen = factura.get("regimen", "")
    proveedor.cuenta_pagar = cuenta_pagar or proveedor.cuenta_pagar


def _idx_opcion_por_codigo(opciones_map: dict[str, str], opciones: list[str], codigo: str | None) -> int | None:
    if not codigo:
        return None
    label = next((k for k, v in opciones_map.items() if v == codigo), None)
    return opciones.index(label) if label in opciones else None


def _factura_ya_causada_db(numero_dian: str) -> bool:
    if not numero_dian:
        return False
    with SessionLocal() as db:
        return causacion_service.esta_causada(db, numero_dian)


def _listar_facturas_causadas_db() -> list[dict]:
    with SessionLocal() as db:
        rows = db.scalars(
            select(FacturaCausada).order_by(FacturaCausada.fecha_causacion.desc(), FacturaCausada.id.desc())
        ).all()
        return [
            {
                "consecutivo": r.consecutivo,
                "numero_dian": r.numero_dian,
                "razon_social": r.razon_social,
                "fecha_factura": r.fecha_factura,
            }
            for r in rows
        ]

# Sidebar
with st.sidebar:
    st.title("Causacion SIIGO")
    st.divider()
    st.subheader("Configuracion")

    # Tipo de comprobante desde la BD
    with SessionLocal() as _db_sid:
        tipos_comp = tipos_service.listar_como_opciones(_db_sid)
    if tipos_comp:
        opciones_tipos = [f"{t['codigo']} - {t['titulo']}" for t in tipos_comp]
        sel_tipo = st.selectbox("Tipo de comprobante", opciones_tipos, key="sel_tipo_comp")
        tipo_comp = sel_tipo.split(" - ")[0].strip()
    else:
        tipo_comp = st.text_input("Tipo de comprobante (codigo SIIGO)", value="12", max_chars=6)
        st.caption("Agrega tipos en la pestana Catalogos base.")

    with SessionLocal() as _db_consec_sidebar:
        ultimo_guardado = consecutivos_service.get_ultimo(_db_consec_sidebar, tipo_comp)
    st.caption(f"Ultimo consecutivo registrado: **{ultimo_guardado}**")

    ultimo_manual = st.number_input(
        "Ajustar consecutivo inicial (0 = usar el registrado)",
        min_value=0, value=0, step=1,
    )
    if ultimo_manual > 0:
        with SessionLocal() as _db_set_consec:
            consecutivos_service.set_ultimo(_db_set_consec, tipo_comp, ultimo_manual - 1)
            _db_set_consec.commit()
        st.success(f"Consecutivo ajustado. Proximo: {ultimo_manual}")

    centro_costo = st.text_input("Centro de costo (vacio si no aplica)", value="")

    st.divider()
    with st.expander("Historial de facturas causadas"):
        historial = _listar_facturas_causadas_db()
        if historial:
            df_hist = pd.DataFrame(historial)[["consecutivo", "numero_dian", "razon_social", "fecha_factura"]]
            st.dataframe(df_hist, width="stretch", hide_index=True)
        else:
            st.info("No hay facturas causadas aun.")

    st.divider()
    if st.button("Reiniciar sesion"):
        for k in ["facturas_parseadas", "mapeos", "movimientos", "reporte"]:
            st.session_state[k] = []
        st.session_state["reporte"] = None
        st.session_state["paso"] = 1
        st.rerun()

# Tabs principales
tab_caus, tab_cat = st.tabs(["Causacion", "Catalogos base"])

# TAB CAUSACION
with tab_caus:

    # Paso 1: Cargar facturas
    st.header("Paso 1 - Cargar facturas DIAN")
    st.caption("Sube el archivo xlsx exportado del token DIAN (puede contener multiples facturas).")

    archivos = st.file_uploader(
        "Selecciona uno o varios archivos .xlsx",
        type=["xlsx"],
        accept_multiple_files=True,
        key="uploader_facturas",
    )

    if archivos and st.button("Parsear facturas", type="primary"):
        facturas_ok: list[dict] = []
        errores: list[str] = []

        for archivo in archivos:
            try:
                resultados = parser.parsear_archivo(archivo, archivo.name)
                for resultado in resultados:
                    num = resultado.get("numero_dian", "")
                    if num and _factura_ya_causada_db(num):
                        errores.append(f"La factura **{num}** ya fue causada anteriormente. Se omite.")
                        continue
                    facturas_ok.append({**resultado, "_archivo": archivo.name})
                    for adv in resultado.get("advertencias", []):
                        errores.append(f"**{archivo.name} / {num}**: {adv}")
            except ValueError as e:
                errores.append(f"**{archivo.name}**: {e}")

        for e in errores:
            st.warning(e)

        if facturas_ok:
            st.session_state["facturas_parseadas"] = facturas_ok
            st.session_state["paso"] = 2
            st.success(f"{len(facturas_ok)} factura(s) listas para procesar.")
            st.rerun()
        else:
            st.error("No se pudo procesar ninguna factura valida.")

    # Paso 2: Mapeo de cuentas
    if st.session_state["paso"] >= 2 and st.session_state["facturas_parseadas"]:
        st.divider()
        st.header("Paso 2 - Revisar y confirmar cuentas contables")
        st.caption("Aprendido = del historial. Sugerido = del plan de cuentas. Manual = sin informacion previa.")

        with SessionLocal() as _db_p2:
            cuentas_gasto_disponibles = cuentas_service.listar_cuentas_gasto(_db_p2)
            cuentas_pago_disponibles  = cuentas_service.listar_metodos_pago(_db_p2)
            impuestos_disponibles     = impuestos_service.listar_como_dict(_db_p2)

        OPTS_GASTO = [f"{c['codigo']} - {c['nombre']}" for c in cuentas_gasto_disponibles]
        OPTS_GASTO_MAP = {f"{c['codigo']} - {c['nombre']}": c["codigo"] for c in cuentas_gasto_disponibles}

        OPTS_PAGO = [f"{c['codigo']} - {c['nombre']}" for c in cuentas_pago_disponibles]
        OPTS_PAGO_MAP = {f"{c['codigo']} - {c['nombre']}": c["codigo"] for c in cuentas_pago_disponibles}

        opciones_impuestos = {f"{i['cod']} ({i['porcentaje']}%)": i["cod"] for i in impuestos_disponibles}

        with st.form("form_mapeo_cuentas"):
            mapeos_sesion: list[dict] = []
            hay_pendientes = False

            for idx_fac, factura in enumerate(st.session_state["facturas_parseadas"]):
                with SessionLocal() as _db_prov_item:
                    proveedor_aprendido = _buscar_proveedor_db(_db_prov_item, factura.get("nit"))
                tipo_default = (
                    proveedor_aprendido.tipo_persona
                    if proveedor_aprendido and proveedor_aprendido.tipo_persona
                    else factura.get("tipo_proveedor", "juridica")
                )
                cuenta_pago_default = proveedor_aprendido.cuenta_pagar if proveedor_aprendido else ""
                titulo = (
                    f"{factura.get('numero_dian', 'Sin numero')} - "
                    f"{factura.get('razon_social', 'Proveedor desconocido')} | "
                    f"NIT: {factura.get('nit', '?')} | Fecha: {factura.get('fecha', '?')} | "
                    f"Total: ${factura.get('total', 0):,.0f}"
                )
                with st.expander(titulo, expanded=(idx_fac == 0)):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        nit_input = st.text_input("NIT proveedor", value=factura.get("nit", ""), key=f"nit_{idx_fac}")
                        factura["nit"] = nit_input
                    with col2:
                        tipo_prov = st.selectbox(
                            "Tipo proveedor", ["juridica", "natural"],
                            index=0 if tipo_default != "natural" else 1,
                            key=f"tipo_{idx_fac}",
                        )
                        factura["tipo_proveedor"] = tipo_prov
                    with col3:
                        st.metric("Total factura", f"${factura.get('total', 0):,.0f}")

                    if OPTS_PAGO:
                        idx_pago_default = _idx_opcion_por_codigo(OPTS_PAGO_MAP, OPTS_PAGO, cuenta_pago_default)
                        sel_pago = st.selectbox(
                            "Cuenta de pago (activo/pasivo — buscar por codigo o nombre)",
                            options=OPTS_PAGO,
                            index=idx_pago_default,
                            placeholder="Escribe para buscar...",
                            key=f"pago_{idx_fac}",
                        )
                        cuenta_pago_fac = OPTS_PAGO_MAP.get(sel_pago, "") if sel_pago else ""
                        cuenta_pago_nombre_fac = sel_pago.split(" - ", 1)[1] if sel_pago and " - " in sel_pago else ""
                        hay_pendientes = hay_pendientes or not cuenta_pago_fac
                    else:
                        st.warning("No hay cuentas de activo/pasivo de 8 digitos disponibles. Verifica el PUC.")
                        cuenta_pago_fac = ""
                        cuenta_pago_nombre_fac = ""
                        hay_pendientes = True

                    if not factura.get("items"):
                        st.warning("No se detectaron lineas de items para esta factura.")
                        continue

                    sel_gasto_global = st.selectbox(
                        "Cuenta gasto/costo para todos los items de esta factura",
                        options=OPTS_GASTO,
                        index=None,
                        placeholder="Opcional: aplica una cuenta a todos los items...",
                        key=f"cg_global_{idx_fac}",
                    )
                    cuenta_gasto_global = OPTS_GASTO_MAP.get(sel_gasto_global, "") if sel_gasto_global else ""

                    for idx_item, item in enumerate(factura["items"]):
                        st.markdown(f"**Item {idx_item + 1}:** {item['descripcion']}")
                        ci1, ci2, ci3, ci4 = st.columns([3, 2, 2, 2])

                        with ci1:
                            with SessionLocal() as _db_map_item:
                                cuenta_auto, sugerencias, fuente = _mapear_cuenta_gasto_db(
                                    _db_map_item, factura["nit"], item["descripcion"]
                                )
                            if fuente == "aprendido":
                                etiqueta = "Aprendido"
                            elif fuente == "regla":
                                etiqueta = "Regla"
                            elif fuente == "sugerido":
                                etiqueta = "Sugerido"
                            else:
                                etiqueta = "Manual"

                            ia_sugerencia = None
                            ia_preaplicada = False
                            fuente_item = fuente

                            if (
                                fuente == "manual"
                                and not cuenta_gasto_global
                                and ai_service.esta_disponible()
                            ):
                                ia_sugerencia = ai_service.sugerir(
                                    item["descripcion"],
                                    cuentas_gasto_disponibles,
                                    impuestos_disponibles,
                                    tipo_default,
                                )
                                if ia_sugerencia and ia_sugerencia.cuenta_gasto and ia_sugerencia.confianza_alta:
                                    ia_preaplicada = True
                                    fuente_item = "ia_alta"

                            codigo_ref = (
                                cuenta_gasto_global
                                or (ia_sugerencia.cuenta_gasto if ia_preaplicada and ia_sugerencia else "")
                                or cuenta_auto
                                or (sugerencias[0]["codigo"] if sugerencias else "")
                            )
                            idx_gasto_default = None
                            if codigo_ref:
                                label_ref = next(
                                    (k for k in OPTS_GASTO_MAP if OPTS_GASTO_MAP[k] == codigo_ref), None
                                )
                                if label_ref and label_ref in OPTS_GASTO:
                                    idx_gasto_default = OPTS_GASTO.index(label_ref)

                            sel_gasto = st.selectbox(
                                f"Cuenta gasto/costo ({etiqueta}) — buscar por codigo o nombre",
                                options=OPTS_GASTO,
                                index=idx_gasto_default,
                                placeholder="Escribe para buscar...",
                                key=f"cg_{idx_fac}_{idx_item}",
                            )

                            if ia_sugerencia and ia_sugerencia.cuenta_gasto:
                                _ia_lbl = next(
                                    (k for k in OPTS_GASTO_MAP if OPTS_GASTO_MAP[k] == ia_sugerencia.cuenta_gasto),
                                    ia_sugerencia.cuenta_gasto,
                                )
                                if ia_preaplicada:
                                    st.caption(
                                        f"\U0001f916 IA preselecciono: **{_ia_lbl}** "
                                        f"({ia_sugerencia.confianza:.0%}) — {ia_sugerencia.explicacion}"
                                    )
                                else:
                                    st.caption(
                                        f"\U0001f4a1 IA sugiere: **{_ia_lbl}** "
                                        f"({ia_sugerencia.confianza:.0%}) — {ia_sugerencia.explicacion}"
                                    )

                            cuenta_gasto_final = cuenta_gasto_global or (OPTS_GASTO_MAP.get(sel_gasto, "") if sel_gasto else "")
                            hay_pendientes = hay_pendientes or not cuenta_gasto_final

                        with ci2:
                            st.metric("Base", f"${item['base']:,.0f}")

                        with ci3:
                            cod_imp_aprendido = ""
                            if not item.get("cod_impuesto"):
                                with SessionLocal() as _db_imp_learn:
                                    cod_imp_aprendido = aprendizaje_service.obtener_cod_impuesto(
                                        _db_imp_learn,
                                        factura.get("nit"),
                                        item["descripcion"],
                                    ) or ""

                            cod_imp_item = item.get("cod_impuesto", "") or cod_imp_aprendido
                            cod_imp_ia = ia_sugerencia.cod_impuesto if ia_preaplicada and ia_sugerencia else ""
                            cod_imp_inicial = cod_imp_item or cod_imp_ia
                            with SessionLocal() as _db_bi:
                                imp_info = impuestos_service.buscar_como_dict(_db_bi, cod_imp_inicial) if cod_imp_inicial else None

                            if imp_info:
                                cod_imp_final = imp_info["cod"]
                                pct_final = imp_info["porcentaje"]
                                cuenta_imp_d = imp_info["cuenta_debito"]
                                cuenta_imp_c = imp_info["cuenta_credito"]
                                es_retencion = any(
                                    t in imp_info.get("naturaleza", "").lower()
                                    for t in ("retefuente", "reteica", "reteiva")
                                )
                                st.text_input(
                                    "Cod. impuesto (auto)",
                                    value=f"{cod_imp_final} — {imp_info['naturaleza']} {pct_final}%",
                                    disabled=True,
                                    key=f"imp_{idx_fac}_{idx_item}",
                                )
                                if cod_imp_aprendido and cod_imp_final == cod_imp_aprendido:
                                    st.caption("Impuesto autocompletado desde aprendizaje historico")
                            else:
                                hay_pendientes = True
                                if opciones_impuestos:
                                    imp_sel_default = next(
                                        (k for k, v in opciones_impuestos.items() if v == cod_imp_ia),
                                        None,
                                    )
                                    idx_imp_default = (
                                        list(opciones_impuestos.keys()).index(imp_sel_default)
                                        if imp_sel_default in opciones_impuestos
                                        else None
                                    )
                                    imp_sel = st.selectbox(
                                        "Cod. impuesto (seleccionar)",
                                        options=list(opciones_impuestos.keys()),
                                        index=idx_imp_default,
                                        placeholder="Escribe para buscar...",
                                        key=f"imp_sel_{idx_fac}_{idx_item}",
                                    )
                                    cod_imp_final = opciones_impuestos.get(imp_sel, "") if imp_sel else ""
                                else:
                                    cod_imp_final = st.text_input(
                                        "Cod. impuesto (manual)",
                                        value=cod_imp_item or "",
                                        key=f"imp_man_{idx_fac}_{idx_item}",
                                    )
                                with SessionLocal() as _db_bi2:
                                    imp_info2 = impuestos_service.buscar_como_dict(_db_bi2, cod_imp_final) if cod_imp_final else None
                                pct_final = imp_info2["porcentaje"] if imp_info2 else item.get("porcentaje", 0)
                                cuenta_imp_d = imp_info2["cuenta_debito"] if imp_info2 else ""
                                cuenta_imp_c = imp_info2["cuenta_credito"] if imp_info2 else ""
                                es_retencion = bool(imp_info2 and "ret" in imp_info2.get("naturaleza", "").lower())

                        with ci4:
                            st.metric("Valor impuesto", f"${item.get('valor_impuesto', 0):,.0f}")

                        mapeos_sesion.append({
                            "idx_factura":        idx_fac,
                            "descripcion":        item["descripcion"],
                            "base":               item["base"],
                            "cod_impuesto":       cod_imp_final,
                            "porcentaje":         pct_final,
                            "valor_impuesto":     item.get("valor_impuesto", 0),
                            "cuenta_gasto":       cuenta_gasto_final,
                            "cuenta_sugerida":    (
                                cuenta_auto
                                or (ia_sugerencia.cuenta_gasto if ia_sugerencia else None)
                                or (sugerencias[0]["codigo"] if sugerencias else None)
                            ),
                            "fuente":             fuente_item,
                            "ia_confianza":       ia_sugerencia.confianza if ia_sugerencia else None,
                            "ia_explicacion":     ia_sugerencia.explicacion if ia_sugerencia else None,
                            "ia_modelo":          ia_sugerencia.modelo if ia_sugerencia else None,
                            "cuenta_impuesto_deb":cuenta_imp_d,
                            "cuenta_impuesto_cre":cuenta_imp_c,
                            "es_retencion":       bool(es_retencion),
                            "cuenta_pago":        cuenta_pago_fac,
                            "cuenta_pago_nombre": cuenta_pago_nombre_fac,
                        })
                        st.divider()

            btn_label = "Validar partida doble" if not hay_pendientes else "Validar (hay campos pendientes)"
            validar_mapeo = st.form_submit_button(btn_label, type="primary")

        if validar_mapeo:
            st.session_state["mapeos"] = mapeos_sesion
            st.session_state["paso"] = 3
            st.rerun()

    # Paso 3: Validacion
    if st.session_state["paso"] >= 3 and st.session_state["mapeos"]:
        st.divider()
        st.header("Paso 3 - Validacion de partida doble")

        facturas = st.session_state["facturas_parseadas"]
        mapeos   = st.session_state["mapeos"]
        todos_movimientos: list[dict] = []

        with SessionLocal() as _db_num_real:
            ultimo_validacion = consecutivos_service.get_ultimo(_db_num_real, tipo_comp)

        for idx_fac, factura in enumerate(st.session_state["facturas_parseadas"]):
            num_real = ultimo_validacion + 1 + idx_fac
            mapeos_factura = [m for m in mapeos if m["idx_factura"] == idx_fac]
            movs = exporter.construir_movimientos(
                factura=factura,
                consecutivo=num_real,
                mapeos_confirmados=mapeos_factura,
                tipo_comprobante=tipo_comp,
                centro_costo=centro_costo,
            )
            todos_movimientos.extend(movs)

        st.session_state["movimientos"] = todos_movimientos
        reporte = validator.validar_movimientos(todos_movimientos)
        st.session_state["reporte"] = reporte

        datos_tabla = []
        for c in reporte.comprobantes:
            datos_tabla.append({
                "Consecutivo": c.consecutivo,
                "Debitos":    f"${c.total_debito:,.0f}",
                "Creditos":   f"${c.total_credito:,.0f}",
                "Diferencia": f"${c.diferencia:,.0f}",
                "Estado":     "OK" if c.cuadra else "ERROR",
            })
        datos_tabla.append({
            "Consecutivo": "TOTAL",
            "Debitos":    f"${reporte.gran_total_debitos:,.0f}",
            "Creditos":   f"${reporte.gran_total_creditos:,.0f}",
            "Diferencia": f"${reporte.diferencia_global:,.0f}",
            "Estado":     "OK" if reporte.global_cuadra else "ERROR",
        })
        st.dataframe(pd.DataFrame(datos_tabla), width="stretch", hide_index=True)

        if reporte.todos_cuadran:
            st.success("Todos los comprobantes cuadran. Puede generar el archivo.")
            if st.button("Generar importacion SIIGO", type="primary"):
                st.session_state["paso"] = 4
                st.rerun()
        else:
            st.error("Hay comprobantes que no cuadran. Revise el mapeo de cuentas.")
            for c in reporte.comprobantes_invalidos:
                st.warning(f"**{c.consecutivo}**: diferencia de ${c.diferencia:,.0f}")
            if st.button("Volver al Paso 2"):
                st.session_state["paso"] = 2
                st.rerun()

    # Paso 4: Descarga
    if st.session_state["paso"] >= 4 and st.session_state["movimientos"]:
        st.divider()
        st.header("Paso 4 - Descargar e importar a SIIGO")

        movimientos = st.session_state["movimientos"]
        facturas    = st.session_state["facturas_parseadas"]
        mapeos      = st.session_state["mapeos"]
        reporte     = st.session_state["reporte"]

        xlsx_buffer = exporter.generar_xlsx(movimientos)
        nombre_archivo = exporter.nombre_archivo_salida()

        col_dl, col_info = st.columns([2, 3])
        with col_dl:
            st.download_button(
                label="Descargar importacion_SIIGO.xlsx",
                data=xlsx_buffer,
                file_name=nombre_archivo,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
        with col_info:
            with SessionLocal() as _db_ultimo_p4:
                ultimo_c = consecutivos_service.get_ultimo(_db_ultimo_p4, tipo_comp)
            total_f  = len(facturas)
            st.markdown(f"""
            **Resumen**
            - Facturas: **{total_f}**
            - Primer consecutivo: **{ultimo_c + 1}**
            - Ultimo consecutivo: **{ultimo_c + total_f}**
            - Total debitos: **${reporte.gran_total_debitos:,.0f}**
            - Total creditos: **${reporte.gran_total_creditos:,.0f}**
            """)

        if st.button("Confirmar importacion y guardar aprendizaje", type="primary"):
            try:
                with SessionLocal() as db_confirm:
                    ultimo_actual = consecutivos_service.get_ultimo(db_confirm, tipo_comp)
                    for idx_fac, factura in enumerate(facturas):
                        num_c = ultimo_actual + 1 + idx_fac
                        mapeos_factura = [x for x in mapeos if x["idx_factura"] == idx_fac]
                        cuenta_pagar = next((m.get("cuenta_pago", "") for m in mapeos_factura if m.get("cuenta_pago")), "")

                        _guardar_proveedor_db(db_confirm, factura, cuenta_pagar)
                        if not causacion_service.esta_causada(db_confirm, factura.get("numero_dian", "")):
                            causacion_service.registrar_factura_causada(
                                db_confirm,
                                factura=factura,
                                consecutivo=num_c,
                                tipo_comprobante=tipo_comp,
                                archivo_origen=factura.get("_archivo", ""),
                            )
                        for m in mapeos_factura:
                            if m.get("cuenta_gasto") and factura.get("nit"):
                                causacion_service.confirmar_mapeo(
                                    db_confirm,
                                    numero_dian=factura.get("numero_dian", ""),
                                    nit=factura.get("nit"),
                                    descripcion=m["descripcion"],
                                    cuenta_sugerida=m.get("cuenta_sugerida"),
                                    cuenta_aplicada=m["cuenta_gasto"],
                                    cod_impuesto=m.get("cod_impuesto"),
                                    origen=m.get("fuente", "manual"),
                                )

                    nuevo_ultimo = ultimo_actual + len(facturas)
                    consecutivos_service.set_ultimo(db_confirm, tipo_comp, nuevo_ultimo)
                    db_confirm.commit()
            except Exception as exc:
                st.error(f"No se pudo guardar la importacion en la base de datos: {exc}")
            else:
                st.success(f"Importacion confirmada. Proximo consecutivo: **{nuevo_ultimo + 1}**")
                st.balloons()
                for k in ["facturas_parseadas", "mapeos", "movimientos"]:
                    st.session_state[k] = []
                st.session_state["reporte"] = None
                st.session_state["paso"] = 1


# TAB CATALOGOS
with tab_cat:
    st.header("Catalogos base")
    st.caption("Los registros existentes son de solo lectura. Usa los formularios para agregar nuevos registros.")

    sub_imp, sub_cuentas, sub_tipos = st.tabs(["Codigos de Impuesto", "Plan de Cuentas PUC", "Tipos de Comprobante"])

    # ── Codigos de impuesto ───────────────────────────────────────────────────
    with sub_imp:
        st.subheader("Codigos de Impuesto")
        with SessionLocal() as _db_imp_tab:
            impuestos_db = impuestos_service.listar_como_dict(_db_imp_tab)

        if impuestos_db:
            df_imp_view = pd.DataFrame(impuestos_db).rename(columns={
                "cod": "Codigo", "porcentaje": "%", "naturaleza": "Tipo",
                "cuenta_debito": "Cta. Debito", "cuenta_credito": "Cta. Credito",
            })
            st.dataframe(df_imp_view, use_container_width=True, hide_index=True)
        else:
            st.info("No hay codigos de impuesto en la base de datos.")

        st.divider()
        st.subheader("Agregar nuevo codigo de impuesto")
        with st.form("form_nuevo_imp", clear_on_submit=True):
            ci1, ci2, ci3 = st.columns(3)
            with ci1:
                imp_codigo   = st.text_input("Codigo SIIGO", placeholder="ej. IVA19")
                imp_tipo     = st.text_input("Tipo impuesto", placeholder="ej. IVA")
            with ci2:
                imp_tarifa   = st.number_input("Tarifa %", min_value=0.0, max_value=100.0, step=0.5, value=0.0)
                imp_cta_deb  = st.text_input("Cuenta debito (PUC)", placeholder="ej. 24080501")
            with ci3:
                imp_cta_cre  = st.text_input("Cuenta credito (PUC)", placeholder="ej. 24080501")
                imp_cta_ven  = st.text_input("Cta. ventas (opcional)", placeholder="")
            imp_ok = st.form_submit_button("Agregar impuesto", type="primary")
            if imp_ok:
                if not imp_codigo.strip():
                    st.error("El codigo es obligatorio.")
                else:
                    try:
                        with SessionLocal() as _db_add_imp:
                            existente = impuestos_service.buscar_por_codigo(_db_add_imp, imp_codigo.strip())
                            if existente:
                                st.error(f"El codigo **{imp_codigo.strip()}** ya existe.")
                            else:
                                impuestos_service.crear_impuesto(
                                    _db_add_imp,
                                    codigo        = imp_codigo.strip(),
                                    tipo_impuesto = imp_tipo.strip() or None,
                                    tarifa        = float(imp_tarifa),
                                    cuenta_debito = imp_cta_deb.strip() or None,
                                    cuenta_credito= imp_cta_cre.strip() or None,
                                    cta_ventas    = imp_cta_ven.strip() or None,
                                )
                                _db_add_imp.commit()
                                st.success(f"Impuesto **{imp_codigo.strip()}** agregado.")
                                st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

    # ── Plan de cuentas PUC ───────────────────────────────────────────────────
    with sub_cuentas:
        st.subheader("Plan de Cuentas PUC")

        col_bus, col_cls = st.columns([3, 1])
        with col_bus:
            busqueda_cta = st.text_input("Buscar por codigo o nombre", placeholder="ej. 519500 o publicidad", key="bus_cta")
        with col_cls:
            filtro_clase = st.selectbox("Clase", ["Todas", "1", "2", "3", "4", "5", "6", "7", "8", "9"], key="fil_clase")

        with SessionLocal() as _db_cta_tab:
            from sqlalchemy import select as _select
            from db.models.catalogo import CuentaContable as _CC
            stmt_cta = _select(_CC).where(_CC.activo == True)
            if filtro_clase != "Todas":
                stmt_cta = stmt_cta.where(_CC.clase == int(filtro_clase))
            todas_ctas = _db_cta_tab.scalars(stmt_cta.order_by(_CC.codigo)).all()

        if busqueda_cta:
            busq_n = busqueda_cta.strip().lower()
            todas_ctas = [c for c in todas_ctas if busq_n in c.codigo or busq_n in c.nombre.lower()]

        if todas_ctas:
            df_ctas = pd.DataFrame([
                {"Codigo": c.codigo, "Nombre": c.nombre, "Nivel": c.nivel, "Fiscal": c.fiscal}
                for c in todas_ctas[:500]
            ])
            st.caption(f"Mostrando {len(df_ctas)} de {len(todas_ctas)} cuentas" + (" (limite 500)" if len(todas_ctas) > 500 else ""))
            st.dataframe(df_ctas, use_container_width=True, hide_index=True)
        else:
            st.info("No se encontraron cuentas.")

        st.divider()
        st.subheader("Agregar nueva cuenta PUC")
        with st.form("form_nueva_cuenta", clear_on_submit=True):
            cc1, cc2 = st.columns(2)
            with cc1:
                cta_codigo = st.text_input("Codigo PUC (solo digitos)", placeholder="ej. 51950501")
                cta_nombre = st.text_input("Nombre de la cuenta", placeholder="ej. Publicidad digital")
            with cc2:
                cta_fiscal = st.checkbox("Es cuenta fiscal (diferencia fiscal)", value=False)
                st.caption("El nivel y clase se calculan automaticamente del codigo.")
            cta_ok = st.form_submit_button("Agregar cuenta", type="primary")
            if cta_ok:
                cod_c = cta_codigo.strip()
                nom_c = cta_nombre.strip()
                if not cod_c or not nom_c:
                    st.error("Codigo y nombre son obligatorios.")
                elif not cod_c.isdigit():
                    st.error("El codigo debe contener solo digitos.")
                else:
                    try:
                        with SessionLocal() as _db_add_cta:
                            existente = cuentas_service.buscar_por_codigo(_db_add_cta, cod_c)
                            if existente:
                                st.error(f"El codigo **{cod_c}** ya existe.")
                            else:
                                cuentas_service.crear_cuenta(_db_add_cta, codigo=cod_c, nombre=nom_c, fiscal=cta_fiscal)
                                _db_add_cta.commit()
                                st.success(f"Cuenta **{cod_c} - {nom_c}** agregada.")
                                st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

    # ── Tipos de comprobante contable ─────────────────────────────────────────
    with sub_tipos:
        st.subheader("Tipos de Comprobante")
        with SessionLocal() as _db_tip_tab:
            tipos_db = tipos_service.listar_como_opciones(_db_tip_tab)

        if tipos_db:
            df_tipos_view = pd.DataFrame(tipos_db)[["codigo", "titulo"]].rename(
                columns={"codigo": "Codigo", "titulo": "Titulo"}
            )
            st.dataframe(df_tipos_view, use_container_width=True, hide_index=True)
        else:
            st.info("No hay tipos de comprobante en la base de datos.")

        st.divider()
        st.subheader("Agregar nuevo tipo de comprobante")
        with st.form("form_nuevo_tipo", clear_on_submit=True):
            col_tc1, col_tc2 = st.columns(2)
            with col_tc1:
                nuevo_codigo = st.text_input(
                    "Codigo del comprobante",
                    placeholder="ej. 25",
                    help="Codigo numerico unico en SIIGO",
                )
            with col_tc2:
                nuevo_titulo = st.text_input(
                    "Titulo comprobante",
                    placeholder="ej. Compras nacionales",
                )
            enviado = st.form_submit_button("Agregar tipo", type="primary")
            if enviado:
                if not nuevo_codigo.strip() or not nuevo_titulo.strip():
                    st.error("Debe ingresar el codigo y el titulo del comprobante.")
                else:
                    try:
                        with SessionLocal() as _db_add_tip:
                            existente = tipos_service.buscar_por_codigo(_db_add_tip, nuevo_codigo.strip())
                            if existente:
                                st.error(f"El codigo **{nuevo_codigo.strip()}** ya existe.")
                            else:
                                tipos_service.crear_tipo(
                                    _db_add_tip,
                                    codigo=nuevo_codigo.strip(),
                                    titulo=nuevo_titulo.strip(),
                                )
                                _db_add_tip.commit()
                                st.success(f"Tipo **{nuevo_codigo.strip()} - {nuevo_titulo.strip()}** agregado.")
                                st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

