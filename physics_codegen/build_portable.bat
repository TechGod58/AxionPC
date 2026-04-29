@echo off
setlocal
cd /d "%~dp0"

set "APP_NAME=AxionPhysicsCodegen"
set "DIST_DIR=dist\%APP_NAME%"
set "ZIP_PATH=dist\%APP_NAME%_portable.zip"

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
echo [1/2] Building portable Windows bundle...
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
  echo Portable build failed.
  pause
  exit /b 1
)

if not exist "%DIST_DIR%" (
  echo Build completed but output folder was not found: %DIST_DIR%
  pause
  exit /b 1
)

copy /Y "README.txt" "%DIST_DIR%\README.txt" >nul
copy /Y "tools\Run_PhysicsCodegen.bat" "%DIST_DIR%\Run_PhysicsCodegen.bat" >nul

echo.
echo [2/2] Creating portable zip...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-ChildItem -Path '%DIST_DIR%' -Recurse | Unblock-File; Compress-Archive -Path '%DIST_DIR%\*' -DestinationPath '%ZIP_PATH%' -Force"
if errorlevel 1 (
  echo Portable bundle built, but zip creation failed.
  echo Folder: %CD%\%DIST_DIR%
  pause
  exit /b 0
)

echo.
echo ============================================================
echo Portable build complete.
echo ============================================================
echo   Portable folder: %CD%\%DIST_DIR%
echo   Portable zip:    %CD%\%ZIP_PATH%
echo.
echo No installation is required.
echo Users can run:
echo   Run_PhysicsCodegen.bat
echo or:
echo   AxionPhysicsCodegen.exe
echo ============================================================
if defined AXION_NO_PAUSE goto :eof
pause
exit /b 0
