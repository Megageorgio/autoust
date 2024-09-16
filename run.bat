@ECHO off
cd /D %~dp0
call set_env.bat
python autoust.py
pause