@echo off
rem Instala las dependencias (si faltan), crea los datos de ejemplo y abre la app.
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
if not exist "data\sample\Reporte_Ministerio_2026-03.xlsx" python scripts\generate_sample_data.py
start "" http://127.0.0.1:5001
python -m conciliacion.app
