"""
Backfill de tipo_causacion en facturas_causadas ya guardadas.

El campo tipo_causacion (módulo: compras/nc/ventas/nc_ventas/soporte/nc_soporte)
se agregó después de que muchas facturas ya se hubieran causado — esas filas
quedaron con tipo_causacion=NULL. Este script las completa a partir de
`datos_json` (que ya guarda la factura parseada y el flag es_venta), usando la
MISMA lógica que aplica el backend al causar
(services.causacion_service.derivar_tipo_causacion), así el resultado es
idéntico al de una causación nueva.

Solo hace UPDATE de tipo_causacion, y solo en filas que hoy están en NULL.
NUNCA borra filas ni sobrescribe un tipo_causacion que ya tuviera valor.
Los registros SIN datos_json (de antes de que se guardara ese detalle) no se
pueden clasificar con certeza y quedan igual (sin tipo) — no se adivina.

Uso:
    # 1) Identificar (no escribe nada):
    python scripts/backfill_tipo_causacion.py

    # 2) Respaldar a CSV y aplicar los cambios:
    python scripts/backfill_tipo_causacion.py --apply

    # Opcional: acotar a una empresa
    python scripts/backfill_tipo_causacion.py --apply --empresa 3

En Docker (recordar PYTHONPATH=/app, si no `python scripts/x.py` no encuentra
el paquete db):
    PYTHONPATH=/app python scripts/backfill_tipo_causacion.py
    PYTHONPATH=/app python scripts/backfill_tipo_causacion.py --apply
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime

from sqlalchemy import func, select

from db.session import SessionLocal, DATABASE_URL
from db.models.contabilidad import FacturaCausada
from scripts.respaldos import ruta_respaldo
from services.causacion_service import derivar_tipo_causacion


def _db_resumen(url: str) -> str:
    """Muestra host/base sin exponer credenciales, para confirmar contra qué BD corre."""
    try:
        return url.split("@", 1)[1] if "@" in url else url
    except Exception:
        return "(desconocida)"


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill de tipo_causacion en facturas_causadas")
    parser.add_argument("--apply", action="store_true", help="Aplica los cambios (por defecto: solo reporta)")
    parser.add_argument("--empresa", type=int, default=None, help="Filtrar por empresa_id")
    args = parser.parse_args()

    print(f"Base de datos objetivo: {_db_resumen(DATABASE_URL)}")
    print(f"Modo: {'APLICAR CAMBIOS' if args.apply else 'DRY RUN (solo reporte)'}\n")

    with SessionLocal() as db:
        stmt = select(FacturaCausada).where(
            FacturaCausada.tipo_causacion.is_(None),
            FacturaCausada.datos_json.is_not(None),
        )
        if args.empresa is not None:
            stmt = stmt.where(FacturaCausada.empresa_id == args.empresa)
        filas = db.scalars(stmt).all()

        n_sin_datos = db.scalar(
            select(func.count()).select_from(FacturaCausada).where(
                FacturaCausada.tipo_causacion.is_(None),
                FacturaCausada.datos_json.is_(None),
            )
        )

        cambios: list[tuple[FacturaCausada, str]] = []
        errores = 0
        for fc in filas:
            try:
                datos = json.loads(fc.datos_json)  # type: ignore[arg-type]
                factura = datos.get("factura") or {}
                es_venta = bool(datos.get("es_venta", False))
            except Exception:
                errores += 1
                continue
            nuevo = derivar_tipo_causacion(factura, es_venta)
            cambios.append((fc, nuevo))

        print(f"Filas sin tipo_causacion CON datos_json : {len(filas)}")
        print(f"  - clasificables                       : {len(cambios)}")
        print(f"  - con datos_json ilegible              : {errores}")
        if n_sin_datos:
            print(f"  (además {n_sin_datos} fila(s) sin datos_json en absoluto — no se pueden clasificar y quedan igual)")

        # Resumen por tipo derivado
        conteo_tipos: dict[str, int] = {}
        for _fc, tipo in cambios:
            conteo_tipos[tipo] = conteo_tipos.get(tipo, 0) + 1
        for tipo, n in sorted(conteo_tipos.items()):
            print(f"    {tipo:12s}: {n}")

        print()
        for fc, tipo in cambios[:60]:
            print(f"  #{fc.id} {fc.numero_dian} ({fc.razon_social or ''}) -> {tipo}")
        if len(cambios) > 60:
            print(f"  ... y {len(cambios) - 60} más")

        if not args.apply:
            print("\nDRY RUN — no se escribió nada.")
            print("Para respaldar y aplicar: agrega --apply")
            return

        if not cambios:
            print("\nNada que actualizar.")
            return

        # ── Respaldo CSV ──
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = ruta_respaldo(f"backup_tipo_causacion_{ts}.csv")
        with open(backup_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "numero_dian", "tipo_causacion_old", "tipo_causacion_new"])
            for fc, tipo in cambios:
                w.writerow([fc.id, fc.numero_dian, fc.tipo_causacion, tipo])
        import os
        print(f"\nRespaldo escrito en: {os.path.abspath(backup_path)}")

        for fc, tipo in cambios:
            fc.tipo_causacion = tipo
        db.commit()
        print(f"Aplicados {len(cambios)} cambios. Listo.")


if __name__ == "__main__":
    main()
