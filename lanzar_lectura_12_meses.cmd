@echo off
rem Espera a que termine el lector de 6 meses (lectura_por_etapas.py sin argumentos) y sigue con los 12 meses. Solo lee; no sube nada. No lanzar dos lectores a la vez.
cd /d C:\escapadas_flash
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
:espera
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*lectura_por_etapas.py*' }) { exit 1 } else { exit 0 }"
if errorlevel 1 (
  timeout /t 120 /nobreak >nul
  goto espera
)
.venv\Scripts\python.exe lectura_por_etapas.py 12 12 >> resultados\lectura_etapas_cmd.txt 2>&1
echo FIN 12 meses %date% %time% >> resultados\lectura_etapas_cmd.txt
