@echo off
:: ══════════════════════════════════════════════════════
::  NoteVerse — One-Click Launcher (Windows)
:: ══════════════════════════════════════════════════════

cd /d "%~dp0"

echo.
echo  NoteVerse — AI Notes Platform
echo ══════════════════════════════════

:: ── 1. Check Python ──────────────────────────────────
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERROR: Python not found. Install from https://python.org and re-run.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo  OK: %%i

:: ── 2. Create virtual-env (first run only) ───────────
if not exist "venv\" (
    echo  Creating virtual environment...
    python -m venv venv
)

:: ── 3. Activate virtual-env ──────────────────────────
call venv\Scripts\activate.bat

:: ── 4. Install dependencies ───────────────────────────
echo  Installing dependencies...
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo  OK: Dependencies ready.

:: ── 5. Ensure uploads directory exists ───────────────
if not exist "static\uploads\" mkdir static\uploads

:: ── 6. Anthropic API key reminder (optional) ─────────
if "%ANTHROPIC_API_KEY%"=="" (
    echo.
    echo  NOTE: ANTHROPIC_API_KEY is not set.
    echo  AI features will show a warning instead.
    echo  To enable them, run this in your terminal:
    echo    set ANTHROPIC_API_KEY=sk-ant-your-key-here
    echo  then re-run this script.
    echo.
)

:: ── 7. Launch Flask ───────────────────────────────────
echo.
echo  Starting server at http://localhost:5000
echo  Press Ctrl+C to stop.
echo.

python app.py
pause
