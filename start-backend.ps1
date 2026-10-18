# 启动后端服务
$ErrorActionPreference = "Continue"
$originalDir = Get-Location

Write-Host "=== MyMovieDB 后端启动脚本 ===" -ForegroundColor Cyan
Write-Host ""

# 添加 ffmpeg 到 PATH（如果不在环境变量中）
$ffmpegPath = "C:\Program Files\ffmpeg\bin"
if ($env:Path -notlike "*ffmpeg*") {
    $env:Path = "$ffmpegPath;$env:Path"
    Write-Host "已添加 ffmpeg 到 PATH: $ffmpegPath" -ForegroundColor Yellow
}

Write-Host "启动后端服务 (端口 8000)..." -ForegroundColor Green
Write-Host "API 文档: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "前端页面: http://localhost:8000" -ForegroundColor Cyan
Write-Host ""

# 使用 Python 3.14（确保使用最新版本）
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCmd.Source -like "*Python37*") {
    Write-Host "检测到 Python 3.7，将切换到 Python 3.14..." -ForegroundColor Yellow
    & "C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe" backend/main.py
} else {
    python backend/main.py
}

Set-Location $originalDir
