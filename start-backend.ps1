# 启动后端服务
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $scriptDir "backend"

Write-Host "🧹 清除 Python 缓存..." -ForegroundColor Yellow
Remove-Item -Recurse -Force __pycache__ -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$backendDir\__pycache__" -ErrorAction SilentlyContinue
Remove-Item -Force "$backendDir\*.pyc" -ErrorAction SilentlyContinue
Get-ChildItem -Path $backendDir -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "✅ 缓存清除完毕，启动后端..." -ForegroundColor Green

Set-Location $backendDir
& python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
