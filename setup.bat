@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  Monte Carlo SQL Validator — Setup
echo ============================================================
echo.

:: ── 1. Check Python is installed ─────────────────────────────────────────────
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python is not installed or not on PATH.
    echo  Please install Python 3.x from https://www.python.org/downloads/
    echo  and ensure "Add Python to PATH" is checked during installation.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo  Found: !PYTHON_VERSION!
echo.

:: ── 2. Create virtual environment ────────────────────────────────────────────
echo [2/5] Creating virtual environment (venv)...
if exist venv (
    echo  Virtual environment already exists. Skipping creation.
) else (
    python -m venv venv
    if errorlevel 1 (
        echo  ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo  Virtual environment created successfully.
)
echo.

:: ── 3. Activate virtual environment ──────────────────────────────────────────
echo [3/5] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo  ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)
echo  Virtual environment activated.
echo.

:: ── 4. Upgrade pip ───────────────────────────────────────────────────────────
echo [4/5] Upgrading pip...
python -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo  WARNING: pip upgrade failed. Continuing with existing version.
) else (
    echo  pip upgraded successfully.
)
echo.

:: ── 5. Install dependencies ───────────────────────────────────────────────────
echo [5/5] Installing dependencies from requirements.txt...
if not exist requirements.txt (
    echo  ERROR: requirements.txt not found in current directory.
    echo  Please run this script from the project root folder.
    pause
    exit /b 1
)
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  ERROR: Dependency installation failed.
    echo  Check the error messages above and re-run setup.bat.
    pause
    exit /b 1
)
echo.

:: ── Done ─────────────────────────────────────────────────────────────────────
echo ============================================================
echo  Setup completed successfully!
echo ============================================================
echo.
echo  Next steps:
echo    1. Copy .env.example to .env
echo       copy .env.example .env
echo.
echo    2. Open .env in a text editor and fill in your Snowflake credentials.
echo.
echo    3. Place your input Excel file at:
echo       input\input_queries.xlsx
echo       (or run:  venv\Scripts\python create_sample_input.py)
echo.
echo    4. Run the application:
echo       run.bat
echo.
pause
endlocal
