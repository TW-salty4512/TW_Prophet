@echo off
rem Local launcher sample for this machine only.
rem Copy this file to "start_tw_prophet_web.local.bat" and edit paths.

rem # CHANGEPOINT Development sample
cd /d "C:\Users\tsalt\Dev\TW_Prophet\project"
"C:\Users\tsalt\anaconda3\envs\tw_prophet_web\python.exe" run_web.py

rem # CHANGEPOINT Production sample (mapped local path)
rem cd /d "C:\data\TW_Prophet"
rem "C:\Users\techw\anaconda3\envs\tw_prophet_web\python.exe" run_web.py

echo [INFO] Copy this file to start_tw_prophet_web.local.bat and edit it.
exit /b 1
