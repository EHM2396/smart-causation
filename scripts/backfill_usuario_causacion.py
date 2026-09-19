"""
Backfill de usuario_id en facturas_causadas ya guardadas.

La columna usuario_id (quién causó, para los informes del admin) la agregó la
migración 020 como columna nueva y vacía. Las causaciones NUEVAS sí la llenan,
pero todas las anteriores quedaron en NULL: en el dashboard del admin se agrupan
bajo "Sin asignar" y no se puede abrir su detalle (no hay id al cual entrar).

Se completa a partir del dueño de la empresa (`empresas.owner_id`): cada empresa
pertenece a un único causador — el frontend lista las empresas del usuario justo
por ese campo — así que la atribución es la correcta.

Solo hace UPDATE de usuario_id, y solo en filas que hoy están en NULL.
NUNCA borra filas ni sobrescribe un usuario_id que ya tuviera valor. Las
causaciones de empresas sin dueño (owner_id NULL) no se pueden atribuir y quedan
igual — no se adivina.

Uso:
    # 1) Identificar (no escribe nada):
    python scripts/backfill_usuario_causacion.py

    # 2) Respaldar a CSV y aplicar los cambios:
    python scripts/backfill_usuario_causacion.py --apply

    # Opcional: acotar a una empresa
    python scripts/backfill_usuario_causacion.py --apply --empresa 3

En Docker (recordar PYTHONPATH=/app, si no `python scripts/x.py` no encuentra
el paquete db):
    PYTHONPATH=/app python scripts/backfill_usuario_causacion.py
    PYTHONPATH=/app python scripts/backfill_usuario_causacion.py --apply
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime

from sqlalchemy import func, select, update

from db.session import SessionLocal, DATABASE_URL
from db.models.auth import Empresa, Usuario
from db.models.contabilidad import FacturaCausada
from scripts.respaldos import ruta_respaldo


def main() -> None:
    ap = argparse.ArgumentParser(description="Completa usuario_id en facturas_causadas.")
    ap.add_argument("--apply", action="store_true", help="Aplica los cambios (por defecto solo informa).")
    ap.add_argument("--empresa", type=int, default=None, help="Limita el backfill a una empresa.")
    args = ap.parse_args()

    print(f"Base de datos: {DATABASE_URL.rsplit('@', 1)[-1]}")
    print("Modo: APLICAR\n" if args.apply else "Modo: SOLO INFORMAR (usá --apply para escribir)\n")

    db = SessionLocal()
    try:
        pendientes = db.scalar(
            select(func.count(FacturaCausada.id)).where(FacturaCausada.usuario_id.is_(None))
        ) or 0
        print(f"Causaciones sin usuario asignado: {pendientes}")
        if pendientes == 0:
            print("Nada que hacer.")
            return

        # Qué se completaría, agrupado por empresa y su dueño.
        cond = [FacturaCausada.usuario_id.is_(None)]
        if args.empresa is not None:
            cond.append(FacturaCausada.empresa_id == args.empresa)

        filas = db.execute(
            select(
                FacturaCausada.empresa_id, Empresa.nombre, Empresa.owner_id,
                Usuario.nombre, Usuario.email, func.count(FacturaCausada.id),
            )
            .outerjoin(Empresa, Empresa.id == FacturaCausada.empresa_id)
            .outerjoin(Usuario, Usuario.id == Empresa.owner_id)
            .where(*cond)
            .group_by(FacturaCausada.empresa_id, Empresa.nombre, Empresa.owner_id,
                      Usuario.nombre, Usuario.email)
            .order_by(func.count(FacturaCausada.id).desc())
        ).all()

        print(f"\n{'EMPRESA':<32} {'SE ASIGNA A':<34} {'CAUSACIONES':>11}")
        print("-" * 80)
        asignables = huerfanas = 0
        for emp_id, emp_nom, owner_id, u_nom, u_mail, n in filas:
            if owner_id is None:
                destino, huerfanas = "— sin dueño, NO se toca —", huerfanas + n
            else:
                destino, asignables = f"{u_nom or u_mail} (id {owner_id})", asignables + n
            print(f"{(emp_nom or f'id {emp_id}')[:31]:<32} {destino[:33]:<34} {n:>11}")

        print("-" * 80)
        print(f"Se completarían: {asignables}")
        if huerfanas:
            print(f"Quedan sin asignar (empresa sin dueño): {huerfanas}")

        if not args.apply:
            print("\nNo se escribió nada. Volvé a correrlo con --apply para aplicar.")
            return

        # Respaldo del estado previo antes de tocar nada.
        sello = datetime.now().strftime("%Y%m%d_%H%M%S")
        respaldo = ruta_respaldo(f"backfill_usuario_causacion_{sello}.csv")
        a_tocar = db.execute(
            select(FacturaCausada.id, FacturaCausada.empresa_id, Empresa.owner_id)
            .join(Empresa, Empresa.id == FacturaCausada.empresa_id)
            .where(*cond, Empresa.owner_id.is_not(None))
        ).all()
        with open(respaldo, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["factura_causada_id", "empresa_id", "usuario_id_anterior", "usuario_id_nuevo"])
            for fc_id, emp_id, owner_id in a_tocar:
                w.writerow([fc_id, emp_id, "", owner_id])
        print(f"\nRespaldo escrito en: {respaldo} ({len(a_tocar)} filas)")

        # Un solo UPDATE correlacionado: usuario_id = dueño de su empresa.
        sub = select(Empresa.owner_id).where(Empresa.id == FacturaCausada.empresa_id).scalar_subquery()
        res = db.execute(
            update(FacturaCausada)
            .where(*cond, sub.is_not(None))
            .values(usuario_id=sub)
        )
        db.commit()
        print(f"Listo: {res.rowcount} causaciones actualizadas.")

        restantes = db.scalar(
            select(func.count(FacturaCausada.id)).where(FacturaCausada.usuario_id.is_(None))
        ) or 0
        print(f"Quedan sin usuario: {restantes}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
