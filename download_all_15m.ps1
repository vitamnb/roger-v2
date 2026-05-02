$pairs = @("ETH/USDT","SOL/USDT","ADA/USDT","AVAX/USDT","DOT/USDT","LINK/USDT","UNI/USDT","AAVE/USDT","MATIC/USDT","NEAR/USDT","ALGO/USDT","ATOM/USDT","ICP/USDT","FIL/USDT","APT/USDT","SUI/USDT","RENDER/USDT","AR/USDT")
foreach ($p in $pairs) {
    Write-Host "Downloading $p..."
    freqtrade download-data --exchange kucoin -t 15m --timerange 20250101-20260427 --pairs $p --userdir "C:\Users\vitamnb\.openclaw\freqtrade" --prepend
    Start-Sleep -Seconds 2
}
