#!/usr/bin/env bash
# Corre las pruebas dentro del contenedor de la API (no ensucia tu Python local).
#
# Uso:
#   ./scripts/test.sh                  → todas las pruebas
#   ./scripts/test.sh -k exporter      → solo las que coincidan con "exporter"
#   ./scripts/test.sh -m contable      → solo las marcadas como contables
#   ./scripts/test.sh --cov=core       → con reporte de cobertura
#
# En Windows (Git Bash) puede hacer falta MSYS_NO_PATHCONV=1 delante.
set -euo pipefail

if ! docker compose ps --status running api >/dev/null 2>&1; then
  echo "El contenedor 'api' no está corriendo. Levantalo con: docker compose up -d"
  exit 1
fi

# pytest no va en la imagen de producción; se instala aquí (queda cacheado
# mientras el contenedor siga vivo, así que la primera corrida es la única lenta).
docker compose exec -T api sh -c "
  python -c 'import pytest' 2>/dev/null || pip install --quiet pytest pytest-cov
  cd /app && PYTHONPATH=/app python -m pytest $*
"
