@echo off
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo Polymarket Agent - Bootstrap (Windows)
echo ============================================================
echo.

REM Check for .env
if exist "%~dp0..\.env" (
    echo [OK] .env already exists, skipping.
) else (
    echo [1/3] Creating .env from .env.example...
    copy "%~dp0..\.env.example" "%~dp0..\.env"
    echo [OK] .env created. Please edit it and fill in your API keys.
    echo.
)

REM Create venv
echo [2/3] Creating Python virtual environment...
cd /d "%~dp0.."
if exist venv (
    echo [SKIP] venv already exists.
) else (
    python -m venv venv
    echo [OK] venv created.
)
echo.

REM Install dependencies
echo [3/3] Installing dependencies...
call "%~dp0..\venv\Scripts\pip.exe" install -e .[dev]
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo [OK] Dependencies installed.
echo.

REM Print next steps
echo ============================================================
echo Environment ready! Next steps:
echo.
echo   1. Edit .env and fill in your keys:
echo      notepad "%~dp0..\.env"
echo.
echo   2. Start the database with Docker:
echo      docker-compose up -d postgres redis
echo.
echo   3. Run database migrations:
echo      make db-upgrade
echo.
echo   4. Start the dev server:
echo      make dev
echo.
echo ============================================================
pause
