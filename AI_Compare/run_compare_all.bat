@echo off
setlocal EnableDelayedExpansion
pushd "%~dp0." 2>nul

set "PY_CMD=python"
where python >nul 2>&1
if not errorlevel 1 goto :py_ok
where py >nul 2>&1
if errorlevel 1 (
  echo [AI_Compare] 未找到 Python，请先安装 Python 3。
  pause
  popd 2>nul
  exit /b 1
)
set "PY_CMD=py -3"
:py_ok

if not exist "results\" mkdir "results"
if not exist "raw_cache\" mkdir "raw_cache"

set "LOG=%CD%\results\run_compare_all_last.log"
echo ---- %DATE% %TIME% ---->>"%LOG%"

echo.
echo ============================================================
echo  AI_Compare 横向对比（自动检测已配置的 Key）
echo ============================================================
echo.
echo  若尚未配置 Key，请先阅读: SETUP_KEYS.md
echo  当前窗口可临时设置，例如:
echo    set SERPER_API_KEY=你的key
echo    set BRAVE_API_KEY=你的key
echo    set TAVILY_API_KEY=tvly-你的key
echo.

echo [1/3] 检查 provider 配置 ...
call %PY_CMD% run_eval.py --list
echo.

echo [2/3] 安装依赖 ...
call %PY_CMD% -m pip install -r requirements.txt -q >>"%LOG%" 2>&1

echo [3/3] 开始对比（--auto）...
call %PY_CMD% run_eval.py --auto >>"%LOG%" 2>&1
if errorlevel 1 (
  echo.
  echo [失败] 详见日志: %LOG%
  pause
  popd 2>nul
  exit /b 1
)

echo.
echo [完成] 报告在 results\ 目录
echo [日志] %LOG%
pause
popd 2>nul
exit /b 0
