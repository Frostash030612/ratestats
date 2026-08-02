@echo off
setlocal EnableExtensions
set "BIN=%~dp0"
set "SRC=%BIN%..\src"
set "ASSETS=%BIN%..\..\assets"
set "DOCS=%BIN%..\docs"
set "PKG=%BIN%.."
setlocal EnableDelayedExpansion
pushd "%~dp0." 2>nul
chcp 65001 >nul

set "PY_CMD=python"
where python >nul 2>nul
if errorlevel 1 set "PY_CMD=py -3"

if "%~1"=="" (
  echo 用法: 创建彩虹表_SGD促销.bat "MarketRateData 完整路径.xlsx" [输出路径.xlsx]
  echo 示例: 创建彩虹表_SGD促销.bat "..\runs\20260709\MarketRateData_20260709_15.03.xlsx"
  popd
  exit /b 1
)

set "SOURCE=%~1"
if "%~2"=="" (
  %PY_CMD% "%SRC%\create_rainbow_sgd_promo_sheet.py" --source "%SOURCE%"
) else (
  %PY_CMD% "%SRC%\create_rainbow_sgd_promo_sheet.py" --source "%SOURCE%" --out "%~2"
)
set "RC=!errorlevel!"
popd
exit /b %RC%
