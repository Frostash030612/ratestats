@echo off
setlocal EnableExtensions
set "BIN=%~dp0"
set "SRC=%BIN%..\src"
set "ASSETS=%BIN%..\..\assets"
set "DOCS=%BIN%..\docs"
set "PKG=%BIN%.."

set "PY_CMD=python"
where python >nul 2>nul
if errorlevel 1 (
  where py >nul 2>nul
  if errorlevel 1 (
    echo Python not found.
    pause
    exit /b 1
  )
  set "PY_CMD=py -3"
)

%PY_CMD% "%SRC%\config_gui.py"
if errorlevel 1 pause
exit /b %errorlevel%
