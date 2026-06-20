#!/usr/bin/env bash
# ===========================================================================
# BETLAB AI - Script de instalación
# ===========================================================================
# Crea un entorno virtual, instala dependencias, inicializa la base de datos
# y (si no hay claves de API) siembra datos demo para probar el sistema.
# ===========================================================================
set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
VENV_DIR=".venv"

echo "==> 1/5  Creando entorno virtual ($VENV_DIR)..."
$PYTHON -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "==> 2/5  Actualizando pip e instalando dependencias..."
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo "==> 3/5  Preparando archivo de configuración (.env)..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo "    Creado .env (rellena tus claves de API si las tienes)."
else
  echo "    .env ya existe; se conserva."
fi

echo "==> 4/5  Inicializando base de datos SQLite..."
python main.py initdb

echo "==> 5/5  Sembrando datos demo (si no hay claves de API)..."
if grep -qE '^(API_FOOTBALL_KEY|ODDS_API_KEY)=.+' .env; then
  echo "    Claves detectadas; omito datos demo. Ejecuta: python main.py pipeline"
else
  python main.py demo
  python main.py value
fi

cat <<'EOF'

===========================================================================
 ✔ BETLAB AI instalado.

 Activa el entorno:        source .venv/bin/activate
 Pipeline completo:        python main.py pipeline
 Lanzar dashboard:         streamlit run dashboard/app.py
 Reporte diario HTML:      python main.py report  ->  reports/reporte_diario.html
===========================================================================
EOF
