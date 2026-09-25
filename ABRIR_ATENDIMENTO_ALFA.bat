@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
    py -3 -m ui.atendimento_app
) else (
    python -m ui.atendimento_app
)

if errorlevel 1 (
    echo.
    echo Nao foi possivel iniciar o RMD Atendimento dentro do ALFA.
    echo Verifique se o Python 3 esta instalado e as dependencias do projeto estao configuradas.
    pause
)
