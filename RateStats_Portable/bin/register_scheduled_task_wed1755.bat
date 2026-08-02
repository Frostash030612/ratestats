@echo off
setlocal EnableExtensions
set "BIN=%~dp0"
set "SRC=%BIN%..\src"
set "ASSETS=%BIN%..\..\assets"
set "DOCS=%BIN%..\docs"
set "PKG=%BIN%.."
rem 注册 Windows 计划任务：每周三 17:55 跑 run_scheduled_full_pipeline.bat
chcp 65001 >nul
setlocal

set "TASK_NAME=RateStats_FullPipeline_Wed1755"
set "SCRIPT=%~dp0run_scheduled_full_pipeline.bat"

echo 任务名: %TASK_NAME%
echo 脚本:   %SCRIPT%
echo 时间:   每周三 17:55
echo.

schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if not errorlevel 1 (
  echo 已存在同名任务，先删除再重建...
  schtasks /delete /tn "%TASK_NAME%" /f
)
schtasks /query /tn "RateStats_FullPipeline_1800" >nul 2>&1
if not errorlevel 1 (
  echo 删除旧任务 RateStats_FullPipeline_1800 ...
  schtasks /delete /tn "RateStats_FullPipeline_1800" /f
)

schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%SCRIPT%\"" ^
  /sc weekly ^
  /d WED ^
  /st 17:55 ^
  /rl LIMITED ^
  /f

if errorlevel 1 (
  echo [ERROR] 注册失败。可尝试「以管理员身份运行」本 bat。
  pause
  exit /b 1
)

echo.
echo [OK] 计划任务已创建。
echo 查看: schtasks /query /tn "%TASK_NAME%" /v /fo list
echo 立即试跑: schtasks /run /tn "%TASK_NAME%"
echo 删除: schtasks /delete /tn "%TASK_NAME%" /f
echo.
pause
