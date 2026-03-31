# 启动 MyMovieDB 后端
$ErrorActionPreference = "Continue"

Write-Host "=== MyMovieDB 后端启动脚本 ===" -ForegroundColor Cyan
Write-Host ""

# 切换到后端目录
Set-Location "F:\github\MyMovieDB\backend"

# 清除 Python 缓存
if (Test-Path "__pycache__") {
    Write-Host "清除 Python 缓存..." -ForegroundColor Yellow
    Remove-Item "__pycache__" -Recurse -Force
}

Write-Host "启动后端服务 (端口 8000)..." -ForegroundColor Green
Write-Host "API 文档: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "前端页面: http://localhost:8000" -ForegroundColor Cyan
Write-Host ""

# 启动服务
python main.py
