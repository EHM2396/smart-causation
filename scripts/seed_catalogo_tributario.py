"""
Carga el catálogo tributario semilla desde el CSV de productos y servicios.

Entra TODO como `sugerida`, nunca como `validada`. El CSV se armó con fuentes
web secundarias, no leyendo el Estatuto Tributario: darle el peso de una
clasificación validada sería atribuirle una autoridad que no tiene. Queda como
punto de partida para que el contador confirme o corrija, con su fuente anotada
para que se vea de dónde salió cada fila.

Se carga con `cuenta_id = NULL`: es la semilla del sistema, visible para todas
las firmas. Cada firma puede después crear sus propias entradas, que pesan más
que la semilla cuando ambas existen.

Uso:
    # 1) Ver qué se cargaría (no escribe nada):
    python scripts/seed_catalogo_tributario.py

    # 2) Cargar:
    python scripts/seed_catalogo_tributario.py --apply

    # Otro archivo:
    python scripts/seed_catalogo_tributario.py --apply --csv otro.csv

En Docker (recordar PYTHONPATH=/app):
    PYTHONPATH=/app python scripts/seed_catalogo_tributario.py
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from sqlalchemy import select

from db.session import SessionLocal, DATABASE_URL
from db.models.tributario import CatalogoTributario
from services.catalogo_tributario_service import normalizar_concepto, registrar_cambio

CSV_POR_DEFECTO = "ID-ProductoServicio-Categora-TratamientoIVA-Artcul.csv"

# El CSV dice "Excluido", "Exento (0%)", "Gravado (19%)"... y el motor maneja
# códigos. Se traduce acá, y lo que no se reconoce NO se adivina: se informa.
_TRATAMIENTO = {
    "excluido": "excluido",
    "exento": "exento",
    "exento (0%)": "exento",
    "gravado (19%)": "gravado_general",
    "gravado (5%)": "gravado_5",
    "no gravado": "no_gravado",
}


def _traducir(valor: str) -> str | None:
    v = (valor or "").strip().lower()
    if v in _TRATAMIENTO:
        return _TRATAMIENTO[v]
    # "Gravado (19%)" con variantes de espaciado o mayúsculas
    if v.startswith("exento"):
        return "exento"
    if v.startswith("excluido"):
        return "excluido"
    if "19" in v and v.startswith("gravado"):
        return "gravado_general"
    if "5" in v and v.startswith("gravado"):
        return "gravado_5"
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Carga el catálogo tributario semilla.")
    ap.add_argument("--apply", action="store_true", help="Escribe (por defecto solo informa).")
    ap.add_argument("--csv", default=CSV_POR_DEFECTO, help="Ruta del CSV.")
    args = ap.parse_args()

    ruta = Path(args.csv)
    if not ruta.exists():
        print(f"No se encontró el archivo: {ruta}")
        return

    print(f"Base de datos: {DATABASE_URL.rsplit('@', 1)[-1]}")
    print(f"Archivo: {ruta}")
    print("Modo: APLICAR\n" if args.apply else "Modo: SOLO INFORMAR (usá --apply para cargar)\n")

    with ruta.open(encoding="utf-8-sig", newline="") as fh:
        filas = list(csv.DictReader(fh))

    db = SessionLocal()
    try:
        nuevos, existentes, sin_traducir = [], 0, []

        for fila in filas:
            concepto = (fila.get("Producto / Servicio") or "").strip()
            if not concepto:
                continue
            tratamiento = _traducir(fila.get("Tratamiento IVA", ""))
            if tratamiento is None:
                sin_traducir.append((concepto, fila.get("Tratamiento IVA", "")))
                continue

            norm = normalizar_concepto(concepto)
            ya = db.scalar(
                select(CatalogoTributario).where(
                    CatalogoTributario.concepto_norm == norm,
                    CatalogoTributario.cuenta_id.is_(None),
                )
            )
            if ya is not None:
                existentes += 1
                continue

            nuevos.append({
                "concepto": concepto,
                "concepto_norm": norm,
                "categoria": (fila.get("Categoría") or "").strip() or None,
                "tratamiento": tratamiento,
                "articulo_et": (fila.get("Artículo(s) ET") or "").strip() or None,
                "fuente_normativa": (fila.get("Fuente") or "").strip() or None,
                "observaciones": (fila.get("Observaciones clave") or "").strip() or None,
            })

        print(f"Filas en el archivo : {len(filas)}")
        print(f"Se cargarían        : {len(nuevos)}")
        print(f"Ya estaban          : {existentes}")
        if sin_traducir:
            print(f"Tratamiento no reconocido (NO se cargan): {len(sin_traducir)}")
            for concepto, valor in sin_traducir:
                print(f"  · {concepto[:60]:<62} → '{valor}'")

        if nuevos:
            print(f"\n{'CONCEPTO':<52} {'TRATAMIENTO':<18} {'ART.'}")
            print("-" * 84)
            for n in nuevos[:12]:
                print(f"{n['concepto'][:51]:<52} {n['tratamiento']:<18} {n['articulo_et'] or '—'}")
            if len(nuevos) > 12:
                print(f"... y {len(nuevos) - 12} más")

        if not args.apply:
            print("\nNo se escribió nada. Volvé a correrlo con --apply para cargar.")
            return

        for datos in nuevos:
            entrada = CatalogoTributario(
                cuenta_id=None,          # semilla del sistema
                estado="sugerida",       # NUNCA validada: el CSV no es fuente jurídica
                **datos,
            )
            db.add(entrada)
            db.flush()
            registrar_cambio(
                db, catalogo=entrada, usuario_id=None, accion="creada",
                detalle="Semilla del catálogo cargada desde CSV — requiere validación del contador",
                norma=datos.get("fuente_normativa"),
            )
        db.commit()
        print(f"\nListo: {len(nuevos)} conceptos cargados como SUGERIDOS.")
        print("Ninguno queda validado: el contador confirma o corrige cada uno al usarlo.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
