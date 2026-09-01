@echo off
REM Roda a analise da carteira no terminal (script isolado em Python).
cd /d "%~dp0"
python scripts\analisar.py %*
pause
