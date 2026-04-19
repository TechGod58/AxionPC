# AxionPhysicsCodegen MSI Installer

## What changed

These installer-related files now live in the repo:

| File | Purpose |
|------|---------|
| `tools/windows_gui_entry.py` | Windowed entrypoint with crash logging and error dialogs |
| `build_portable.bat` | Builds the PyInstaller app, portable zip, and MSI installer |
| `installer/AxionPhysicsCodegen.wxs` | WiX source for the MSI |

The `tools/Run_PhysicsCodegen.bat` file still supports the portable zip path, but the MSI shortcut points directly to the `.exe`.

## First-time build machine setup

Install the .NET 8 SDK on the build machine:

- [https://dotnet.microsoft.com/download/dotnet/8.0](https://dotnet.microsoft.com/download/dotnet/8.0)

Then install the WiX toolset:

```powershell
dotnet tool install --global wix
```

Verify with:

```powershell
wix --version
```

`build_portable.bat` will try to install WiX automatically if it is missing, but you may need to reopen the terminal afterward so the new PATH is available.

## Running the build

From the `physics_codegen` project root:

```powershell
build_portable.bat
```

This produces three outputs in `dist\`:

1. `AxionPhysicsCodegen-Setup.msi`
2. `AxionPhysicsCodegen\`
3. `AxionPhysicsCodegen_portable.zip`

## What the user sees

1. The user downloads `AxionPhysicsCodegen-Setup.msi`.
2. The user double-clicks the MSI.
3. Windows Installer runs a per-user install into `%LOCALAPPDATA%\Programs\AxionPhysicsCodegen\`.
4. A Start Menu shortcut is created for `Axion Physics Codegen`.
5. Launching the shortcut opens the GUI directly with no batch file and no console window.

Uninstall works through Windows Settings -> Apps -> Installed apps.

## Smart App Control

Smart App Control can still warn on first run if neither the MSI nor the EXE is code-signed.

Options:

1. On your own machines, unblock the downloaded MSI once through file Properties.
2. For broader distribution, sign both the EXE and the MSI with a trusted signing service or code-signing certificate.

## What each piece does

### `tools/windows_gui_entry.py`

This entrypoint logs startup failures to:

- `%LOCALAPPDATA%\AxionPhysicsCodegen\error.log`

It also shows a Tk message box if a startup exception occurs in a `--windowed` build.

### `installer/AxionPhysicsCodegen.wxs`

- Uses `Scope="perUser"` so the install does not require admin rights.
- Uses `MajorUpgrade` so future versions replace older ones automatically.
- Creates a Start Menu shortcut pointing directly at `AxionPhysicsCodegen.exe`.
- Works with the repo's payload generator so the MSI file list stays in sync with the PyInstaller output.

### `build_portable.bat`

The build runs in four stages:

1. Build the PyInstaller bundle
2. Create the portable zip
3. Verify or install WiX
4. Generate the WiX payload file and build the MSI

## Verify it worked

After installing via MSI:

- Start Menu contains `Axion Physics Codegen`
- The shortcut target is the `.exe`, not a `.bat`
- Launching it opens only the GUI window
- `%LOCALAPPDATA%\AxionPhysicsCodegen\error.log` shows a startup log line
- Windows Settings shows the app with working uninstall support
