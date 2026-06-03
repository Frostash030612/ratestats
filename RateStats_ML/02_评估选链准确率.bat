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

%PY% evaluate_picker.py --reports-dir "..\RateStats_Portable\assets"
if errorlevel 1 goto :err

echo.
echo 报告在 output\picker_eval_*.xlsx
goto :done

:err
pause
exit /b 1

:done
pause
popd
exit /b 0
