"""
Backfill de base_gravable en facturas_causadas ya guardadas.

La columna la agregó la migración 026 vacía. Las causaciones NUEVAS la llenan
solas; las anteriores quedan en NULL y la analítica cae al `total` (que incluye
IVA), lo que infla costos e ingresos. Este script las completa a partir de
`datos_json`, sumando la base de cada ítem — la MISMA cuenta que hace el backend
al causar (services.causacion_service.base_gravable_de).

Solo hace UPDATE de base_gravable, y solo en filas que hoy están en NULL. NUNCA
borra filas ni sobrescribe un valor existente. Los registros sin datos_json (de
antes de que se guardara ese detalle) no se pueden calcular y quedan igual: la
analítica seguirá usando su total, que es lo mejor disponible.

Uso:
    # 1) Identificar (no escribe nada):
    python scripts/backfill_base_gravable.py

    # 2) Respaldar a CSV y aplicar los cambios:
    python scripts/backfill_base_gravable.py --apply

En Docker (recordar PYTHONPATH=/app):
    PYTHONPATH=/app python scripts/backfill_base_gravable.py
    PYTHONPATH=/app python scripts/backfill_base_gravable.py --apply
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime

from sqlalchemy import func, select

from db.session import SessionLocal, DATABASE_URL
from db.models.contabilidad import FacturaCausada
from services.causacion_service import base_gravable_de


def main() -> None:
    ap = argparse.ArgumentParser(description="Completa base_gravable en facturas_causadas.")
    ap.add_argument("--apply", action="store_true", help="Aplica los cambios (por defecto solo informa).")
    args = ap.parse_args()

    print(f"Base de datos: {DATABASE_URL.rsplit('@', 1)[-1]}")
    print("Modo: APLICAR\n" if args.apply else "Modo: SOLO INFORMAR (usá --apply para escribir)\n")

    db = SessionLocal()
    try:
        pendientes = db.scalar(
            select(func.count(FacturaCausada.id)).where(FacturaCausada.base_gravable.is_(None))
        ) or 0
        print(f"Causaciones sin base gravable: {pendientes}")
        if pendientes == 0:
            print("Nada que hacer.")
            return

        filas = db.execute(
            select(FacturaCausada.id, FacturaCausada.numero_dian,
                   FacturaCausada.total, FacturaCausada.datos_json)
            .where(FacturaCausada.base_gravable.is_(None))
        ).all()

        calculadas: list[tuple[int, str, float, float]] = []
        sin_datos = 0
        for fc_id, numero, total, datos in filas:
            if not datos:
                sin_datos += 1
                continue
            try:
                factura = json.loads(datos).get("factura", {})
            except (ValueError, AttributeError):
                sin_datos += 1
                continue
            base = base_gravable_de(factura)
            if base is None:
                sin_datos += 1
                continue
            calculadas.append((fc_id, numero, float(total or 0), base))

        print(f"Se pueden calcular: {len(calculadas)}")
        if sin_datos:
            print(f"Sin detalle guardado, quedan igual: {sin_datos}")

        if calculadas:
            suma_total = sum(t for _, _, t, _ in calculadas)
            suma_base = sum(b for _, _, _, b in calculadas)
            print(f"\nSuma de totales (con IVA): {suma_total:>18,.2f}")
            print(f"Suma de bases  (sin IVA): {suma_base:>18,.2f}")
            print(f"Diferencia (IVA y otros): {suma_total - suma_base:>18,.2f}")
            print("\nPrimeros 10:")
            print(f"{'FACTURA':<26} {'TOTAL':>16} {'BASE':>16}")
            print("-" * 60)
            for _, numero, total, base in calculadas[:10]:
                print(f"{(numero or '')[:25]:<26} {total:>16,.2f} {base:>16,.2f}")

        if not args.apply:
            print("\nNo se escribió nada. Volvé a correrlo con --apply para aplicar.")
            return

        sello = datetime.now().strftime("%Y%m%d_%H%M%S")
        respaldo = f"backfill_base_gravable_{sello}.csv"
        with open(respaldo, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["factura_causada_id", "numero_dian", "total", "base_gravable_nueva"])
            w.writerows(calculadas)
        print(f"\nRespaldo escrito en: {respaldo} ({len(calculadas)} filas)")

        for fc_id, _, _, base in calculadas:
            db.query(FacturaCausada).filter(FacturaCausada.id == fc_id).update(
                {"base_gravable": base}, synchronize_session=False
            )
        db.commit()
        print(f"Listo: {len(calculadas)} causaciones actualizadas.")

        restantes = db.scalar(
            select(func.count(FacturaCausada.id)).where(FacturaCausada.base_gravable.is_(None))
        ) or 0
        print(f"Quedan sin base (usarán su total): {restantes}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
