# Кадры игры без окна: .\shots.ps1 <папка> <сцена1> <сцена2> ...  (сцена — JS-код страницы; собирает игру заново)
param([string]$Out, [Parameter(ValueFromRemainingArguments = $true)][string[]]$Scenes)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:Path = "Y:\tools\node;$env:Path"
node build.js | Select-Object -Last 1
$cfg = Join-Path $env:TEMP 'zn_shots.json'
@{ out = $Out; scenes = $Scenes } | ConvertTo-Json -Compress | Out-File -Encoding utf8 $cfg
$env:ZN_SHOTS = $cfg
$p = Start-Process 'dist\ZooNight-win32-x64\ZooNight.exe' -PassThru
if (-not $p.WaitForExit(120000)) { Stop-Process $p -Force; 'TIMEOUT' }
$env:ZN_SHOTS = $null
Get-ChildItem $Out | Select-Object Name, Length
