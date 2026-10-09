@echo off
title Sobrou+ (PRODUCAO)
cd /d "%~dp0"
set "SOBROU_AMBIENTE=producao"
set "SOBROU_DADOS=%~dp0data"
set "SOBROU_PORTA=8095"
set "SOBROU_ATRAS_DE_PROXY=1"
set "SOBROU_URL_PUBLICA=https://maze-spider.runlocal.eu"
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
%PY% -X utf8 web\iniciar.py
echo.
echo O Sobrou+ parou. Se apareceu erro acima, tire um print.
pause
