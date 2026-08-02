@echo off
setlocal EnableExtensions
set "BIN=%~dp0"
set "SRC=%BIN%..\src"
set "ASSETS=%BIN%..\..\assets"
set "DOCS=%BIN%..\docs"
set "PKG=%BIN%.."
cd /d "%BIN%"
call "%BIN%05_run_ai_search.bat"
exit /b %ERRORLEVEL%
