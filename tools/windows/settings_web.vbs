' dafeiyu settings (web page on localhost)
' This file lives in <root>/tools/windows/ -- walk up to the project root.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)   ' <root>\tools\windows
here = fso.GetParentFolderName(here)                     ' <root>\tools
here = fso.GetParentFolderName(here)                     ' <root>
sh.CurrentDirectory = here

' Use whatever Python 3 the machine has -- never hardcode a minor version.
py = ""
If sh.Run("cmd /c where py >nul 2>&1", 0, True) = 0 Then
  py = "py -3"
ElseIf sh.Run("cmd /c where pythonw >nul 2>&1", 0, True) = 0 Then
  py = "pythonw"
ElseIf sh.Run("cmd /c where python >nul 2>&1", 0, True) = 0 Then
  py = "python"
Else
  MsgBox "Python 3.9+ not found." & vbCrLf & vbCrLf & _
         "Install it from https://www.python.org/downloads/ and tick" & vbCrLf & _
         "'Add python.exe to PATH' during setup.", 48, "dafeiyu"
  WScript.Quit 1
End If

sh.Run py & " """ & here & "\tools\settings_server.py""", 0, False
