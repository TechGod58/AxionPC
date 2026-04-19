@echo off
setlocal
cd /d %~dp0
python -c "import sympy, numpy, yaml" 1>nul 2>nul
if errorlevel 1 (
  echo Missing required Python packages.
  echo Run: python -m pip install -r requirements.txt
  echo.
  pause
  endlocal
  exit /b 1
)
python -m physics_codegen.cli gui
if errorlevel 1 (
  echo.
  echo GUI exited with errorlevel %errorlevel%.
  pause
)
endlocal
