param([string]$Name = 'CodexWindowStarter')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m PyInstaller --noconfirm --clean --onefile --windowed --name $Name --hidden-import win32com.client app.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败，退出码 $LASTEXITCODE" }
Write-Host "已生成: $PSScriptRoot\dist\$Name.exe"
