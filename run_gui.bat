@echo off
setlocal
cd /d "%~dp0"

set "PYW_CMD="

where pyw >nul 2>nul
if %errorlevel%==0 (
  set "PYW_CMD=pyw -3"
) else (
  where pythonw >nul 2>nul
  if %errorlevel%==0 (
    set "PYW_CMD=pythonw"
  )
)

if "%PYW_CMD%"=="" (
  echo Could not find pythonw/pyw for windowless launch.
  echo Use run_doctor.bat to troubleshoot Python setup.
  echo.
  pause
  exit /b 2
)

%PYW_CMD% -m physics_codegen.cli gui
endlocal
exit /b 0
