@echo off
setlocal EnableExtensions
title IVX Discord Lab - Launcher
pushd "%~dp0"
if errorlevel 1 goto :bad_folder
set "PYTHONUTF8=1"

echo.
echo  =============================================
echo        IVX DISCORD LAB - DESKTOP LAUNCHER
echo  =============================================
echo.

if not exist "app.py" goto :missing_app
if not exist "requirements.txt" goto :missing_requirements
if not exist "bootstrap.py" goto :missing_bootstrap

where py >nul 2>&1
if errorlevel 1 goto :try_python_command
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto :try_python_command
py -3 "bootstrap.py"
goto :capture_exit

:try_python_command
where python >nul 2>&1
if errorlevel 1 goto :try_fixed_path
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto :try_fixed_path
python "bootstrap.py"
goto :capture_exit

:try_fixed_path
call :find_python
if errorlevel 1 goto :no_python
"%BOOTSTRAP_PY%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto :python_too_old
"%BOOTSTRAP_PY%" "bootstrap.py"
goto :capture_exit

:capture_exit
set "APP_EXIT=%ERRORLEVEL%"
goto :finish

:finish
echo.
if not "%APP_EXIT%"=="0" (
    echo The launcher or desktop app exited with error code %APP_EXIT%.
    echo If a setup window appeared, review its error details before trying again.
) else (
    echo IVX Discord Lab has closed.
)
echo.
pause
popd
exit /b %APP_EXIT%

:no_python
echo [ERROR] Python 3.10 or newer was not found.
echo Install Python from https://www.python.org/downloads/windows/
echo During setup, enable the option to add Python to PATH, then run this file again.
goto :stop_error

:python_too_old
echo [ERROR] The selected Python version is older than Python 3.10.
echo Install Python 3.10 or newer, then run this file again.
goto :stop_error

:missing_app
echo [ERROR] app.py was not found.
echo Extract the complete repository ZIP and run this launcher from the project folder.
goto :stop_error

:missing_requirements
echo [ERROR] requirements.txt was not found.
echo Extract the complete repository ZIP and run this launcher from the project folder.
goto :stop_error

:missing_bootstrap
echo [ERROR] bootstrap.py was not found.
echo Download and extract the complete latest repository ZIP before launching.
goto :stop_error

:bad_folder
echo [ERROR] Could not open the folder containing this launcher.
goto :stop_error

:stop_error
echo.
pause
exit /b 1

:find_python
if defined LOCALAPPDATA (
    for %%V in (314 313 312 311 310) do (
        if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
            set "BOOTSTRAP_PY=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
            exit /b 0
        )
    )
)
exit /b 1
