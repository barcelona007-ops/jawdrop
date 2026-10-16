@echo off
rem Deja los precios de Jawdrop frescos sin abrir la pagina (gratis: Ryanair, Wizz y Kiwi).
rem Pensado para el Programador de tareas de Windows (una vez al dia, por la manana).
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
.venv\Scripts\python.exe actualizar.py >> actualizar_log.txt 2>&1
rem Contrasta en segundo plano las mejores opciones con Google Flights (SerpApi): max 12 busquedas por dia, nunca baja de 50 libres.
.venv\Scripts\python.exe auditor.py >> auditor_log.txt 2>&1
rem Sube la pantalla del iPhone con los precios nuevos a Cloudflare (sin consultar nada).
.venv\Scripts\python.exe publicar_movil.py --subir >> actualizar_log.txt 2>&1
