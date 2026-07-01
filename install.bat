@echo off
echo.
echo  === ASCII Video Converter - Installation ===
echo.

:: Auto-detect Python (tries "python", then "python3", then "py")
set PYTHON=
for %%P in (python python3 py) do (
  if not defined PYTHON (
    %%P --version >nul 2>&1 && set PYTHON=%%P
  )
)

if not defined PYTHON (
  echo [ERREUR] Python introuvable dans le PATH.
  echo  Telecharge Python sur https://www.python.org/downloads/
  pause
  exit /b 1
)

echo Python detecte : %PYTHON%
echo.
echo [1/2] Creation de l'environnement virtuel...
%PYTHON% -m venv venv
if errorlevel 1 ( echo [ERREUR] Echec venv. && pause && exit /b 1 )

echo [2/2] Installation des dependances...
venv\Scripts\pip install -r requirements.txt
if errorlevel 1 ( echo [ERREUR] Echec pip install. && pause && exit /b 1 )

echo.
echo  Installation terminee !
echo  Lance l'appli avec : start.bat
echo.
pause
