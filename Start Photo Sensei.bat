@echo off
title Photo Sensei
cd /d "%~dp0"
echo ============================================================
echo   Photo Sensei - Telegram photography coaching bot
echo   Keep this window OPEN while you use the bot.
echo   Close this window (or press Ctrl+C) to stop it.
echo ============================================================
echo.
echo Stopping any bot already running (avoids a token conflict)...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*bot.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
echo.
:loop
echo [%time%] Starting bot...
python bot.py
echo.
echo [%time%] Bot stopped (exit code %errorlevel%). Restarting in 5 seconds...
echo (Close this window now if you meant to stop it.)
timeout /t 5 >nul
goto loop
