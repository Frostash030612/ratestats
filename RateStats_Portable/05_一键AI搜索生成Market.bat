@echo off
cd /d "%~dp0"
call "%~dp005_run_ai_search.bat"
exit /b %ERRORLEVEL%
