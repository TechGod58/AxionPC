@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "APP_NAME=AxionPhysicsCodegen"
set "APP_VERSION=1.0.0"
set "DIST_DIR=dist\%APP_NAME%"
set "MSI_PATH=dist\%APP_NAME%-Setup.msi"
set "ZIP_PATH=dist\%APP_NAME%_portable.zip"
set "WXS_FILE=installer\%APP_NAME%.wxs"
set "HARVEST_WXS=installer\AppPayload.wxs"

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not available in PATH.
  echo Install Python 3.11+ and run this script again.
  pause
  exit /b 1
)

python -c "import PyInstaller" 1>nul 2>nul
if errorlevel 1 (
  echo Installing PyInstaller...
  python -m pip install --upgrade pyinstaller
  if errorlevel 1 (
    echo Failed to install PyInstaller.
    pause
    exit /b 1
  )
)

echo.
echo [1/4] Building PyInstaller bundle...
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name "%APP_NAME%" ^
  --hidden-import=tkinter ^
  --exclude-module torch ^
  --exclude-module tensorflow ^
  --exclude-module sklearn ^
  --exclude-module cv2 ^
  --exclude-module PIL ^
  --exclude-module matplotlib ^
  --exclude-module pandas ^
  --exclude-module scipy ^
  --exclude-module transformers ^
  --add-data "physics_codegen\data;physics_codegen\data" ^
  "tools\windows_gui_entry.py"

if errorlevel 1 (
  echo PyInstaller build failed.
  pause
  exit /b 1
)

if not exist "%DIST_DIR%" (
  echo Build completed but output folder was not found: %DIST_DIR%
  pause
  exit /b 1
)

copy /Y "README.txt" "%DIST_DIR%\README.txt" >nul

echo.
echo [2/4] Creating portable zip...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-ChildItem -Path '%DIST_DIR%' -Recurse | Unblock-File; Compress-Archive -Path '%DIST_DIR%\*' -DestinationPath '%ZIP_PATH%' -Force"
if errorlevel 1 (
  echo Warning: portable zip creation failed. MSI build will still be attempted.
)

echo.
echo [3/4] Checking for WiX toolset...
where wix >nul 2>nul
if errorlevel 1 (
  echo WiX toolset not found. Installing via dotnet tool...
  where dotnet >nul 2>nul
  if errorlevel 1 (
    echo dotnet SDK not found. Install .NET 8 SDK from:
    echo   https://dotnet.microsoft.com/download
    echo Then run this script again.
    pause
    exit /b 1
  )
  dotnet tool install --global wix
  if errorlevel 1 (
    echo Failed to install WiX. You can install manually with:
    echo   dotnet tool install --global wix
    pause
    exit /b 1
  )
  where wix >nul 2>nul
  if errorlevel 1 (
    echo WiX installed, but not yet on PATH for this shell.
    echo Close this window and re-run build_portable.bat.
    pause
    exit /b 1
  )
)

wix eula accept wix7 >nul 2>nul

echo.
echo [4/4] Building MSI installer...

if not exist "installer" mkdir "installer"

python "tools\generate_wix_payload.py" "%DIST_DIR%" "%HARVEST_WXS%"

if errorlevel 1 (
  echo Payload manifest generation failed.
  pause
  exit /b 1
)

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
echo Build complete.
echo ============================================================
echo   MSI installer (primary):  %CD%\%MSI_PATH%
echo   Portable folder:          %CD%\%DIST_DIR%
echo   Portable zip (secondary): %CD%\%ZIP_PATH%
echo.
echo To distribute: share the MSI. Users double-click to install.
echo Launches from Start Menu as "Axion Physics Codegen" with no
echo console window and no batch file in the shortcut path.
echo ============================================================
pause
exit /b 0
