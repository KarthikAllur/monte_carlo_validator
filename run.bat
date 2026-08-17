@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  Monte Carlo SQL Validator — Running Application
echo ============================================================
echo.

:: ── 1. Verify virtual environment exists ─────────────────────────────────────
if not exist venv\Scripts\activate.bat (
    echo  ERROR: Virtual environment not found.
    echo  Please run setup.bat first to create and configure the environment.
    echo.
    pause
    exit /b 1
)

:: ── 2. Activate virtual environment ──────────────────────────────────────────
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo  ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)

:: ── 3. Verify .env exists ─────────────────────────────────────────────────────
if not exist .env (
    echo  ERROR: .env file not found.
    echo  Please copy .env.example to .env and fill in your Snowflake credentials:
    echo    copy .env.example .env
    echo.
    pause
    exit /b 1
)

:: ── 4. Verify input Excel exists ──────────────────────────────────────────────
if not exist input\input_queries.xlsx (
    echo  WARNING: input\input_queries.xlsx not found.
    echo  You can create a sample file by running:
    echo    venv\Scripts\python create_sample_input.py
    echo.
    echo  Press any key to run anyway (will fail if file is missing)...
    pause >nul
)

:: ── 5. Run the application ────────────────────────────────────────────────────
echo  Starting application...
echo.
python src\main.py
set EXIT_CODE=%errorlevel%

echo.
if %EXIT_CODE% equ 0 (
    echo ============================================================
    echo  Application finished successfully.
    echo  Check output\output_results.xlsx for results.
    echo  Check logs\application.log for detailed logs.
    echo ============================================================
) else (
    echo ============================================================
    echo  Application exited with error code: %EXIT_CODE%
    echo  Check logs\application.log for details.
    echo ============================================================
)

echo.
pause
endlocal
