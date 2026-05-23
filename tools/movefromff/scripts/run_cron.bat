@echo off
cd /d "%~dp0\.."
"%~dp0\..\.venv\Scripts\python.exe" -m movefromff --mode cron
exit /b %ERRORLEVEL%
