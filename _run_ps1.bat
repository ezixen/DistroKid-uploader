@echo off
setlocal EnableExtensions
REM Always use built-in Windows PowerShell (same as 0_associate_ps1.bat).
REM Usage: _run_ps1.bat script.ps1 [args...]

if "%~1"=="" (
  echo ERROR: No script specified.
  exit /b 1
)

set "SCRIPT=%~1"
shift

if not exist "%SCRIPT%" (
  echo ERROR: Script not found: %SCRIPT%
  pause
  exit /b 1
)

set "PSEXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PSEXE%" (
  echo ERROR: Windows PowerShell not found: %PSEXE%
  pause
  exit /b 1
)

"%PSEXE%" -NoLogo -NoExit -ExecutionPolicy Bypass -File "%SCRIPT%" %*
endlocal
