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
where python >nul 2>nul || set "PY_CMD=py -3"

echo [SEED] 将 url_params.xlsx 合并进 url_params_ai.xlsx（手动 URL 优先）
echo [SEED] 可选：先加参数 --discover-first 再跑 Vertex 发现
echo.

%PY_CMD% "%SRC%\seed_url_params_ai_from_manual.py" %*
if errorlevel 1 goto :err

echo.
echo [SEED] 完成。下一步可运行：
echo   05_run_ai_search.bat
echo 或：
echo   python run_market_rate_ai_search.py --skip-discover
goto :finish

:err
echo [SEED] 失败
pause
exit /b 1

:finish
pause
exit /b 0
