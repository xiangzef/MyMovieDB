"""
MyMovieDB 开发环境启动脚本（subprocess 方式）

用法: python run_dev.py

特点:
- Ctrl+C 退出干净无任何报错
- uvicorn 子进程独立运行，不受 Python 事件循环干扰
- 所有日志正常输出到终端
"""
import subprocess
import sys
import signal
import os

def run():
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    print("=" * 60)
    print("  MyMovieDB 开发服务器")
    print("  访问: http://127.0.0.1:8000")
    print("  按 Ctrl+C 停止")
    print("=" * 60)

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app",
         "--host", "0.0.0.0", "--port", "8000",
         "--log-level", "info"],
        cwd=backend_dir,
    )

    def stop(signum, frame):
        print("\n正在停止服务器...")
        proc.terminate()
        proc.wait()
        print("服务器已停止")
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    proc.wait()

if __name__ == "__main__":
    run()
