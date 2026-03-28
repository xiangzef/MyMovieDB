# 启动后端服务
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $scriptDir "backend"

# 从 config.py 读取端口
$port = 8000
$portMatch = Select-String -Path "$backendDir\config.py" -Pattern 'PORT\s*=\s*(\d+)' | Select-Object -First 1
if ($portMatch) {
    $port = [int]$portMatch.Matches.Groups[1].Value
}

Write-Host "🧹 清除 Python 缓存..." -ForegroundColor Yellow
Remove-Item -Recurse -Force "$scriptDir\__pycache__" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$backendDir\__pycache__" -ErrorAction SilentlyContinue
Get-ChildItem -Path $backendDir -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "✅ 缓存清除完毕，启动后端（端口 $port）..." -ForegroundColor Green

Set-Location $backendDir
& python -m uvicorn main:app --host 0.0.0.0 --port $port
