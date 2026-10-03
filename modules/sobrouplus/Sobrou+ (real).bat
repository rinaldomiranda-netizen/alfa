@echo off
title Sobrou+ (real)
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% -X utf8 web\iniciar.py
echo.
echo O Sobrou+ parou. Se apareceu erro acima, tire um print.
pause
