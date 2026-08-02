@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "BIN=%~dp0"
set "SRC=%BIN%..\src"
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

echo [ICBC] Resolve latest promo/board URLs from official column pages...
%PY_CMD% "%SRC%\icbc_url_resolve.py"
if errorlevel 1 goto :err

echo.
pause
exit /b 0

:err
echo.
echo ICBC URL resolve failed.
pause
exit /b 1
