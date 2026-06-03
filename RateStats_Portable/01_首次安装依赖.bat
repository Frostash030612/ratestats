@echo off
setlocal
cd /d "%~dp0"

set "PY_CMD=python"
where python >nul 2>nul
if errorlevel 1 (
  where py >nul 2>nul
  if errorlevel 1 (
    echo Python not found in PATH.
    echo Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
  )
  set "PY_CMD=py -3"
)

echo [1/3] Upgrade pip...
%PY_CMD% -m pip install --upgrade pip
if errorlevel 1 goto :err

echo [2/3] 从 requirements.txt 安装依赖（已含 curl_cffi，用于 Maybank 等站点的 Chrome TLS 模拟抓取）...
%PY_CMD% -m pip install -r requirements.txt
if errorlevel 1 goto :err

echo [3/3] 确保 curl_cffi 已安装（与 requirements 一致，旧环境可补装）...
%PY_CMD% -m pip install "curl_cffi>=0.7.0"
if errorlevel 1 goto :err

echo.
echo Dependencies installed successfully.
pause
exit /b 0

:err
echo.
echo Install failed.
pause
exit /b 1
