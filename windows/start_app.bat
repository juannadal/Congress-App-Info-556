@echo off
rem Starts the Congress app and opens the "Label passages" page. Close this window to stop the app.
set PYTHONUTF8=1
cd /d "%~dp0.."
if not exist "%USERPROFILE%\.info556\venv\Scripts\python.exe" (
  echo Run windows\setup_windows.bat first.
  pause
  exit /b 1
)
start "" cmd /c "timeout /t 8 >nul && start http://localhost:8501/Label_passages"
"%USERPROFILE%\.info556\venv\Scripts\python.exe" -m streamlit run app.py --server.headless true
pause
