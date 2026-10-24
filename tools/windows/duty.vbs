' duty runner -- called by the system scheduler, hidden window, one round.
' Arg = which driver: claude | zcode | opencode | codex | gemini | api (default)
' This file lives in <root>/tools/windows/ -- walk up to the project root.
' Pure ASCII on purpose: WSH decodes BOM-less files as the system ANSI codepage,
' so any non-ASCII literal here would arrive at the agent as mojibake.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)   ' <root>\tools\windows
here = fso.GetParentFolderName(here)                     ' <root>\tools
here = fso.GetParentFolderName(here)                     ' <root>
sh.CurrentDirectory = here

drv = "api"
If WScript.Arguments.Count > 0 Then drv = WScript.Arguments(0)

prompt = "Follow duty.md and automation-prompt.txt and run one duty round."

Select Case drv
  Case "claude"   cmd = "claude -p """ & prompt & """"
  Case "zcode"    cmd = "zcode -p """ & prompt & """"
  Case "opencode" cmd = "opencode run """ & prompt & """"
  Case "codex"    cmd = "codex exec """ & prompt & """"
  Case "gemini"   cmd = "gemini -p """ & prompt & """"
  Case Else
    ' Use whatever Python 3 the machine has -- never hardcode a minor version.
    py = ""
    If sh.Run("cmd /c where py >nul 2>&1", 0, True) = 0 Then
      py = "py -3"
    ElseIf sh.Run("cmd /c where pythonw >nul 2>&1", 0, True) = 0 Then
      py = "pythonw"
    ElseIf sh.Run("cmd /c where python >nul 2>&1", 0, True) = 0 Then
      py = "python"
    Else
      WScript.Quit 1
    End If
    cmd = py & " tools\api_runner.py"
End Select

sh.Run "cmd /c " & cmd, 0, False
