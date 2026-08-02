@echo off
setlocal EnableExtensions
set "BIN=%~dp0"
set "SRC=%BIN%..\src"
set "ASSETS=%BIN%..\..\assets"
set "DOCS=%BIN%..\docs"
set "PKG=%BIN%.."
setlocal
cd /d "%BIN%"

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
%PY_CMD% "%SRC%\sync_url_params_to_json.py"
if errorlevel 1 (
  echo URL params sync failed. Please check assets/url_params.xlsx.
  goto :err
)

for /f "delims=" %%I in ('powershell -NoProfile -Command "(Get-Date).ToString('yyyyMMdd')"') do set "DATE_TAG=%%I"
for /f "delims=" %%I in ('powershell -NoProfile -Command "(Get-Date).ToString('yyyyMMdd_HH.mm')"') do set "RUN_TAG=%%I"
call "%BIN%set_runs_out_dir.bat"
if errorlevel 1 goto :err

echo Generating MarketRateData Excel...
set "MARKET_OUT=%OUT_DIR%\MarketRateData_%RUN_TAG%.xlsx"
%PY_CMD% "%SRC%\market_rate_data_generator.py" --xlsx-out "%MARKET_OUT%"
if errorlevel 1 (
  echo Default filename may be locked. Retrying with timestamp filename...
  for /f %%I in ('powershell -NoProfile -Command "(Get-Date).ToString(\"yyyyMMdd_HHmmss\")"') do set TS=%%I
  %PY_CMD% "%SRC%\market_rate_data_generator.py" --xlsx-out "%OUT_DIR%\MarketRateData_%TS%.xlsx"
  if errorlevel 1 goto :err
)

echo.
echo Done. Output folder: %OUT_DIR%
pause
exit /b 0

:err
echo.
echo Generation failed. Run 01 installer batch first, then retry.
pause
exit /b 1
