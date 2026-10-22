@echo off
title Speed Compass - shared with judges
cd /d "%~dp0"
set URL=http://127.0.0.1:8501

rem Only one copy can run at a time.
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -UseBasicParsing '%URL%/_stcore/health' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if %errorlevel%==0 (
  echo Speed Compass is already running in another window.
  echo Close that window first, then double-click "Share with judges" again.
  pause
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
echo  Starting Speed Compass for judges...
echo  1. Judges join the same Wi-Fi as this laptop, or your phone hotspot (most reliable).
echo  2. The sidebar shows a QR code and address for them to open.
echo  3. If Windows asks whether Python may use networks, tick Private networks and click Allow.
echo  Keep this window open during the demo. Close it to stop the app.
echo.

set SPEED_COMPASS_SHARE=1
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "$ProgressPreference='SilentlyContinue'; for ($i = 0; $i -lt 120; $i++) { try { Invoke-WebRequest -UseBasicParsing '%URL%/_stcore/health' -TimeoutSec 2 | Out-Null; Start-Process '%URL%'; break } catch { Start-Sleep -Seconds 1 } }"

python -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0

echo.
echo  Speed Compass has stopped. If you see an error above, send a screenshot of this window.
pause
