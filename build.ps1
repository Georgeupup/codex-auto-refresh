param([string]$Name = 'CodexWindowStarter')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m PyInstaller --noconfirm --clean --onefile --windowed --name $Name --icon "$PSScriptRoot\assets\logo.ico" --add-data "$PSScriptRoot\assets\logo.png;assets" --add-data "$PSScriptRoot\assets\logo_32.png;assets" --add-data "$PSScriptRoot\assets\logo.ico;assets" --hidden-import win32com.client app.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败，退出码 $LASTEXITCODE" }
Write-Host "已生成: $PSScriptRoot\dist\$Name.exe"
