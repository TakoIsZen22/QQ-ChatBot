Option Explicit
Dim shell, fs, projectRoot, pythonw
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
projectRoot = fs.GetParentFolderName(WScript.ScriptFullName)
If fs.FileExists(projectRoot & "\QQ ChatBot.exe") Then
    shell.CurrentDirectory = projectRoot
    shell.Run Chr(34) & projectRoot & "\QQ ChatBot.exe" & Chr(34), 0, False
    WScript.Quit 0
End If
pythonw = projectRoot & "\.venv\Scripts\pythonw.exe"
If Not fs.FileExists(pythonw) Then
    MsgBox "Please run tools\install.bat first.", 48, "QQ ChatBot"
    WScript.Quit 1
End If
shell.CurrentDirectory = projectRoot
shell.Run Chr(34) & pythonw & Chr(34) & " -m src.desktop", 0, False
