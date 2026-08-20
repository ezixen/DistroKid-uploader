@echo off
setlocal EnableExtensions EnableDelayedExpansion
:: DEV ONLY — Run from Admin CMD in Safe Mode.
:: msconfig -> Boot -> Safe boot (Minimal) -> reboot
:: After success: msconfig -> uncheck Safe boot -> reboot normally
::
:: Removes stuck automation Chrome / Playwright profile SUBFOLDERS under
:: C:\Temp and D:\Temp (and optional BandCamp unpack trees). Does not wipe
:: the whole Temp directory — only matching junk names.

echo === Safe Mode: stuck Chrome / Playwright Temp folders ===
echo.

call :KillChromeQuiet

:: --- Temp roots: wipe matching stuck subfolders (all of them) ---
call :CleanTempRoot "C:\Temp"
call :CleanTempRoot "C:\temp"
call :CleanTempRoot "D:\Temp"
call :CleanTempRoot "D:\temp"
if defined TEMP if /I not "%TEMP%"=="C:\Temp" if /I not "%TEMP%"=="C:\temp" (
  call :CleanTempRoot "%TEMP%"
)

:: --- Optional: old BandCamp unpack folders (edit / add paths for this PC) ---
call :ForceRemoveDir "C:\downloads\BandCamp-Uploader"
call :ForceRemoveDir "C:\downloads\BandCamp-uploader"

echo.
echo === Summary (Temp automation leftovers) ===
call :ReportTempRoot "C:\Temp"
call :ReportTempRoot "D:\Temp"
if exist "C:\downloads\BandCamp-Uploader" (echo STILL: C:\downloads\BandCamp-Uploader) else (echo GONE or absent: C:\downloads\BandCamp-Uploader)
echo.
echo Done. Turn OFF Safe boot in msconfig, then reboot normally.
pause
exit /b 0

:: ---------------------------------------------------------------------------
:KillChromeQuiet
taskkill /IM chrome.exe /F >nul 2>&1
taskkill /IM chromium.exe /F >nul 2>&1
taskkill /IM msedge.exe /F >nul 2>&1
timeout /t 2 /nobreak >nul
exit /b 0

:: ---------------------------------------------------------------------------
:CleanTempRoot
set "ROOT=%~1"
if not exist "%ROOT%\" (
  echo skip missing: %ROOT%
  exit /b 0
)
echo --- Cleaning matching subfolders under: %ROOT%

:: Playwright / Puppeteer / Selenium / Chrome automation profile dirs
for /d %%D in ("%ROOT%\playwright_chromiumdev_profile-*") do call :ForceRemoveDir "%%~fD"
for /d %%D in ("%ROOT%\playwright_chromium*") do call :ForceRemoveDir "%%~fD"
for /d %%D in ("%ROOT%\puppeteer_*") do call :ForceRemoveDir "%%~fD"
for /d %%D in ("%ROOT%\selenium-*") do call :ForceRemoveDir "%%~fD"
for /d %%D in ("%ROOT%\chrome-canary*") do call :ForceRemoveDir "%%~fD"
for /d %%D in ("%ROOT%\chrome-wiwm*") do call :ForceRemoveDir "%%~fD"
for /d %%D in ("%ROOT%\chrome-debug-profile*") do call :ForceRemoveDir "%%~fD"
for /d %%D in ("%ROOT%\ela-chrome*") do call :ForceRemoveDir "%%~fD"
for /d %%D in ("%ROOT%\merge-purge-*chrome*") do call :ForceRemoveDir "%%~fD"

:: Legacy BandCamp junk dropped into Temp
for /d %%D in ("%ROOT%\local-secrets*") do call :ForceRemoveDir "%%~fD"
for /d %%D in ("%ROOT%\BandCamp-Uploader*") do call :ForceRemoveDir "%%~fD"
for /d %%D in ("%ROOT%\BandCamp-uploader*") do call :ForceRemoveDir "%%~fD"

:: Renamed leftovers from prior cleanup attempts
for /d %%D in ("%ROOT%\*.to_delete") do call :ForceRemoveDir "%%~fD"
for /d %%D in ("%ROOT%\*.__delete_me__") do call :ForceRemoveDir "%%~fD"
for /d %%D in ("%ROOT%\*__delete_me__") do call :ForceRemoveDir "%%~fD"

exit /b 0

:: ---------------------------------------------------------------------------
:ForceRemoveDir
set "TARGET=%~1"
if "%TARGET%"=="" exit /b 0
if not exist "%TARGET%" exit /b 0

echo Removing: %TARGET%
takeown /F "%TARGET%" /A /R /D Y >nul 2>&1
icacls "%TARGET%" /grant Administrators:F /T /C /Q >nul 2>&1
icacls "%TARGET%" /grant "%USERNAME%":F /T /C /Q >nul 2>&1
icacls "%TARGET%" /grant SYSTEM:F /T /C /Q >nul 2>&1

:: Extended path prefix helps with long / stubborn paths
rd /s /q "\\?\%TARGET%" >nul 2>&1
if exist "%TARGET%" rd /s /q "%TARGET%" >nul 2>&1

:: Robocopy empty-mirror fallback when rd fails
if exist "%TARGET%" (
  set "EMPTY=%TEMP%\empty_del_%RANDOM%"
  mkdir "!EMPTY!" >nul 2>&1
  robocopy "!EMPTY!" "%TARGET%" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /nc /ns /np >nul 2>&1
  rd /s /q "!EMPTY!" >nul 2>&1
  rd /s /q "\\?\%TARGET%" >nul 2>&1
)

if exist "%TARGET%" (
  echo   STILL: %TARGET%
) else (
  echo   GONE:  %TARGET%
)
exit /b 0

:: ---------------------------------------------------------------------------
:ReportTempRoot
set "ROOT=%~1"
if not exist "%ROOT%\" exit /b 0
set "LEFT=0"
for /d %%D in ("%ROOT%\playwright_chromium*") do (
  echo STILL: %%~fD
  set /a LEFT+=1
)
for /d %%D in ("%ROOT%\chrome-canary*") do (
  echo STILL: %%~fD
  set /a LEFT+=1
)
for /d %%D in ("%ROOT%\chrome-debug-profile*") do (
  echo STILL: %%~fD
  set /a LEFT+=1
)
for /d %%D in ("%ROOT%\local-secrets*") do (
  echo STILL: %%~fD
  set /a LEFT+=1
)
if !LEFT! EQU 0 echo OK: no matching stuck folders left under %ROOT%
exit /b 0
