@echo off
title Reiniciar Sobrou+
cd /d "%~dp0"
echo Fechando o Sobrou+ antigo (os dados ficam guardados)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8095" ^| findstr "LISTENING"') do taskkill /PID %%p /F >nul 2>nul
ping -n 3 127.0.0.1 >nul
echo Ligando o Sobrou+ novo...
start "" "%~dp0Sobrou+ (real).bat"
ping -n 6 127.0.0.1 >nul
echo Pronto. Pode fechar esta janela.
ping -n 3 127.0.0.1 >nul
