@echo off
setlocal EnableExtensions
set "BIN=%~dp0"
set "SRC=%BIN%..\src"
set "ASSETS=%BIN%..\..\assets"
set "DOCS=%BIN%..\docs"
set "PKG=%BIN%.."
setlocal EnableDelayedExpansion
pushd "%~dp0." 2>nul
if errorlevel 1 (
  echo [06] ERROR: cannot cd to script folder.
  pause
  exit /b 1
)

set "PY_CMD=python"
where python >nul 2>&1
if not errorlevel 1 goto :py_ok
where py >nul 2>&1
if errorlevel 1 goto :no_python
set "PY_CMD=py -3"
:py_ok

if not exist "%ASSETS%\" mkdir "%ASSETS%"

for /f "delims=" %%I in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Date).ToString('yyyyMMdd')"') do set "DATE_TAG=%%I"
for /f "delims=" %%I in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Date).ToString('yyyyMMdd_HH.mm')"') do set "RUN_TAG=%%I"

if not defined DATE_TAG goto :tag_err
if not defined RUN_TAG goto :tag_err

call "%BIN%set_runs_out_dir.bat"
if errorlevel 1 goto :tag_err
set "BASE_OUT_DIR=%OUT_DIR%"
set "OUT_DIR=%BASE_OUT_DIR%\full_pipeline_%RUN_TAG%"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
set "MARKET_OUT=%OUT_DIR%\MarketRateData_%RUN_TAG%.xlsx"
set "MARKET_AI_OUT=%OUT_DIR%\MarketRateData_%RUN_TAG%_AISearch.xlsx"
set "COMPARE_OUT=%OUT_DIR%\market_data_compare_%RUN_TAG%_Vertex.xlsx"
set "EMAIL_CFG=%ASSETS%\email_params.log"

echo ============================================================
echo [06] Part A: Manual url_params - MarketRateData + Rainbow
echo [06] Part B: Vertex AI search - MarketRateData *_AISearch
echo [06] Part C: Compare manual vs Vertex AISearch
echo [06] RUN_TAG=%RUN_TAG%
echo [06] BASE_OUT_DIR=%BASE_OUT_DIR%
echo [06] OUT_DIR=%OUT_DIR%
echo ============================================================
echo.

echo [A0] Sync url_params.xlsx -^> url_params.json ...
call %PY_CMD% "%SRC%\sync_url_params_to_json.py"
if errorlevel 1 goto :err

echo [A1] Generate MarketRateData ...
call %PY_CMD% "%SRC%\market_rate_data_generator.py" --xlsx-out "%MARKET_OUT%"
if errorlevel 1 goto :err

echo [A2] Generate Rainbow workbook ...
call %PY_CMD% "%SRC%\generate_rainbow_from_market.py" --source "%MARKET_OUT%" --out-dir-zh "%OUT_DIR%" --out-tag "%RUN_TAG%"
if errorlevel 1 goto :err

rem 同步一份彩虹表到当日 runs/YYYYMMDD/ 根目录（与 03 批处理输出位置一致）
call %PY_CMD% -c "import shutil; from pathlib import Path; tag='%RUN_TAG%'; src=Path(r'%OUT_DIR%')/f'彩虹表_按MarketRateData更新_{tag}.xlsx'; dst=Path(r'%BASE_OUT_DIR%')/src.name; shutil.copy2(src,dst) if src.is_file() else (_ for _ in ()).throw(FileNotFoundError(src))"
if errorlevel 1 (
  echo [A2] WARN: could not copy rainbow to %BASE_OUT_DIR%
) else (
  echo [A2] Rainbow also copied to: %BASE_OUT_DIR%
)

echo.
echo [B] AI search + MarketRateData AISearch ...
set "OUTPUT_FOLDER=%OUT_DIR%"
set "CALLER_COMBINED=1"
call "%BIN%05_run_ai_search.bat"
set "CALLER_COMBINED="
if errorlevel 1 goto :err

echo.
echo [C] Compare manual vs Vertex AISearch ...
if not exist "%MARKET_OUT%" (
  echo [C] WARN: Manual market missing: %MARKET_OUT%
  goto :skip_compare
)
if not exist "%MARKET_AI_OUT%" (
  echo [C] WARN: AI market missing: %MARKET_AI_OUT%
  goto :skip_compare
)
call %PY_CMD% "%SRC%\compare_vertex_market.py" --manual "%MARKET_OUT%" --ai "%MARKET_AI_OUT%" --out-dir "%OUT_DIR%" --run-tag "%RUN_TAG%"
if errorlevel 1 goto :err

:skip_compare
echo.
if not exist "%BASE_OUT_DIR%\logs" mkdir "%BASE_OUT_DIR%\logs"
set "MAIL_LOG=%BASE_OUT_DIR%\logs\email_last_run.log"
>>"%MAIL_LOG%" echo ---- %DATE% %TIME% [06] DATE_TAG=%DATE_TAG% RUN_TAG=%RUN_TAG% ----

where choice >nul 2>&1
if errorlevel 1 goto :mail_fallback

echo [MAIL] Send email? Y=Yes N=No
choice /C YN /N /M "Send email Y or N? "
set "CH=!errorlevel!"
if !CH! geq 2 (
  echo [MAIL] Skipped.
  goto :mail_done
)
goto :mail_send

:mail_fallback
set "SEND_MAIL="
echo [MAIL] Type Y and Enter to send, or Enter alone to skip.
set /p SEND_MAIL=Send email Y or skip: 
if /I not "!SEND_MAIL!"=="Y" goto :mail_done

:mail_send
echo [MAIL] Sending report email ...
call %PY_CMD% "%SRC%\send_report_email.py" --config-log "%EMAIL_CFG%" --market "%MARKET_OUT%" --market-ai "%MARKET_AI_OUT%" --compare "%COMPARE_OUT%" --rainbow-dir-zh "%OUT_DIR%" --rainbow-tag "%RUN_TAG%" --date-tag "%RUN_TAG%"
if errorlevel 1 echo [MAIL] Send failed. Check %EMAIL_CFG%

:mail_done
echo.
echo [06] All done.
echo   Manual Market: %MARKET_OUT%
echo   AI Market:     %MARKET_AI_OUT%
echo   Compare:       %COMPARE_OUT%
echo   Rainbow:       %OUT_DIR%  (彩虹表_按MarketRateData更新_%RUN_TAG%.xlsx)
echo   Rainbow copy:  %BASE_OUT_DIR%  (同上文件名)
goto :finish

:no_python
echo [06] Python not found. Run 01 installer batch first.
goto :err

:tag_err
echo [06] ERROR: cannot get DATE_TAG / RUN_TAG from PowerShell.
goto :err

:err
echo.
echo [06] Failed.
pause
popd 2>nul
exit /b 1

:finish
pause
popd 2>nul
exit /b 0
