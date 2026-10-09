@echo off
title Sobrou+ - DESENVOLVIMENTO
cd /d "%~dp0"
set "SOBROU_AMBIENTE=desenvolvimento"
set "SOBROU_DADOS=%~dp0data_desenvolvimento"
set "SOBROU_PORTA=8096"
set "SOBROU_ATRAS_DE_PROXY=0"
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
%PY% -X utf8 web\iniciar.py --sem-navegador
pause
