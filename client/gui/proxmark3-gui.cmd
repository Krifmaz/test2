@echo off
rem Launch Proxmark3 Studio on Windows. Installs PySide6 on first run.
rem Usage: proxmark3-gui.cmd [--client C:\ProxSpace\pm3\test2\client\proxmark3.exe] [--port COM5]
setlocal
cd /d "%~dp0"

set "PY=py -3"
%PY% --version >nul 2>&1 || set "PY=python"
%PY% --version >nul 2>&1 || (
    echo Python 3 was not found. Install it from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" during setup.
    pause
    exit /b 1
)

%PY% -c "import PySide6" >nul 2>&1 || (
    echo Installing PySide6 ^(first run only^)...
    %PY% -m pip install --user -r requirements.txt || (
        echo PySide6 install failed.
        pause
        exit /b 1
    )
)

%PY% -m pm3gui %*
if errorlevel 1 pause
