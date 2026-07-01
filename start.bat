@echo off
echo.
echo  === ASCII Video Converter ===
echo  Opening at http://localhost:5000
echo  (Ctrl+C to stop)
echo.
start http://localhost:5000
venv\Scripts\python app.py
pause
