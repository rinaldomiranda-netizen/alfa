' Inicia o ALFA em segundo plano (sem janela de console), usando o
' Python do ambiente virtual do projeto.
'
' Usado pelo atalho de inicialização automática do Windows
' (scripts\instalar_inicializacao_windows.ps1). Não é executado
' automaticamente até que esse instalador seja rodado manualmente.

Dim shell, base, pythonw, script

Set shell = CreateObject("WScript.Shell")
base = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\scripts\") - 1)

pythonw = """" & base & "\.venv311\Scripts\pythonw.exe"""
script = """" & base & "\main.py"""

shell.CurrentDirectory = base
shell.Run pythonw & " " & script, 0, False
