@echo off
chcp 65001 >nul
pushd "%~dp0"
set "PY=python"
where python >nul 2>&1 || set "PY=py -3"

if not exist "models\url_ranker.joblib" (
  echo 请先运行 01_训练模型.bat
  pause
  exit /b 1
)

echo 在发现报告上网格搜索 blend / min_proba ...
%PY% tune_picker.py
if errorlevel 1 goto :err

echo.
echo 最佳参数已写入 models\picker_tuning.json
goto :done

:err
pause
exit /b 1

:done
pause
popd
exit /b 0
