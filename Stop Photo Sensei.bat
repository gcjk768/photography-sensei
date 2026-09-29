@echo off
title Stop Photo Sensei
echo Stopping Photo Sensei bot...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*bot.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Done. Photo Sensei is stopped.
timeout /t 2 >nul
