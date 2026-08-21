"""
Backfill de proveedores (terceros) ya guardados.

Corrige registros previos usando EXACTAMENTE la misma lógica que ya aplica el
backend al causar/guardar una factura, así el resultado es idéntico a las nuevas
extracciones:

  * Teléfono: quita pipes, indicativos sueltos y código de país 57.
              (services.terceros_service._phone -> core.parser._limpiar_telefono)
  * Códigos geo SIIGO (departamento / ciudad): resuelve por nombre normalizado,
    tolerante a acentos/puntuación y variantes de Bogotá D.C.
              (services.terceros_service._resolver_geo)

Solo hace UPDATE de telefono / codigo_departamento / codigo_ciudad_siigo.
NUNCA borra filas ni pone en NULL un código que ya estuviera (solo actualiza
cuando resuelve un valor nuevo distinto al actual).

Uso:
    # 1) Identificar (no escribe nada):
    python scripts/backfill_terceros.py

    # 2) Respaldar a CSV y aplicar los cambios:
    python scripts/backfill_terceros.py --apply

    # Opcional: acotar a una empresa
    python scripts/backfill_terceros.py --apply --empresa 3

En Docker:
    docker exec -it siigo_api python scripts/backfill_terceros.py
    docker exec -it siigo_api python scripts/backfill_terceros.py --apply
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime

from sqlalchemy import select

from db.session import SessionLocal, DATABASE_URL
from db.models.contabilidad import Proveedor
from services.terceros_service import _phone, _resolver_geo


def _db_resumen(url: str) -> str:
    """Muestra host/base sin exponer credenciales, para confirmar contra qué BD corre."""
    try:
        cuerpo = url.split("@", 1)[1] if "@" in url else url
        return cuerpo
    except Exception:
        return "(desconocida)"


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill teléfono + geo de proveedores")
    parser.add_argument("--apply", action="store_true", help="Aplica los cambios (por defecto: solo reporta)")
    parser.add_argument("--empresa", type=int, default=None, help="Filtrar por empresa_id")
    args = parser.parse_args()

    print(f"Base de datos objetivo: {_db_resumen(DATABASE_URL)}")
    print(f"Modo: {'APLICAR CAMBIOS' if args.apply else 'DRY RUN (solo reporte)'}\n")

    with SessionLocal() as db:
        stmt = select(Proveedor)
        if args.empresa is not None:
            stmt = stmt.where(Proveedor.empresa_id == args.empresa)
        proveedores = db.scalars(stmt).all()

        cambios: list[tuple[Proveedor, dict]] = []
        for p in proveedores:
            f: dict = {}

            # ── Teléfono ──
            tel_nuevo = _phone(p.telefono)
            if tel_nuevo is not None and tel_nuevo != p.telefono:
                f["telefono_old"] = p.telefono
                f["telefono_new"] = tel_nuevo

            # ── Códigos geo (solo si resuelve y cambia; no borra lo existente) ──
            cod_depto, cod_ciudad = _resolver_geo(db, p.ciudad, p.departamento, p.codigo_pais or "Col")
            if cod_depto is not None and cod_depto != p.codigo_departamento:
                f["codigo_departamento_old"] = p.codigo_departamento
                f["codigo_departamento_new"] = cod_depto
            if cod_ciudad is not None and cod_ciudad != p.codigo_ciudad_siigo:
                f["codigo_ciudad_siigo_old"] = p.codigo_ciudad_siigo
                f["codigo_ciudad_siigo_new"] = cod_ciudad

            if f:
                cambios.append((p, f))

        # ── Reporte ──
        tel_n = sum(1 for _, f in cambios if "telefono_new" in f)
        depto_n = sum(1 for _, f in cambios if "codigo_departamento_new" in f)
        ciudad_n = sum(1 for _, f in cambios if "codigo_ciudad_siigo_new" in f)

        print(f"Proveedores revisados : {len(proveedores)}")
        print(f"Con cambios           : {len(cambios)}")
        print(f"  - teléfono          : {tel_n}")
        print(f"  - código depto      : {depto_n}")
        print(f"  - código ciudad     : {ciudad_n}\n")

        for p, f in cambios[:60]:
            partes = []
            if "telefono_new" in f:
                partes.append(f"tel {f['telefono_old']!r} -> {f['telefono_new']!r}")
            if "codigo_departamento_new" in f:
                partes.append(f"depto {f['codigo_departamento_old']!r} -> {f['codigo_departamento_new']!r}")
            if "codigo_ciudad_siigo_new" in f:
                partes.append(f"ciudad {f['codigo_ciudad_siigo_old']!r} -> {f['codigo_ciudad_siigo_new']!r}")
            print(f"  #{p.id} {p.nit} {(p.razon_social or '')[:30]:30} | " + "; ".join(partes))
        if len(cambios) > 60:
            print(f"  ... y {len(cambios) - 60} más")

        if not args.apply:
            print("\nDRY RUN — no se escribió nada.")
            print("Para respaldar y aplicar: agrega --apply")
            return

        if not cambios:
            print("\nNada que actualizar.")
            return

        # ── Respaldo CSV (valores ACTUALES de las filas que cambiarán) ──
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"backup_proveedores_{ts}.csv"
        with open(backup_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "nit", "telefono", "ciudad", "departamento",
                        "codigo_departamento", "codigo_ciudad_siigo"])
            for p, _f in cambios:
                w.writerow([p.id, p.nit, p.telefono, p.ciudad, p.departamento,
                            p.codigo_departamento, p.codigo_ciudad_siigo])
        import os
        print(f"\nRespaldo escrito en: {os.path.abspath(backup_path)}")

        # ── Aplicar ──
        for p, f in cambios:
            if "telefono_new" in f:
                p.telefono = f["telefono_new"]
            if "codigo_departamento_new" in f:
                p.codigo_departamento = f["codigo_departamento_new"]
            if "codigo_ciudad_siigo_new" in f:
                p.codigo_ciudad_siigo = f["codigo_ciudad_siigo_new"]
        db.commit()
        print(f"Aplicados {len(cambios)} cambios. Listo.")


if __name__ == "__main__":
    main()
