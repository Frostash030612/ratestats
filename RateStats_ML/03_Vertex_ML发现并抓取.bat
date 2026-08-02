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

for /f "delims=" %%I in ('powershell -NoProfile -Command "(Get-Date).ToString('yyyyMMdd_HH.mm')"') do set "TAG=%%I"

for /f "delims=" %%I in ('powershell -NoProfile -Command "(Get-Date).ToString('yyyyMMdd')"') do set "DATE_TAG=%%I"
set "RUN_TAG=%TAG%"
echo Vertex + ML 选链，输出到 ..\runs\%DATE_TAG% 或 runs\%%RUN_TAG%%
%PY% run_vertex_ml_discovery.py --run-tag %DATE_TAG% --fetch
if errorlevel 1 goto :err

echo.
echo 完成: ..\runs\%DATE_TAG%\url_params_ai_ml.xlsx
goto :done

:err
pause
exit /b 1

:done
pause
popd
exit /b 0
