@echo off
rem Abre Jawdrop: arranca el servidor local y abre la pagina en el navegador.
cd /d "%~dp0"
.venv\Scripts\python.exe servidor.py
pause
