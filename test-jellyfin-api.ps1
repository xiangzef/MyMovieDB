# 测试 Jellyfin API
$ErrorActionPreference = "Stop"

Write-Host "=== 测试 Jellyfin API ===" -ForegroundColor Cyan
Write-Host ""

# 测试健康检查
Write-Host "1. 测试健康检查..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
    Write-Host "✅ 后端运行正常: $health" -ForegroundColor Green
} catch {
    Write-Host "❌ 后端未启动或无法连接" -ForegroundColor Red
    Write-Host "请先运行 start-backend.ps1 启动后端" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# 测试 Jellyfin 统计 API
Write-Host "2. 测试 Jellyfin 统计 API..." -ForegroundColor Yellow
try {
    $stats = Invoke-RestMethod -Uri "http://localhost:8000/jellyfin/stats" -TimeoutSec 5
    Write-Host "✅ Jellyfin 统计 API 正常" -ForegroundColor Green
    Write-Host "   已导入影片数量: $($stats.total_imported)" -ForegroundColor Cyan
} catch {
    Write-Host "❌ Jellyfin 统计 API 失败: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# 测试 Jellyfin 扫描 API (OPTIONS 预检)
Write-Host "3. 测试 Jellyfin 扫描 API 预检..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/jellyfin/scan" -Method OPTIONS -TimeoutSec 5
    Write-Host "✅ Jellyfin 扫描 API 可访问" -ForegroundColor Green
} catch {
    Write-Host "❌ Jellyfin 扫描 API 预检失败: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== 测试完成 ===" -ForegroundColor Cyan
Write-Host "现在可以在前端页面测试扫描功能了" -ForegroundColor Green
