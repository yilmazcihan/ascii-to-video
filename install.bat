@echo off
echo.
echo  === ASCII Video Converter - Setup ===
echo.

:: Auto-detect Python (tries "python", then "python3", then "py")
set PYTHON=
for %%P in (python python3 py) do (
  if not defined PYTHON (
    %%P --version >nul 2>&1 && set PYTHON=%%P
  )
)

if not defined PYTHON (
  echo [ERROR] Python not found in PATH.
  echo  Download Python at https://www.python.org/downloads/
  pause
  exit /b 1
)

echo Python detected: %PYTHON%
echo.
echo [1/2] Creating virtual environment...
%PYTHON% -m venv venv
if errorlevel 1 ( echo [ERROR] Failed to create venv. && pause && exit /b 1 )

echo [2/2] Installing dependencies...
venv\Scripts\pip install -r requirements.txt
if errorlevel 1 ( echo [ERROR] pip install failed. && pause && exit /b 1 )

echo.
echo  Setup complete!
echo  Run the app with: start.bat
echo.
pause
