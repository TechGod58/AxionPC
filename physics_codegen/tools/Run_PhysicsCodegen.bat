@echo off
setlocal
cd /d "%~dp0"

if not exist "AxionPhysicsCodegen.exe" (
  echo AxionPhysicsCodegen.exe was not found in this folder.
  echo Build a portable bundle first using build_portable.bat.
  pause
  exit /b 1
)

start "" "%~dp0AxionPhysicsCodegen.exe"
exit /b 0
