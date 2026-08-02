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

echo [2/5] RateStats_Portable 依赖...
%PY_CMD% -m pip install -r "%DOCS%\requirements.txt"
if errorlevel 1 goto :err

echo [3/5] RateStats_ML 依赖...
%PY_CMD% -m pip install -r "..\..\RateStats_ML\requirements.txt"
if errorlevel 1 goto :err

echo [4/5] AI_Compare 依赖...
%PY_CMD% -m pip install -r "..\..\AI_Compare\requirements.txt"
if errorlevel 1 goto :err

echo [5/5] 确保 curl_cffi 已安装...
%PY_CMD% -m pip install "curl_cffi>=0.7.0"
if errorlevel 1 goto :err

echo.
echo 全部依赖安装完成（手动 / Vertex AI / ML 选链）。
echo.
echo 常用入口：
echo   03_一键生成Market+彩虹表.bat          手动 url_params
echo   06_一键生成Market彩虹表与AI搜索.bat    手动 + Vertex AI
echo   ..\RateStats_ML\03_Vertex_ML发现并抓取.bat   ML 选链 + 抓取
pause
exit /b 0

:err
echo.
echo Install failed.
pause
exit /b 1
