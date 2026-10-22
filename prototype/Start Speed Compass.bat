@echo off
title Speed Compass
cd /d "%~dp0"
set URL=http://127.0.0.1:8501

rem Already running? Just open it.
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -UseBasicParsing '%URL%/_stcore/health' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if %errorlevel%==0 (
  echo Speed Compass is already running. Opening it in your browser.
  start "" %URL%
  timeout /t 3 >nul
  exit /b
)

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.11 from python.org, tick "Add python.exe to PATH", then try again.
  pause
  exit /b
)

python -c "import streamlit, plotly, anthropic, segno, google.genai" >nul 2>nul
if errorlevel 1 (
  echo First run on this computer: installing the app's packages. This needs internet and takes a minute.
  python -m pip install --user -r requirements.txt
)

echo.
echo  Starting Speed Compass...
echo  Your browser opens by itself when the app is ready, in about 10 to 20 seconds.
echo  Keep this window open during the demo. Close it to stop the app.
echo.

rem Open the browser only once the app answers its health check.
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "$ProgressPreference='SilentlyContinue'; for ($i = 0; $i -lt 120; $i++) { try { Invoke-WebRequest -UseBasicParsing '%URL%/_stcore/health' -TimeoutSec 2 | Out-Null; Start-Process '%URL%'; break } catch { Start-Sleep -Seconds 1 } }"

python -m streamlit run app.py --server.port 8501 --server.address 127.0.0.1

echo.
echo  Speed Compass has stopped. If you see an error above, send a screenshot of this window.
pause
