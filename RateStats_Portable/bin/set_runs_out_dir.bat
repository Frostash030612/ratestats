@echo off
setlocal EnableExtensions
set "BIN=%~dp0"
set "SRC=%BIN%..\src"
set "ASSETS=%BIN%..\..\assets"
set "DOCS=%BIN%..\docs"
set "PKG=%BIN%.."

rem Set OUT_DIR under runs/ after DATE_TAG or BATCH_NAME is defined.

rem Example DATE_TAG=20260603 then call this script.

rem Example BATCH_NAME=sameday_20260603 then call this script.

set "RUNS_ROOT=%BIN%..\..\runs"

if defined RATESTATS_RUNS_ROOT set "RUNS_ROOT=%RATESTATS_RUNS_ROOT%"



if defined BATCH_NAME (

  set "OUT_DIR=%RUNS_ROOT%\%BATCH_NAME%"

) else if defined DATE_TAG (

  set "OUT_DIR=%RUNS_ROOT%\%DATE_TAG%"

) else (

  echo [set_runs_out_dir] ERROR: need DATE_TAG or BATCH_NAME

  exit /b 1

)

if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

exit /b 0
