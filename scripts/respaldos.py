"""
Dónde dejan su respaldo los scripts de backfill.

Escribirlo en el directorio de trabajo parecía bastar, pero no: el contenedor de
la API se recrea en cada "Pull and redeploy" de Portainer y se lleva todo lo que
no esté en un volumen. Un respaldo de producción se perdió así — sin consecuencias
porque el dato era recalculable, pero el respaldo existe justamente para cuando
NO lo es.

En producción el contenedor monta `api_data:/app/data`, que sobrevive a los
redespliegues. Se usa esa ruta cuando existe; si no (desarrollo local, o correr
el script fuera de Docker), se cae al directorio actual.
"""
from __future__ import annotations

import os

# Volumen persistente del contenedor de la API (ver docker-compose.hostinger.yml).
DIR_PERSISTENTE = "/app/data"


def ruta_respaldo(nombre_archivo: str) -> str:
    """Ruta completa donde escribir un respaldo, preferiendo el volumen."""
    if os.path.isdir(DIR_PERSISTENTE) and os.access(DIR_PERSISTENTE, os.W_OK):
        return os.path.join(DIR_PERSISTENTE, nombre_archivo)
    return nombre_archivo
