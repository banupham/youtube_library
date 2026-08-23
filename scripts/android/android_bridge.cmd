@echo off
setlocal
python "%~dp0android_bridge.py" %*
exit /b %ERRORLEVEL%
