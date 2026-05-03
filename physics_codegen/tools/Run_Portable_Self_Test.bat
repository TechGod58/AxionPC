@echo off
setlocal
cd /d "%~dp0"

if not exist "AxionPhysicsCodegen.exe" (
  echo AxionPhysicsCodegen.exe was not found in this folder.
  echo Build a portable bundle first using build_portable.bat.
  pause
  exit /b 1
)

"%~dp0AxionPhysicsCodegen.exe" --self-test
set "RESULT=%ERRORLEVEL%"

echo.
if exist "%~dp0userdata\portable_self_test.json" (
  echo Portable self-test report:
  echo %~dp0userdata\portable_self_test.json
  echo.
  type "%~dp0userdata\portable_self_test.json"
) else (
  echo Self-test report was not created.
)

echo.
if "%RESULT%"=="0" (
  echo Portable self-test PASSED.
) else (
  echo Portable self-test FAILED with exit code %RESULT%.
)
pause
exit /b %RESULT%
