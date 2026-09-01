@echo off
REM Abre a interface web da carteira no navegador.
cd /d "%~dp0"
node src\server\index.js %*
pause
