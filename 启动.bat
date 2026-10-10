@echo off
chcp 65001 >nul
setlocal
set HERE=%~dp0
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

rem 优先用项目配置里的解释器（.workbuddy 那套），其次 PATH 上的 python
set PY=python
set CAND=%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe
if exist "%CAND%" set PY=%CAND%

"%PY%" "%HERE%启动器.py" %*
set RC=%ERRORLEVEL%
if not "%RC%"=="0" (
  echo.
  echo 退出码 %RC%。若启动失败，可直接用命令行：
  echo     python -m clipkit --help
  pause
)
endlocal
