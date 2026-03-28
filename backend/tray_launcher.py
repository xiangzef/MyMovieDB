# -*- coding: utf-8 -*-
"""
MyMovieDB 系统托盘启动器
- 后台运行 FastAPI 服务
- 系统托盘图标，右键菜单：打开 / 退出
- 双击或点击"打开"自动打开浏览器
"""
import sys
import os
import io
import threading
import webbrowser
import logging
import tempfile
from pathlib import Path

# 修复无控制台（windowless）环境下 stdout/stderr 为 None 的问题
# 必须在所有 import 之前做，否则 uvicorn/logging 初始化时会崩溃
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 尝试导入托盘相关库
try:
    from pystray import Icon, Menu, MenuItem
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False
    logger.warning("pystray 未安装，系统托盘功能将不可用")

# 全局变量
app = None
tray_icon = None


def create_default_icon():
    """创建一个默认的电影图标"""
    # 创建一个 64x64 的图片
    img = Image.new('RGB', (64, 64), color=(30, 30, 50))
    draw = ImageDraw.Draw(img)
    
    # 画一个简单的胶片/电影图标
    # 矩形边框
    draw.rectangle([10, 15, 54, 49], outline=(255, 200, 50), width=2)
    # 胶片孔
    for x in [18, 26, 34, 42, 50]:
        draw.rectangle([x, 18, x+3, 23], fill=(255, 200, 50))
        draw.rectangle([x, 41, x+3, 46], fill=(255, 200, 50))
    # 播放符号
    draw.polygon([(25, 28), (25, 38), (38, 33)], fill=(255, 200, 50))
    
    return img


def get_icon_path():
    """获取图标路径（优先使用资源文件）"""
    # 检查资源目录
    if getattr(sys, 'frozen', False):
        # 打包后的 exe 所在目录
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent
    
    icon_path = base_dir / "icon.ico"
    if icon_path.exists():
        return str(icon_path)
    
    # 如果没有图标文件，返回 None（将使用默认图标）
    return None


def start_server():
    """启动 FastAPI 服务器"""
    import time
    import traceback

    # 写日志到文件，方便排查
    log_path = Path(sys.executable).parent / "mymoviedb.log" if getattr(sys, 'frozen', False) else Path(__file__).parent / "mymoviedb.log"

    start_error = []

    def _run():
        try:
            # 切换工作目录到 exe/脚本所在目录
            if getattr(sys, 'frozen', False):
                os.chdir(Path(sys.executable).parent)
            else:
                os.chdir(Path(__file__).parent)

            from main import app as fastapi_app
            import uvicorn
            from uvicorn.config import Config

            config = Config(
                app=fastapi_app,
                host="127.0.0.1",
                port=8000,
                log_level="warning",
                use_colors=False,   # 禁用彩色输出，避免无控制台时崩溃
                access_log=False,
            )
            server = uvicorn.Server(config)
            server.run()
        except Exception as e:
            err = traceback.format_exc()
            start_error.append(err)
            logger.error(f"服务器线程异常: {err}")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(err)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    # 等待最多 8 秒，轮询端口是否开放
    import socket
    for _ in range(16):
        time.sleep(0.5)
        if start_error:
            err_msg = start_error[0]
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"服务器启动异常：\n\n{err_msg[:500]}\n\n详细日志：{log_path}",
                    "MyMovieDB 错误",
                    0x10
                )
            except Exception:
                pass
            return False
        try:
            s = socket.create_connection(("127.0.0.1", 8000), timeout=0.3)
            s.close()
            logger.info("FastAPI 服务器已就绪 (http://127.0.0.1:8000)")
            return True
        except OSError:
            continue

    # 超时仍未启动
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            f"服务器在 8 秒内未响应，可能启动失败。\n详细日志：{log_path}",
            "MyMovieDB 错误",
            0x10
        )
    except Exception:
        pass
    return False


def open_browser():
    """打开浏览器"""
    try:
        webbrowser.open("http://127.0.0.1:8000")
        logger.info("已打开浏览器")
    except Exception as e:
        logger.error(f"打开浏览器失败: {e}")


def show_window():
    """显示窗口/打开浏览器"""
    open_browser()


def on_open_click(tray_icon=None, item=None, event=None):
    """打开按钮点击"""
    open_browser()


def on_exit_click(tray_icon=None, item=None, event=None):
    """退出按钮点击"""
    logger.info("正在退出...")
    if tray_icon:
        tray_icon.stop()
    sys.exit(0)


def create_tray_icon():
    """创建系统托盘图标"""
    global tray_icon
    
    if not PYSTRAY_AVAILABLE:
        logger.warning("系统托盘功能不可用，请运行: pip install pystray Pillow")
        return None
    
    # 获取或创建图标
    icon_path = get_icon_path()
    if icon_path:
        icon_image = Image.open(icon_path)
    else:
        icon_image = create_default_icon()
    
    # 创建托盘菜单
    menu = Menu(
        MenuItem("打开 Web 界面", on_open_click, default=True),
        MenuItem("---"),  # 分隔线
        MenuItem("退出", on_exit_click),
    )
    
    # 创建托盘图标
    tray_icon = Icon(
        "MyMovieDB",
        icon_image,
        "MyMovieDB - 本地影视库",
        menu
    )
    
    return tray_icon


def setup_auto_start():
    """设置开机自启（可选）"""
    import winreg
    
    try:
        key = winreg.HKEY_CURRENT_USER
        path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        
        # 检查是否已设置
        with winreg.OpenKey(key, path, 0, winreg.KEY_ALL_ACCESS) as reg_key:
            try:
                value, _ = winreg.QueryValueEx(reg_key, "MyMovieDB")
                logger.info("已设置开机自启")
                return True
            except FileNotFoundError:
                pass
        
        # 获取 exe 路径
        if getattr(sys, 'frozen', False):
            exe_path = sys.executable
        else:
            exe_path = str(Path(__file__).parent / "MyMovieDB.exe")
        
        # 设置开机自启
        if os.path.exists(exe_path):
            with winreg.OpenKey(key, path, 0, winreg.KEY_ALL_ACCESS) as reg_key:
                winreg.SetValueEx(reg_key, "MyMovieDB", 0, winreg.REG_SZ, exe_path)
            logger.info("已设置开机自启")
            return True
        
    except Exception as e:
        logger.warning(f"设置开机自启失败: {e}")
    
    return False


def run():
    """主运行函数"""
    logger.info("=" * 50)
    logger.info("MyMovieDB 启动中...")
    logger.info("=" * 50)
    
    # 启动服务器
    if not start_server():
        logger.error("服务器启动失败，程序退出")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, "服务器启动失败，请检查端口 8000 是否被占用。", "MyMovieDB 错误", 0x10)
        except Exception:
            pass
        sys.exit(1)
    
    # 等待服务器启动
    import time
    time.sleep(1)
    
    # 自动打开浏览器
    open_browser()
    
    # 创建系统托盘
    if PYSTRAY_AVAILABLE:
        logger.info("系统托盘已创建，双击或右键可打开/退出")
        tray = create_tray_icon()
        if tray:
            # 运行托盘图标（会阻塞）
            tray.run()
    else:
        logger.info("提示: 安装 pystray 可以启用系统托盘功能")
        logger.info("运行: pip install pystray Pillow")
        logger.info("")
        logger.info("程序正在运行，按 Ctrl+C 停止...")
        
        # 保持运行
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("程序已停止")
            sys.exit(0)


if __name__ == "__main__":
    run()
