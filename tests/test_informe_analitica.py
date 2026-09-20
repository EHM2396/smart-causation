"""
El informe de analítica en Excel.

Se envía fuera de Ciolix, así que un error acá llega directo a un cliente o a la
DIAN. Lo que más importa es el SIGNO: en el detalle, una nota crédito tiene que
leerse en negativo — si apareciera sumando, el archivo diría lo contrario que la
pantalla que lo generó.
"""
from __future__ import annotations

import pytest

from services import analitica_service, informe_analitica_service

pytestmark = pytest.mark.informe


def test_los_colores_son_los_de_la_plataforma():
    """La marca del archivo tiene que coincidir con la de la aplicación
    (--brand en globals.css); si alguien cambia una sola, se nota acá."""
    assert informe_analitica_service.MARCA == "#4F46E5"


def test_el_detalle_usa_el_mismo_signo_que_el_informe():
    """El Excel lee el signo de analitica_service, no de una copia propia: así
    no puede contradecir a la pantalla."""
    assert analitica_service.SIGNO["nc"] == -1
    assert analitica_service.SIGNO["nc_ventas"] == -1
    assert analitica_service.SIGNO["nd"] == 1
    assert analitica_service.SIGNO["compras"] == 1


def test_toda_etiqueta_del_informe_existe():
    """El Excel nombra los documentos con ETIQUETA; un tipo sin etiqueta saldría
    con su nombre interno ('nc_soporte') en un archivo que ve un cliente."""
    for tipo in analitica_service.SIGNO:
        assert tipo in analitica_service.ETIQUETA, f"{tipo} saldría sin nombre legible"


@pytest.mark.parametrize("nombre", ["Resumen", "Documentos", "Items"])
def test_el_informe_declara_sus_tres_hojas(nombre):
    """Resumen para leer, Documentos para revisar, Items para el análisis
    tributario. Si se quita una, algo que alguien usaba dejó de estar."""
    import inspect
    fuente = inspect.getsource(informe_analitica_service)
    assert f'add_worksheet("{nombre}")' in fuente
