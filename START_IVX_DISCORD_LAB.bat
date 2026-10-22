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

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating a local Python environment...
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv ".venv"
    ) else (
        where python >nul 2>&1
        if not errorlevel 1 (
            python -m venv ".venv"
        ) else (
            call :find_python
            if errorlevel 1 goto :no_python
            "%BOOTSTRAP_PY%" -m venv ".venv"
        )
    )
    if errorlevel 1 goto :venv_failed
)

".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto :python_too_old

".venv\Scripts\python.exe" -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo [2/3] Installing desktop requirements. This may take a few minutes on first launch...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "requirements.txt"
    if errorlevel 1 goto :install_failed
) else (
    echo [2/3] Desktop requirements are already installed.
)

echo [3/3] Launching IVX Discord Lab...
echo.
".venv\Scripts\python.exe" "app.py"
set "APP_EXIT=%ERRORLEVEL%"
echo.
if not "%APP_EXIT%"=="0" (
    echo The app closed with an error code: %APP_EXIT%
    echo If you need help, copy the error output above.
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

:venv_failed
echo [ERROR] Could not create the local .venv environment.
echo Check your Python installation and folder permissions.
goto :stop_error

:install_failed
echo [ERROR] Dependency installation failed.
echo Check your internet connection and the output above, then run this file again.
goto :stop_error

:missing_app
echo [ERROR] app.py was not found.
echo Extract the complete repository ZIP and run this launcher from the project folder.
goto :stop_error

:missing_requirements
echo [ERROR] requirements.txt was not found.
echo Extract the complete repository ZIP and run this launcher from the project folder.
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
    for %%V in (313 312 311 310) do (
        if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
            set "BOOTSTRAP_PY=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
            exit /b 0
        )
    )
)
exit /b 1
