@echo off
rem Instala las dependencias (si faltan), crea los datos de la demo y abre el gestor.
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
if not exist "data\sample\Reporte_Ministerio_2026-03.xlsx" python scripts\generate_sample_data.py
if not exist "data\demo\usuarios.json" python scripts\generate_demo_data.py
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:5001"
echo Usuario: demo   Contrasena: gidep-demo
python -m gidep
