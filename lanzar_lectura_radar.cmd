@echo off
rem Lector ÚNICO del Radar largo, por etapas (17-10-2026): 100 zona-meses, limpia la caché de Kiwi caducada, reconstruye la cuadrícula y repite. Para solo si C: baja de 500 MB libres. No lanzar dos a la vez.
cd /d C:\escapadas_flash
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
.venv\Scripts\python.exe lectura_por_etapas.py >> resultados\lectura_etapas_cmd.txt 2>&1
echo FIN %date% %time% >> resultados\lectura_etapas_cmd.txt
