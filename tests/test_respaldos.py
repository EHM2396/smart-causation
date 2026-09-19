"""
Dónde caen los respaldos de los scripts de backfill.

Un respaldo escrito en el directorio de trabajo del contenedor desaparece en el
siguiente "Pull and redeploy". Ya pasó en producción: el CSV del backfill de
base_gravable se perdió. No hubo daño porque el dato era recalculable, pero el
respaldo existe para los casos en que no lo es.
"""
from __future__ import annotations

import pytest

from scripts import respaldos

pytestmark = pytest.mark.respaldos


def test_usa_el_volumen_persistente_cuando_existe(tmp_path, monkeypatch):
    monkeypatch.setattr(respaldos, "DIR_PERSISTENTE", str(tmp_path))
    ruta = respaldos.ruta_respaldo("backfill_x_20260101.csv")
    assert ruta == str(tmp_path / "backfill_x_20260101.csv")


def test_cae_al_directorio_actual_si_no_hay_volumen(tmp_path, monkeypatch):
    """Fuera de Docker (o en local) el volumen no existe: no se debe fallar."""
    monkeypatch.setattr(respaldos, "DIR_PERSISTENTE", str(tmp_path / "no-existe"))
    assert respaldos.ruta_respaldo("backfill_x.csv") == "backfill_x.csv"


def test_cae_al_directorio_actual_si_el_volumen_no_es_escribible(tmp_path, monkeypatch):
    """Existir no alcanza: si no se puede escribir, mejor el directorio actual
    que reventar a mitad del backfill."""
    monkeypatch.setattr(respaldos, "DIR_PERSISTENTE", str(tmp_path))
    monkeypatch.setattr(respaldos.os, "access", lambda *_a, **_k: False)
    assert respaldos.ruta_respaldo("backfill_x.csv") == "backfill_x.csv"
