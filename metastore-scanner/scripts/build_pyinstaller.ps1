# Build a standalone metastore-scanner executable (requires PyInstaller).
# Usage (from metastore-scanner/): pip install pyinstaller; .\scripts\build_pyinstaller.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Host "Install PyInstaller first: pip install pyinstaller"
    exit 1
}

pyinstaller --onefile --name metastore-scanner `
    --collect-all scanner `
    main.py

Write-Host "Output under .\dist\metastore-scanner.exe (Windows) or dist/metastore-scanner (POSIX)"
