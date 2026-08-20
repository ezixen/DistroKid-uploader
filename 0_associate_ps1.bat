@echo off
setlocal EnableExtensions
title Bandcamp Uploader - associate .ps1 with Windows PowerShell

echo.
echo === Associate .ps1 with Windows PowerShell (current user) ===
echo No prompts for which PowerShell — always the built-in one:
echo   %%SystemRoot%%\System32\WindowsPowerShell\v1.0\powershell.exe
echo.

set "PSEXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

if not exist "%PSEXE%" (
  echo ERROR: Windows PowerShell not found at:
  echo   %PSEXE%
  echo This should exist on every normal Windows install.
  pause
  exit /b 1
)

echo Using: %PSEXE%
echo.

REM Clear previous BandCamp / Explorer / OpenWith choices for .ps1
reg delete "HKCU\Software\Classes\BandCamp.PowerShellScript" /f >nul 2>&1
reg delete "HKCU\Software\Classes\.ps1" /f >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.ps1\UserChoice" /f >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.ps1\UserChoiceLatest" /f >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.ps1\OpenWithList" /f >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.ps1\OpenWithProgids" /f >nul 2>&1

REM Register handler (per-user, no admin)
reg add "HKCU\Software\Classes\.ps1" /ve /d "BandCamp.PowerShellScript" /f >nul
reg add "HKCU\Software\Classes\.ps1\OpenWithProgids" /v "BandCamp.PowerShellScript" /t REG_NONE /f >nul
reg add "HKCU\Software\Classes\BandCamp.PowerShellScript" /ve /d "Windows PowerShell Script" /f >nul
reg add "HKCU\Software\Classes\BandCamp.PowerShellScript\DefaultIcon" /ve /d "\"%PSEXE%\",0" /f >nul
reg add "HKCU\Software\Classes\BandCamp.PowerShellScript\shell" /ve /d "open" /f >nul
reg add "HKCU\Software\Classes\BandCamp.PowerShellScript\shell\open" /ve /d "Run with Windows PowerShell" /f >nul
reg add "HKCU\Software\Classes\BandCamp.PowerShellScript\shell\open\command" /ve /d "\"%PSEXE%\" -NoLogo -NoExit -ExecutionPolicy Bypass -File \"%%1\" %%*" /f >nul

REM Also point Applications\powershell.exe open command (helps some Open With lists)
reg add "HKCU\Software\Classes\Applications\powershell.exe\shell\open\command" /ve /d "\"%PSEXE%\" -NoLogo -NoExit -ExecutionPolicy Bypass -File \"%%1\" %%*" /f >nul

echo Done. .ps1 open command:
echo   "%PSEXE%" -NoLogo -NoExit -ExecutionPolicy Bypass -File "%%1"
echo.
echo Tip: step .bat files always work even if Explorer still shows a picker.
echo Or use the no-install EXE in the app\ folder.
echo.
pause
endlocal
