@echo off
setlocal
cd /d %~dp0
if "%~1"=="" (
  echo Usage:
  echo   run_rewrite.bat "equation text"
  echo Example:
  echo   run_rewrite.bat "1/G_net = Σ_(i=1)^N 1/G_i"
  exit /b 1
)
python -m physics_codegen.cli rewrite --text "%~1"
endlocal
