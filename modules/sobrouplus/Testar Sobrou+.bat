@echo off
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% -X utf8 -m unittest discover -v tests > testes_resultado.txt 2>&1
type testes_resultado.txt
pause
