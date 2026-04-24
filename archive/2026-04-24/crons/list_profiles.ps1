Get-ChildItem 'C:\Users\vitamnb\AppData\Local\BraveSoftware\Brave-Browser\User Data' -Directory | ForEach-Object {
    $name = $_.Name
    $prefsPath = Join-Path $_.FullName 'Preferences'
    if (Test-Path $prefsPath) {
        $content = Get-Content $prefsPath -Raw -ErrorAction SilentlyContinue
        if ($content -match '"name":\s*"([^"]+)"') {
            Write-Output "$name -> $($Matches[1])"
        } else {
            Write-Output "$name -> (no name found)"
        }
    } else {
        Write-Output "$name -> (no prefs)"
    }
}
