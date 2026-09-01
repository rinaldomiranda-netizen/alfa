<#
    Remove a inicialização automática do ALFA com o Windows,
    revertendo o que scripts\instalar_inicializacao_windows.ps1 fez.
#>

$startupDir = [Environment]::GetFolderPath("Startup")
$atalho = Join-Path $startupDir "ALFA.lnk"

if (Test-Path $atalho) {
    Remove-Item $atalho -Force
    Write-Host "Inicialização automática do ALFA removida."
} else {
    Write-Host "Nenhum atalho de inicialização do ALFA encontrado."
}
