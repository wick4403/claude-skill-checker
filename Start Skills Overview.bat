@echo off
:: Stop eventuele bestaande instantie op poort 8765
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8765.*LISTEN"') do (
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: Start de app
python "%~dp0skills_overview.py"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Fout: controleer of Python is geinstalleerd.
    pause
)
