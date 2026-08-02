@echo off
setlocal EnableExtensions
set "BIN=%~dp0"
set "SRC=%BIN%..\src"
set "ASSETS=%BIN%..\..\assets"
set "DOCS=%BIN%..\docs"
set "PKG=%BIN%.."
rem 定时任务专用：手动 Market + 彩虹表 + Vertex AI 发现抓取 + 对比 + 自动发邮件（无 pause）
setlocal EnableDelayedExpansion
pushd "%~dp0." 2>nul
if errorlevel 1 exit /b 1

set "PY_CMD=python"
where python >nul 2>&1
if errorlevel 1 (
  where py >nul 2>&1
  if errorlevel 1 exit /b 1
  set "PY_CMD=py -3"
)

if not exist "%ASSETS%\" mkdir "%ASSETS%"

for /f "delims=" %%I in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Date).ToString('yyyyMMdd')"') do set "DATE_TAG=%%I"
for /f "delims=" %%I in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Date).ToString('yyyyMMdd_HH.mm')"') do set "RUN_TAG=%%I"
if not defined DATE_TAG exit /b 1
if not defined RUN_TAG exit /b 1

call "%BIN%set_runs_out_dir.bat"
if errorlevel 1 exit /b 1

set "MARKET_OUT=%OUT_DIR%\MarketRateData_%RUN_TAG%.xlsx"
set "MARKET_AI_OUT=%OUT_DIR%\MarketRateData_%RUN_TAG%_AISearch.xlsx"
set "COMPARE_OUT=%OUT_DIR%\market_data_compare_%RUN_TAG%_Vertex.xlsx"
set "EMAIL_CFG=%ASSETS%\email_params.log"
set "LOG=%OUT_DIR%\scheduled_run_%RUN_TAG%.log"

echo ============================================================ > "%LOG%"
echo [SCHEDULED] %DATE% %TIME% RUN_TAG=%RUN_TAG% >> "%LOG%"
echo [SCHEDULED] OUT_DIR=%OUT_DIR% >> "%LOG%"
echo ============================================================ >> "%LOG%"

echo [A0] sync url_params >> "%LOG%"
call %PY_CMD% "%SRC%\sync_url_params_to_json.py" >> "%LOG%" 2>&1
if errorlevel 1 goto :err

echo [A1] manual MarketRateData >> "%LOG%"
call %PY_CMD% "%SRC%\market_rate_data_generator.py" --xlsx-out "%MARKET_OUT%" >> "%LOG%" 2>&1
if errorlevel 1 goto :err

echo [A2] rainbow >> "%LOG%"
call %PY_CMD% "%SRC%\generate_rainbow_from_market.py" --source "%MARKET_OUT%" --out-dir-zh "%OUT_DIR%" --out-tag "%RUN_TAG%" >> "%LOG%" 2>&1
if errorlevel 1 goto :err

echo [B] Vertex AI discover + fetch >> "%LOG%"
set "OUTPUT_FOLDER=%OUT_DIR%"
set "RUN_TAG=%RUN_TAG%"
set "CALLER_COMBINED=1"
call %PY_CMD% "%SRC%\run_market_rate_ai_search.py" --output-folder "%OUT_DIR%" --run-tag "%RUN_TAG%" >> "%LOG%" 2>&1
set "CALLER_COMBINED="
if errorlevel 1 goto :err

if not exist "%MARKET_AI_OUT%" goto :err

echo [C] compare manual vs AI >> "%LOG%"
call %PY_CMD% "%SRC%\compare_vertex_market.py" --manual "%MARKET_OUT%" --ai "%MARKET_AI_OUT%" --out-dir "%OUT_DIR%" --run-tag "%RUN_TAG%" >> "%LOG%" 2>&1
if errorlevel 1 goto :err

echo [D] send email (manual + AI + compare + rainbow) >> "%LOG%"
call %PY_CMD% "%SRC%\send_report_email.py" --config-log "%EMAIL_CFG%" --market "%MARKET_OUT%" --market-ai "%MARKET_AI_OUT%" --compare "%COMPARE_OUT%" --rainbow-dir-zh "%OUT_DIR%" --rainbow-tag "%RUN_TAG%" --date-tag "%RUN_TAG%" >> "%LOG%" 2>&1
if errorlevel 1 echo [MAIL] send failed, see log >> "%LOG%"

echo [OK] finished %DATE% %TIME% >> "%LOG%"
popd 2>nul
exit /b 0

:err
echo [FAIL] exit %errorlevel% at %DATE% %TIME% >> "%LOG%"
popd 2>nul
exit /b 1
