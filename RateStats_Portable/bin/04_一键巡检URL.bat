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

echo [0/1] Sync url_params.xlsx -> url_params.json...
%PY_CMD% "%SRC%\sync_url_params_to_json.py"
if errorlevel 1 (
  echo URL params sync failed. Please check assets/url_params.xlsx.
  goto :err
)

echo [1/1] URL health check...
%PY_CMD% "%SRC%\check_url_health.py"
if errorlevel 1 goto :err

echo.
echo URL check done.
pause
exit /b 0

:err
echo.
echo URL check failed.
pause
exit /b 1
