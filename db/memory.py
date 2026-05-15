"""
Módulo de memoria persistente usando SQLite.
Guarda: consecutivos, facturas causadas, mapeos aprendidos NIT+keyword→PUC.
"""

import sqlite3
import os
from datetime import date

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "siigo_memory.db")


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(os.path.abspath(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Crea las tablas si no existen."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS consecutivos (
                prefijo     TEXT PRIMARY KEY,
                ultimo_num  INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS facturas_causadas (
                numero_dian     TEXT PRIMARY KEY,
                nit_proveedor   TEXT,
                razon_social    TEXT,
                fecha_factura   TEXT,
                total           REAL,
                consecutivo     TEXT,
                fecha_causacion TEXT
            );

            CREATE TABLE IF NOT EXISTS mapeos_puc (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nit         TEXT,
                keyword     TEXT,
                cuenta_puc  TEXT NOT NULL,
                descripcion TEXT,
                usos        INTEGER DEFAULT 1,
                ultima_vez  TEXT
            );

            CREATE TABLE IF NOT EXISTS proveedores (
                nit             TEXT PRIMARY KEY,
                razon_social    TEXT,
                tipo            TEXT,
                regimen         TEXT,
                cuenta_pagar    TEXT
            );
        """)


# ── Consecutivos ──────────────────────────────────────────────────────────────

def get_ultimo_consecutivo(prefijo: str) -> int:
    """Retorna el último número usado para el prefijo dado. 0 si no hay historial."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT ultimo_num FROM consecutivos WHERE prefijo = ?", (prefijo.upper(),)
        ).fetchone()
    return row["ultimo_num"] if row else 0


def set_ultimo_consecutivo(prefijo: str, numero: int) -> None:
    """Actualiza (o inserta) el último consecutivo usado."""
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO consecutivos (prefijo, ultimo_num)
               VALUES (?, ?)
               ON CONFLICT(prefijo) DO UPDATE SET ultimo_num = excluded.ultimo_num""",
            (prefijo.upper(), numero),
        )


def siguiente_consecutivo(prefijo: str) -> tuple[str, int]:
    """
    Devuelve (consecutivo_formateado, numero_entero) para el próximo comprobante.
    Ejemplo: ('CE-00246', 246)
    No lo persiste todavía — llamar a set_ultimo_consecutivo al confirmar.
    """
    siguiente = get_ultimo_consecutivo(prefijo) + 1
    etiqueta = f"{prefijo.upper()}-{str(siguiente).zfill(5)}"
    return etiqueta, siguiente


# ── Facturas causadas ─────────────────────────────────────────────────────────

def factura_ya_causada(numero_dian: str) -> bool:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM facturas_causadas WHERE numero_dian = ?", (numero_dian,)
        ).fetchone()
    return row is not None


def registrar_factura(
    numero_dian: str,
    nit_proveedor: str,
    razon_social: str,
    fecha_factura: str,
    total: float,
    consecutivo: str,
) -> None:
    with _get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO facturas_causadas
               (numero_dian, nit_proveedor, razon_social, fecha_factura, total, consecutivo, fecha_causacion)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                numero_dian,
                nit_proveedor,
                razon_social,
                fecha_factura,
                total,
                consecutivo,
                date.today().isoformat(),
            ),
        )


def listar_facturas_causadas() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM facturas_causadas ORDER BY fecha_causacion DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Mapeos PUC aprendidos ─────────────────────────────────────────────────────

def buscar_mapeo_puc(nit: str, descripcion: str) -> str | None:
    """
    Busca en el historial de mapeos aprendidos.
    Estrategia: primero busca por NIT + keyword exacto; luego solo por keyword.
    Retorna el código PUC más frecuentemente usado, o None si no hay historial.
    """
    keywords = _extraer_keywords(descripcion)
    with _get_conn() as conn:
        for kw in keywords:
            row = conn.execute(
                """SELECT cuenta_puc FROM mapeos_puc
                   WHERE nit = ? AND keyword = ?
                   ORDER BY usos DESC LIMIT 1""",
                (nit, kw),
            ).fetchone()
            if row:
                return row["cuenta_puc"]
        # Segundo intento: solo keyword sin NIT
        for kw in keywords:
            row = conn.execute(
                """SELECT cuenta_puc FROM mapeos_puc
                   WHERE keyword = ?
                   ORDER BY usos DESC LIMIT 1""",
                (kw,),
            ).fetchone()
            if row:
                return row["cuenta_puc"]
    return None


def guardar_mapeo_puc(nit: str, descripcion: str, cuenta_puc: str) -> None:
    """Guarda o actualiza el mapeo aprendido para NIT + cada keyword de la descripción."""
    keywords = _extraer_keywords(descripcion)
    with _get_conn() as conn:
        for kw in keywords:
            existing = conn.execute(
                "SELECT id, usos FROM mapeos_puc WHERE nit = ? AND keyword = ? AND cuenta_puc = ?",
                (nit, kw, cuenta_puc),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE mapeos_puc SET usos = usos + 1, ultima_vez = ? WHERE id = ?",
                    (date.today().isoformat(), existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO mapeos_puc (nit, keyword, cuenta_puc, descripcion, usos, ultima_vez)
                       VALUES (?, ?, ?, ?, 1, ?)""",
                    (nit, kw, cuenta_puc, descripcion, date.today().isoformat()),
                )


def _extraer_keywords(texto: str) -> list[str]:
    """Extrae palabras clave significativas de una descripción."""
    STOP = {
        "de", "la", "el", "en", "y", "a", "por", "con", "del", "los", "las",
        "un", "una", "para", "al", "se", "su", "que", "es", "lo", "no",
    }
    palabras = texto.lower().split()
    return list({p for p in palabras if len(p) > 3 and p not in STOP})


# ── Proveedores ───────────────────────────────────────────────────────────────

def get_proveedor(nit: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM proveedores WHERE nit = ?", (nit,)
        ).fetchone()
    return dict(row) if row else None


def guardar_proveedor(nit: str, razon_social: str, tipo: str, regimen: str, cuenta_pagar: str) -> None:
    with _get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO proveedores (nit, razon_social, tipo, regimen, cuenta_pagar)
               VALUES (?, ?, ?, ?, ?)""",
            (nit, razon_social, tipo, regimen, cuenta_pagar),
        )
