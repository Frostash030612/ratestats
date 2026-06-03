$ErrorActionPreference = 'Stop'
$dir = $PSScriptRoot
$bat = (Get-ChildItem -LiteralPath $dir -Filter '03_*.bat' | Select-Object -First 1).FullName
if (-not $bat) { throw "No 03_*.bat found in $dir" }
$st = '18:00'
$now = Get-Date
$sixToday = Get-Date -Year $now.Year -Month $now.Month -Day $now.Day -Hour 18 -Minute 0 -Second 0
if ($now -ge $sixToday) {
    $runAt = $sixToday.AddDays(1)
    $msg = 'Scheduled for tomorrow 18:00 (already past 18:00 today).'
} else {
    $runAt = $sixToday
    $msg = 'Scheduled for today 18:00.'
}
# schtasks /SD on zh-CN Windows expects yyyy/MM/dd
$sd = $runAt.ToString('yyyy/MM/dd')
$tr = "cmd.exe /c cd /d `"$dir`" && call `"$bat`""
& schtasks.exe /Create /TN 'RateStats_03_MarketRainbow_Once' /TR $tr /SC ONCE /ST $st /SD $sd /F
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "[OK] $msg"
Write-Host "Verify: schtasks /Query /TN RateStats_03_MarketRainbow_Once /V /FO LIST"
Write-Host "Cancel: schtasks /Delete /TN RateStats_03_MarketRainbow_Once /F"
