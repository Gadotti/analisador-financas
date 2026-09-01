@echo off
REM Abre a interface web da carteira no navegador.
cd /d "%~dp0"
python server.py %*
pause
