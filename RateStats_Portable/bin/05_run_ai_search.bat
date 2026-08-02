@echo off
setlocal EnableExtensions
set "BIN=%~dp0"
set "SRC=%BIN%..\src"
set "ASSETS=%BIN%..\..\assets"
set "DOCS=%BIN%..\docs"
set "PKG=%BIN%.."
setlocal EnableDelayedExpansion
pushd "%~dp0." 2>nul
if errorlevel 1 (
  echo [05] ERROR: cannot cd to script folder.
  pause
  exit /b 1
)

set "PY_CMD=python"
where python >nul 2>&1
if not errorlevel 1 goto :py_ok
where py >nul 2>&1
if errorlevel 1 goto :no_python
set "PY_CMD=py -3"
:py_ok

if not exist "%ASSETS%\" mkdir "%ASSETS%"

for /f "delims=" %%I in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Date).ToString('yyyyMMdd')"') do set "DATE_TAG=%%I"
call "%BIN%set_runs_out_dir.bat"
if not exist "%OUT_DIR%\logs" mkdir "%OUT_DIR%\logs"
set "LOG=%OUT_DIR%\logs\ai_search_last_run.log"
echo ---- %DATE% %TIME% ---->>"%LOG%"

echo [05] Vertex AI search + MarketRateData *_AISearch.xlsx
echo [05] Config: runs\...\url_params_ai.xlsx
echo [05] Will NOT touch url_params.xlsx or url_params.json
echo [05] Log: %LOG%
echo.

set "AI_EXTRA="
if defined OUTPUT_FOLDER set "AI_EXTRA=--output-folder "%OUTPUT_FOLDER%""
if defined RUN_TAG set "AI_EXTRA=%AI_EXTRA% --run-tag "%RUN_TAG%""

echo [05] pip install google-auth requests ...
call %PY_CMD% -m pip install google-auth requests -q >>"%LOG%" 2>&1
if errorlevel 1 goto :err

echo [05] run_market_rate_ai_search.py ...
call %PY_CMD% "%SRC%\run_market_rate_ai_search.py" %AI_EXTRA% >>"%LOG%" 2>&1
if errorlevel 1 goto :err

echo.
echo [05] Done. Output in today folder, name contains _AISearch
if defined OUTPUT_FOLDER echo [05] Folder: %OUTPUT_FOLDER%
if defined RUN_TAG echo [05] Tag: %RUN_TAG%
echo [05] Log: %LOG%
goto :finish

:no_python
echo [05] Python not found. Run 01 installer batch first.
goto :err

:err
echo.
echo [05] Failed. Try: python test_vertex_search.py
echo [05] See log: %LOG%
pause
popd 2>nul
exit /b 1

:finish
if not defined CALLER_COMBINED pause
popd 2>nul
exit /b 0
