@echo off
chcp 65001 >nul
echo ================================================
echo    MyMovieDB一键打包脚本
echo ================================================
echo.

cd /d "%~dp0backend"

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python
    pause
    exit /b 1
)

REM 检查 pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 pip
    pause
    exit /b 1
)

echo [1/5] 安装打包依赖...
pip install pyinstaller pystray Pillow --quiet
if errorlevel 1 (
    echo [错误] 安装依赖失败
    pause
    exit /b 1
)

echo [2/5] 安装项目依赖...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [错误] 安装项目依赖失败
    pause
    exit /b 1
)

echo [3/5] 安装 googletrans...
pip install googletrans==4.0.0rc1 --quiet
if errorlevel 1 (
    pip install googletrans --quiet
)

REM 创建图标（如果没有）
if not exist "icon.ico" (
    echo [可选] 创建默认图标...
    python create_icon.py
)

echo [4/5] 正在打包（需要几分钟）...
echo.

REM 执行打包
pyinstaller ^
    --name="MyMovieDB" ^
    --onefile ^
    --windowed ^
    --icon=icon.ico ^
    --add-data="icon.ico;." ^
    --hidden-import=uvicorn ^
    --hidden-import=uvicorn.logging ^
    --hidden-import=uvicorn.loops ^
    --hidden-import=uvicorn.loops.auto ^
    --hidden-import=uvicorn.protocols ^
    --hidden-import=uvicorn.protocols.http ^
    --hidden-import=uvicorn.protocols.http.auto ^
    --hidden-import=uvicorn.protocols.websockets ^
    --hidden-import=uvicorn.protocols.websockets.auto ^
    --hidden-import=uvicorn.lifespan ^
    --hidden-import=uvicorn.lifespan.auto ^
    --hidden-import=starlette ^
    --hidden-import=starlette.routing ^
    --hidden-import=starlette.middleware ^
    --hidden-import=starlette.middleware.cors ^
    --hidden-import=fastapi ^
    --hidden-import=pydantic ^
    --hidden-import=pydantic.BaseModel ^
    --hidden-import=httpcore ^
    --hidden-import=httpx ^
    --hidden-import=anyio ^
    --hidden-import=sniffio ^
    --hidden-import=googletrans ^
    --hidden-import=pystray ^
    --hidden-import=PIL ^
    --hidden-import=PIL.Image ^
    --hidden-import=PIL.ImageDraw ^
    --collect-all=uvicorn ^
    --collect-all=starlette ^
    --collect-all=fastapi ^
    --collect-all=pydantic ^
    --collect-all=googletrans ^
    --collect-all=pystray ^
    tray_launcher.py

if errorlevel 1 (
    echo.
    echo [错误] 打包失败！
    pause
    exit /b 1
)

echo [5/5] 整理文件...
mkdir "..\dist" 2>nul
copy "dist\MyMovieDB.exe" "..\dist\" >nul
copy "icon.ico" "..\dist\" >nul 2>nul

REM 复制前端文件
mkdir "..\dist\frontend" 2>nul
copy "..\frontend\index.html" "..\dist\frontend\" >nul

REM 创建数据目录
mkdir "..\dist\data\covers" 2>nul

echo.
echo ================================================
echo    打包完成！
echo ================================================
echo.
echo exe 文件位置: dist\MyMovieDB.exe
echo.
echo 使用方法:
echo   1. 双击 MyMovieDB.exe 运行
echo   2. 程序会在系统托盘生成图标
echo   3. 右键托盘图标可打开/退出
echo   4. 程序会自动打开浏览器
echo.
echo 注意事项:
echo   - 关闭黑窗口后程序会继续在后台运行
echo   - 关闭浏览器不会关闭程序
echo   - 使用托盘图标的"退出"来完全关闭
echo.
pause
