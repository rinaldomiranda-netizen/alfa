@echo off
title Sobrou+ (demonstracao)
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
echo Sobrou+ - DEMONSTRACAO (dados de exemplo, banco separado)
echo.
echo  1 - Cliente (app do celular)
echo  2 - Empresa parceira (administrador)
echo  3 - Balcao da empresa (operador)
echo  4 - Entregador
echo  5 - Equipe Sobrou+ (central)
echo  6 - Financeiro Sobrou+
echo  7 - Instituicao (doacoes)
echo.
set /p OP=Escolha o perfil e tecle ENTER: 
set PERFIL=cliente
if "%OP%"=="2" set PERFIL=admin_empresa
if "%OP%"=="3" set PERFIL=operador_empresa
if "%OP%"=="4" set PERFIL=entregador
if "%OP%"=="5" set PERFIL=admin_sobrou
if "%OP%"=="6" set PERFIL=financeiro
if "%OP%"=="7" set PERFIL=instituicao
%PY% -X utf8 web\laboratorio.py %PERFIL%
if errorlevel 1 pause
