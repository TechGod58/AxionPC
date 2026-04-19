@echo off
setlocal enabledelayedexpansion

REM Always run from this folder
cd /d "%~dp0"

title physics_codegen GUI launcher

echo === physics_codegen GUI launcher ===
echo Folder: %CD%
echo.

REM Prefer the Python Launcher (py) on Windows, fallback to python.
set "PY_CMD="

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY_CMD=py -3"
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    set "PY_CMD=python"
  )
)

if "%PY_CMD%"=="" (
  echo ERROR: Could not find Python.
  echo Install Python 3.11+ and ensure "py" or "python" is on PATH.
  echo.
  pause
  exit /b 2
)

echo Using: %PY_CMD%
%PY_CMD% -c "import sys; print('Python:', sys.version); print('Exe:', sys.executable)"
echo.

REM Run doctor first so any path/import issues are visible
echo --- Doctor (import check) ---
%PY_CMD% -m physics_codegen.cli doctor
echo.

echo --- Launching GUI ---
%PY_CMD% -m physics_codegen.cli gui

echo.
echo If the GUI crashed, the traceback should be above.
pause
