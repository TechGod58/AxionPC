@echo off
setlocal
cd /d "%~dp0"

set "PORTABLE_EXE=%~dp0physics_codegen\dist\AxionPhysicsCodegen\AxionPhysicsCodegen.exe"
if exist "%PORTABLE_EXE%" (
  start "" "%PORTABLE_EXE%"
  exit /b 0
)

if exist "%~dp0physics_codegen\physics_codegen\cli.py" (
  cd /d "%~dp0physics_codegen"
)

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
  echo Build the portable app with physics_codegen\build_portable.bat.
  echo Use run_doctor.bat to troubleshoot source-mode Python setup.
  echo.
  pause
  exit /b 2
)

%PYW_CMD% -m physics_codegen.cli gui
endlocal
exit /b 0
