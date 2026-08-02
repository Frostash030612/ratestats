@echo off
chcp 65001 >nul
pushd "%~dp0"
set "PY=python"
where python >nul 2>&1 || set "PY=py -3"

echo [1/2] pip install -r requirements.txt ...
%PY% -m pip install -r requirements.txt -q

echo [2/2] train.py （含 runs 发现报告 + 典型错链负样本）...
%PY% train.py --use-discovery
if errorlevel 1 goto :err

echo.
echo 完成。模型在 models\url_ranker.joblib
goto :done

:err
echo 训练失败
pause
exit /b 1

:done
pause
popd
exit /b 0
