@echo off
setlocal
cd /d "%~dp0"
title physics_codegen doctor
echo === physics_codegen doctor ===
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -m physics_codegen.cli doctor
) else (
  python -m physics_codegen.cli doctor
)
pause
