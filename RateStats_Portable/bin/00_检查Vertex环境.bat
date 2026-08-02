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
  echo [00] ERROR: cannot cd to script folder.
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

set "DEFAULT_KEY=%CD%\assets\ratestatsearch-f5f95dab974f.json"
set "KEY_PATH=%GOOGLE_APPLICATION_CREDENTIALS%"
if not defined KEY_PATH set "KEY_PATH=%DEFAULT_KEY%"

echo ============================================================
echo [00] Vertex environment check
echo [00] Script dir: %CD%
echo [00] Python cmd: %PY_CMD%
echo [00] GOOGLE_APPLICATION_CREDENTIALS=%GOOGLE_APPLICATION_CREDENTIALS%
echo [00] Effective key path: %KEY_PATH%
echo ============================================================
echo.

echo [1/3] Check key file exists...
if not exist "%KEY_PATH%" (
  echo [00] FAIL: key file not found:
  echo       %KEY_PATH%
  echo.
  echo [00] Fix:
  echo   1) Put your service-account JSON under RateStats_Portable\assets\
  echo   2) Or set env var GOOGLE_APPLICATION_CREDENTIALS to the JSON path.
  goto :err
)
echo [00] OK: key file exists.
echo.

echo [2/3] Check required Python packages...
call %PY_CMD% -c "import google.oauth2.service_account, requests; print('[00] OK: imports fine')"
if errorlevel 1 (
  echo [00] FAIL: missing dependency.
  echo [00] Run 01_首次安装依赖.bat first.
  goto :err
)
echo.

echo [3/3] Run Vertex smoke test...
call %PY_CMD% "%SRC%\test_vertex_search.py"
if errorlevel 1 (
  echo.
  echo [00] FAIL: Vertex smoke test failed.
  echo [00] Check project/engine/permission and key validity.
  goto :err
)

echo.
echo [00] PASS: Vertex environment is ready.
goto :finish

:no_python
echo [00] FAIL: Python not found in PATH.
echo [00] Install Python 3.10+ and check "Add Python to PATH".
goto :err

:err
echo.
echo [00] Check failed.
pause
popd 2>nul
exit /b 1

:finish
pause
popd 2>nul
exit /b 0
