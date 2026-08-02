@echo off
setlocal EnableExtensions
set "BIN=%~dp0"
set "SRC=%BIN%..\src"
set "ASSETS=%BIN%..\..\assets"
set "DOCS=%BIN%..\docs"
set "PKG=%BIN%.."
chcp 65001 >nul
setlocal

set "SCRIPT="%SRC%\create_rainbow_sgd_board_sheet.py"
set "SOURCE=%~1"
if "%SOURCE%"=="" (
  echo 用法: %~nx0 "runs\YYYYMMDD\MarketRateData_YYYYMMDD_HH.MM.xlsx" [输出路径]
  exit /b 1
)

set "OUT=%~2"
if "%OUT%"=="" (
  python "%SCRIPT%" --source "%SOURCE%"
) else (
  python "%SCRIPT%" --source "%SOURCE%" --out "%OUT%"
)

endlocal
