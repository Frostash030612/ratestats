@echo off

setlocal EnableDelayedExpansion

pushd "%~dp0." 2>nul



set "PY_CMD=python"

where python >nul 2>&1

if not errorlevel 1 goto :py_ok

where py >nul 2>&1

if errorlevel 1 (

  echo [AI_Compare] Python not found.

  pause

  popd 2>nul

  exit /b 1

)

set "PY_CMD=py -3"

:py_ok



if not exist "results\" mkdir "results"

if not exist "raw_cache\" mkdir "raw_cache"



set "LOG=%CD%\results\run_eval_last.log"

echo ---- %DATE% %TIME% ---->>"%LOG%"



REM 第一个参数: auto | list | vertex,serper,...  留空则 --auto

set "MODE=%~1"

if "%MODE%"=="" set "MODE=auto"



echo [AI_Compare] pip install ...

call %PY_CMD% -m pip install -r requirements.txt -q >>"%LOG%" 2>&1



if /I "%MODE%"=="list" (

  call %PY_CMD% run_eval.py --list

  pause

  popd 2>nul

  exit /b 0

)



if /I "%MODE%"=="auto" (

  echo [AI_Compare] run_eval.py --auto ...

  call %PY_CMD% run_eval.py --auto >>"%LOG%" 2>&1

) else (

  echo [AI_Compare] run_eval.py --providers %MODE% ...

  call %PY_CMD% run_eval.py --providers "%MODE%" >>"%LOG%" 2>&1

)



if errorlevel 1 (

  echo [AI_Compare] Failed. See %LOG%

  pause

  popd 2>nul

  exit /b 1

)



echo [AI_Compare] Done. Report in results\

echo [AI_Compare] Log: %LOG%

pause

popd 2>nul

exit /b 0

