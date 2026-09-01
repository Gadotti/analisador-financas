@echo off
REM Roda a analise da carteira no terminal.
cd /d "%~dp0"
python run_analysis.py %*
pause
