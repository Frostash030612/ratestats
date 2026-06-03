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

echo [1/2] Generate MarketRateData...
%PY_CMD% "market_rate_data_generator.py" --xlsx-out "."
if errorlevel 1 (
  echo Default filename may be locked. Retrying with timestamp filename...
  for /f %%I in ('powershell -NoProfile -Command "(Get-Date).ToString(\"yyyyMMdd_HHmmss\")"') do set TS=%%I
  %PY_CMD% "market_rate_data_generator.py" --xlsx-out "MarketRateData_%TS%.xlsx"
  if errorlevel 1 goto :err
)

echo [2/2] Generate Rainbow workbook...
%PY_CMD% "generate_rainbow_from_market.py"
if errorlevel 1 goto :err

echo.
echo All done.
pause
exit /b 0

:err
echo.
echo Failed. Check dependencies/network and retry.
pause
exit /b 1
