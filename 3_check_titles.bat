@echo off
cd /d "%~dp0"
call "%~dp0_run_ps1.bat" "%~dp03_check_titles.ps1" %*
