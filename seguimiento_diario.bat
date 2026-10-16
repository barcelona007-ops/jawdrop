@echo off
rem Lee el precio de los vuelos de vigilados.txt, lo apunta en seguimiento_precios.csv y lo sube a git.
rem Pensado para el Programador de tareas de Windows (una vez al dia).
cd /d "%~dp0"
.venv\Scripts\python.exe seguimiento.py --subir >> seguimiento_log.txt 2>&1
