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
  echo [03] ERROR: cannot cd to script folder.
  pause
  exit /b 1
)
chcp 65001 >nul

if not exist "%ASSETS%\" mkdir "%ASSETS%"

set "PY_CMD=python"
where python >nul 2>nul
if errorlevel 1 (
  where py >nul 2>nul
  if errorlevel 1 (
    echo [03] Python not found in PATH.
    popd 2>nul
    pause
    exit /b 1
  )
  set "PY_CMD=py -3"
)

echo [0/2] Sync url_params.xlsx -^> url_params.json...
%PY_CMD% "%SRC%\sync_url_params_to_json.py"
if errorlevel 1 (
  echo [03] URL params sync failed. Check assets\url_params.xlsx
  popd 2>nul
  pause
  exit /b 1
)

for /f "delims=" %%I in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Date).ToString('yyyyMMdd')"') do set "DATE_TAG=%%I"
for /f "delims=" %%I in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Date).ToString('yyyyMMdd_HH.mm')"') do set "RUN_TAG=%%I"

if not defined DATE_TAG (
  echo [03] ERROR: DATE_TAG empty. PowerShell date failed.
  popd 2>nul
  pause
  exit /b 1
)
if not defined RUN_TAG (
  echo [03] ERROR: RUN_TAG empty. PowerShell date failed.
  popd 2>nul
  pause
  exit /b 1
)

call "%BIN%set_runs_out_dir.bat"
if errorlevel 1 (
  echo [03] ERROR: cannot set runs output dir.
  popd 2>nul
  pause
  exit /b 1
)

set "MARKET_OUT=%OUT_DIR%\MarketRateData_%RUN_TAG%.xlsx"
rem Rainbow Chinese filename is built inside Python (--out-dir-zh / --out-tag).
set "EMAIL_CFG=%ASSETS%\email_params.log"

echo [1/2] Generate MarketRateData...
%PY_CMD% "%SRC%\market_rate_data_generator.py" --xlsx-out "%MARKET_OUT%"
if errorlevel 1 (
  echo [03] MarketRateData step failed.
  popd 2>nul
  pause
  exit /b 1
)

echo [2/2] Generate Rainbow workbook...
%PY_CMD% "%SRC%\generate_rainbow_from_market.py" --source "%MARKET_OUT%" --out-dir-zh "%OUT_DIR%" --out-tag "%RUN_TAG%"
if errorlevel 1 (
  echo [03] Rainbow step failed.
  popd 2>nul
  pause
  exit /b 1
)

echo.
if not exist "%OUT_DIR%\logs" mkdir "%OUT_DIR%\logs"
set "MAIL_LOG=%OUT_DIR%\logs\email_last_run.log"
>>"%MAIL_LOG%" echo ---- %DATE% %TIME% DATE_TAG=%DATE_TAG% RUN_TAG=%RUN_TAG% ----

where choice >nul 2>nul
if errorlevel 1 goto :mail_fallback

echo [MAIL] Send email? Y=Yes N=No
choice /C YN /N /M "Send email Y or N? "
set "CH=!errorlevel!"
echo choice_errorlevel=!CH! >>"%MAIL_LOG%"
if !CH! geq 2 (
  echo result=skipped >>"%MAIL_LOG%"
  echo [MAIL] Skipped.
  goto :mail_done
)
goto :mail_send

:mail_fallback
set "SEND_MAIL="
echo [MAIL] Type Y and Enter to send, or Enter alone to skip.
set /p SEND_MAIL=Send email Y or skip: 
echo setp_reply=!SEND_MAIL! >>"%MAIL_LOG%"
if /I not "!SEND_MAIL!"=="Y" (
  echo result=skipped >>"%MAIL_LOG%"
  echo [MAIL] Skipped.
  goto :mail_done
)

:mail_send
echo result=attempt_send >>"%MAIL_LOG%"
echo [MAIL] Sending report email...
%PY_CMD% "%SRC%\send_report_email.py" --config-log "%EMAIL_CFG%" --market "%MARKET_OUT%" --rainbow-dir-zh "%OUT_DIR%" --rainbow-tag "%RUN_TAG%" --date-tag "%RUN_TAG%"
if errorlevel 1 (
  echo result=send_failed >>"%MAIL_LOG%"
  echo [MAIL] Send failed. Check: %EMAIL_CFG%
  echo [MAIL] Log: %MAIL_LOG%
) else (
  echo result=send_ok >>"%MAIL_LOG%"
  echo [MAIL] Send success.
)

:mail_done
echo [MAIL] Last run log: %MAIL_LOG%

echo.
echo All done. Output folder: %OUT_DIR%
echo Rainbow: OUT_DIR=%OUT_DIR% TAG=%RUN_TAG% ^(Chinese name built inside Python^)
pause
popd 2>nul
exit /b 0
