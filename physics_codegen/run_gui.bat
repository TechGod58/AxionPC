@echo off
setlocal
cd /d "%~dp0"

python -c "import sympy, numpy, yaml" 1>nul 2>nul
if errorlevel 1 (
  echo Missing required Python packages.
  echo Run: python -m pip install -r requirements.txt
  echo.
  pause
  endlocal
  exit /b 1
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
  echo Use python -m physics_codegen.cli gui if you need console output.
  echo.
  pause
  endlocal
  exit /b 2
)

%PYW_CMD% -m physics_codegen.cli gui
endlocal
exit /b 0
