@echo off
setlocal enabledelayedexpansion

REM --- OPENBABELFISH APPLIANCE LAUNCHER ---
echo [INIT] Starting OpenBabelFish...

set "PYTHONUTF8=1"
set "PIP_NO_WARN_SCRIPT_LOCATION=0"
set "VENV_DIR=venv"
set "VENV_PYTHON=%~dp0%VENV_DIR%\Scripts\python.exe"

REM 0. Check Python
python --version >nul 2>nul
if !errorlevel! neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

REM 1. Create Venv if missing
if not exist "%VENV_DIR%" (
    echo [1/7] Workspace: Initializing virtual environment...
    python -m venv "%VENV_DIR%"
)

REM 2. Activate and Setup
echo [2/7] Activation: Entering isolated environment...
call "%VENV_DIR%\Scripts\activate.bat"

REM 2.1 Ensure Core Compatibility (NumPy < 2.0.0, Pillow, etc.)
"%VENV_PYTHON%" -c "import numpy; exit(0 if numpy.__version__.startswith('1.') else 1)" >nul 2>nul
if !errorlevel! neq 0 (
    echo [3/7] Dependencies: Synchronizing core libraries...
    "%VENV_PYTHON%" -m pip install --upgrade pip "setuptools<82" wheel --no-warn-script-location
    "%VENV_PYTHON%" -m pip install "numpy<2.0.0" "Pillow>=9.0.0" "urllib3<2.0.0" --no-warn-script-location
)

REM 2.2 Ensure Document Extraction libraries (PDF, DOCX, PPTX, EPUB)
"%VENV_PYTHON%" -c "import fitz" >nul 2>nul
if !errorlevel! neq 0 (
    echo [4/7] Documents: Installing PDF/DOCX/PPTX/EPUB support...
    "%VENV_PYTHON%" -m pip install PyMuPDF python-docx python-pptx EbookLib beautifulsoup4 --no-warn-script-location
)

REM 2.3 Ensure OCR Engine (EasyOCR for scanned PDFs)
"%VENV_PYTHON%" -c "import easyocr" >nul 2>nul
if !errorlevel! neq 0 (
    echo [5/7] OCR: Installing EasyOCR engine...
    "%VENV_PYTHON%" -m pip install easyocr --no-warn-script-location
)

REM 3. Ensure the package itself is installed
echo [6/7] Integration: Verifying local package link...
"%VENV_PYTHON%" -m pip show openbabelfish-translate >nul 2>nul
if !errorlevel! neq 0 (
    echo [6/7] Integration: Linking to venv now...
    "%VENV_PYTHON%" -m pip install -e . --no-build-isolation --no-warn-script-location
    if !errorlevel! neq 0 (
        echo [WARNING] Local installation failed. Attempting to run directly...
    )
) else (
    echo [6/7] Integration: Already linked to venv.
)

REM 4. Run
echo [7/7] Launching OpenBabelFish...
echo.

REM Start the CLI. 
REM Since there are no arguments, it will automatically enter the Rich Interactive Shell.
"%VENV_PYTHON%" -m openbabelfish.cli

exit /b 0
