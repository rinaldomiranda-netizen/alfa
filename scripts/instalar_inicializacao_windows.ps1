<#
    Instala o ALFA para iniciar automaticamente com o Windows.

    Método usado: atalho (.lnk) na pasta de Inicialização do USUÁRIO
    atual (shell:startup) apontando para scripts\iniciar_alfa_silencioso.vbs.

    É reversível: para desfazer, rode
    scripts\remover_inicializacao_windows.ps1 (ou apague o atalho
    "ALFA.lnk" da pasta de Inicialização manualmente).

    Este script NÃO roda sozinho — precisa ser executado
    explicitamente pelo usuário depois de validar que o ALFA
    (main.py) inicia e funciona corretamente de forma manual.
#>

$ErrorActionPreference = "Stop"

$base = Split-Path -Parent $PSScriptRoot
$vbs = Join-Path $base "scripts\iniciar_alfa_silencioso.vbs"

if (-not (Test-Path $vbs)) {
    Write-Error "Não encontrei $vbs. Rode este script a partir da pasta scripts\ do projeto ALFA."
    exit 1
}

$startupDir = [Environment]::GetFolderPath("Startup")
$atalho = Join-Path $startupDir "ALFA.lnk"

$wshShell = New-Object -ComObject WScript.Shell
$shortcut = $wshShell.CreateShortcut($atalho)
$shortcut.TargetPath = "wscript.exe"
$shortcut.Arguments = "`"$vbs`""
$shortcut.WorkingDirectory = $base
$shortcut.Description = "Inicia o assistente de voz ALFA junto com o Windows"
$shortcut.Save()

Write-Host "Atalho criado em: $atalho"
Write-Host "O ALFA será iniciado automaticamente no próximo login do Windows."
Write-Host "Para desativar, rode scripts\remover_inicializacao_windows.ps1"
