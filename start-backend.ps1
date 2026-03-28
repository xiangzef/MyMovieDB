# 启动后端服务
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $scriptDir "backend"

Write-Host "🔧 启动后端服务..." -ForegroundColor Cyan
Set-Location $backendDir
& python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
