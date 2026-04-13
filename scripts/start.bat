@echo off
setlocal enabledelayedexpansion

echo.
echo   ^◈  DataPulse ^— Talk to Your Data
echo   ^─────────────────────────────────
echo.

set "ROOT=%~dp0.."
pushd "%ROOT%"

:: ── Python check ────────────────────────────────────────────────────────────
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   ^✗ Python not found. Install Python 3.10+ from https://python.org and try again.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo   ^✓ Python %PY_VER%

:: ── Node.js check ───────────────────────────────────────────────────────────
node --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   ^✗ Node.js not found. Install Node.js 18+ from https://nodejs.org and try again.
    pause
    exit /b 1
)
for /f %%v in ('node --version') do set NODE_VER=%%v
echo   ^✓ Node.js %NODE_VER%

:: ── .env setup ──────────────────────────────────────────────────────────────
if not exist .env (
    copy .env.example .env >nul
    echo   ^↳ Created .env from .env.example
)

findstr /C:"GROQ_API_KEY=" .env | findstr /V /C:"GROQ_API_KEY=your" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo   ^⚠  GROQ_API_KEY is not set in .env
    echo      Get a free key at: https://console.groq.com/keys
    set /p API_KEY="  Enter your Gemini API key: "
    if "!API_KEY!"=="" (
        echo   ^✗ No key provided. Exiting.
        pause
        exit /b 1
    )
    powershell -Command "(Get-Content .env) -replace 'GROQ_API_KEY=.*', 'GROQ_API_KEY=!API_KEY!' | Set-Content .env"
    echo   ^✓ API key saved to .env
)
echo   ^✓ GROQ_API_KEY is set

:: ── Python venv + deps ──────────────────────────────────────────────────────
if not exist venv (
    echo   ^→ Creating Python virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo   ^→ Installing Python dependencies...
pip install -q -r requirements.txt 2>nul
echo   ^✓ Python dependencies ready

:: ── Sample datasets ──────────────────────────────────────────────────────────
if not exist assets\samples\sme_lending.csv (
    echo   ^→ Generating banking sample datasets...
    python scripts\generate_samples.py
)
echo   ^✓ Sample datasets ready

:: ── Start backend in new window ──────────────────────────────────────────────
echo   ^→ Starting backend on http://localhost:8000...
start "DataPulse Backend" cmd /k "cd /d %ROOT% && call venv\Scripts\activate.bat && cd src\backend && uvicorn main:app --port 8000"

:: Give the backend a moment to start
timeout /t 3 /nobreak >nul

:: ── Frontend deps + start ────────────────────────────────────────────────────
echo   ^→ Installing frontend dependencies...
pushd src\frontend
if not exist node_modules (
    call npm install --silent 2>nul
)
echo   ^✓ Frontend dependencies ready

echo.
echo   ^┌─────────────────────────────────────────^┐
echo   ^│                                         ^│
echo   ^│   Open http://localhost:3000            ^│
echo   ^│   in your browser to use DataPulse      ^│
echo   ^│                                         ^│
echo   ^│   Close this window to stop the frontend^│
echo   ^│   Close the Backend window to stop it   ^│
echo   ^│                                         ^│
echo   ^└─────────────────────────────────────────^┘
echo.

call npm run dev
popd
popd
