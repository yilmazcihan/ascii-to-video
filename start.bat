@echo off
echo.
echo  === ASCII Video Converter ===
echo  Ouverture sur http://localhost:5000
echo  (Ctrl+C pour arreter)
echo.
start http://localhost:5000
venv\Scripts\python app.py
pause
