@echo off
setlocal
cd /d "%~dp0"

set "APP_NAME=AxionPhysicsCodegen"
set "APP_VERSION=1.0.0"
set "DIST_DIR=dist\%APP_NAME%"
set "MSI_PATH=dist\%APP_NAME%-Setup.msi"
set "WXS_FILE=installer\%APP_NAME%.wxs"
set "HARVEST_WXS=installer\AppPayload.wxs"
set "AXION_NO_PAUSE_WAS_SET=%AXION_NO_PAUSE%"

if not defined AXION_NO_PAUSE set "AXION_NO_PAUSE=1"
call "%~dp0build_portable.bat"
if errorlevel 1 (
  echo Portable build step failed, so MSI build cannot continue.
  exit /b 1
)
if not defined AXION_NO_PAUSE_WAS_SET set "AXION_NO_PAUSE="

echo.
echo [Installer] Checking for WiX toolset...
where wix >nul 2>nul
if errorlevel 1 (
  echo WiX toolset not found. Installing via dotnet tool...
  where dotnet >nul 2>nul
  if errorlevel 1 (
    echo dotnet SDK not found. Install .NET 8 SDK from:
    echo   https://dotnet.microsoft.com/download
    pause
    exit /b 1
  )
  dotnet tool install --global wix
  if errorlevel 1 (
    echo Failed to install WiX.
    pause
    exit /b 1
  )
  where wix >nul 2>nul
  if errorlevel 1 (
    echo WiX installed, but not yet on PATH for this shell.
    echo Close this window and re-run build_installer.bat.
    pause
    exit /b 1
  )
)

wix eula accept wix7 >nul 2>nul

echo.
echo [Installer] Generating WiX payload...
python "tools\generate_wix_payload.py" "%DIST_DIR%" "%HARVEST_WXS%"
if errorlevel 1 (
  echo Payload manifest generation failed.
  pause
  exit /b 1
)

echo.
echo [Installer] Building MSI...
wix build ^
  -arch x64 ^
  -d AppVersion=%APP_VERSION% ^
  -d SourceDir="%DIST_DIR%" ^
  -o "%MSI_PATH%" ^
  "%WXS_FILE%" ^
  "%HARVEST_WXS%"

if errorlevel 1 (
  echo WiX build failed.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo Installer build complete.
echo ============================================================
echo   MSI installer: %CD%\%MSI_PATH%
echo ============================================================
if defined AXION_NO_PAUSE goto :eof
pause
exit /b 0
