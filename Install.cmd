@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install.ps1"
if errorlevel 1 echo Installer stopped. Read the message above and docs\RECOVERY.md if writing had started.
pause
