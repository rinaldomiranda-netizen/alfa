' Abre o RMD Atendimento Church SEM janela de console (servidor oculto) - Claude 16/10/2026
' O servidor se encerra sozinho quando a janela do sistema e fechada.
Option Explicit
Dim sh, fso, base, py, log
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
py = base & "\.venv311\Scripts\pythonw.exe"
If Not fso.FileExists(py) Then py = base & "\.venv311\Scripts\python.exe"
If Not fso.FolderExists(base & "\logs") Then fso.CreateFolder(base & "\logs")
log = base & "\logs\church_real.log"
sh.CurrentDirectory = base
sh.Run "cmd /c """"" & py & """ -X utf8 """ & base & "\atendimento_web\iniciar_church.py"" >> """ & log & """ 2>&1""", 0, False
