# 停止后端服务
$port = 8000
$proc = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess

if ($proc) {
    Stop-Process -Id $proc -Force
    Write-Host "✅ 已停止后端服务 (PID: $proc, 端口: $port)" -ForegroundColor Green
} else {
    Write-Host "⚠️ 端口 $port 没有运行的进程" -ForegroundColor Yellow
}
