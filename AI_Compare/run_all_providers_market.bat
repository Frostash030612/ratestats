@echo off
setlocal EnableDelayedExpansion
pushd "%~dp0." 2>nul

set "PY_CMD=python"
where python >nul 2>&1
if not errorlevel 1 goto :py_ok
set "PY_CMD=py -3"
:py_ok

echo.
echo ============================================================
echo  四家 AI 搜索: Vertex + Serper + Brave + Tavily
echo  发现 URL + 生成 MarketRateData_*_Provider.xlsx
echo ============================================================
echo.
echo  Key 请放在本目录 keys.txt （见 SETUP_KEYS.md）
echo  仅发现链接: run_all_providers_market.bat discover
echo.

if /I "%~1"=="discover" (
  call %PY_CMD% run_all_providers_market.py --discover-only --skip-missing-keys --also-write-portable-vertex
) else (
  call %PY_CMD% run_all_providers_market.py --skip-missing-keys --also-write-portable-vertex
)

set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" (
  echo.
  echo [失败] exit=%EC%
  pause
  popd 2>nul
  exit /b %EC%
)
echo.
echo [完成]
pause
popd 2>nul
exit /b 0
