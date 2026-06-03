@echo off
setlocal
cd /d "%~dp0"

set "PY_CMD=python"
where python >nul 2>nul
if errorlevel 1 (
  where py >nul 2>nul
  if errorlevel 1 (
    echo Python not found in PATH.
    pause
    exit /b 1
  )
  set "PY_CMD=py -3"
)

echo Syncing url_params.xlsx -> url_params.json...
%PY_CMD% "sync_url_params_to_json.py"
if errorlevel 1 (
  echo URL params sync failed. Please check assets/url_params.xlsx.
  goto :err
)

echo Generating MarketRateData Excel...
%PY_CMD% "market_rate_data_generator.py" --xlsx-out "."
if errorlevel 1 (
  echo Default filename may be locked. Retrying with timestamp filename...
  for /f %%I in ('powershell -NoProfile -Command "(Get-Date).ToString(\"yyyyMMdd_HHmmss\")"') do set TS=%%I
  %PY_CMD% "market_rate_data_generator.py" --xlsx-out "MarketRateData_%TS%.xlsx"
  if errorlevel 1 goto :err
)

echo.
echo Done. Output file is in current folder.
pause
exit /b 0

:err
echo.
echo Generation failed. Run 01 installer batch first, then retry.
pause
exit /b 1
