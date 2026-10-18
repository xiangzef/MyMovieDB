# MyMovieDB 容器镜像。
#
# 路径口径来自 backend/config.py：配置项相对 backend/ 解析，所以
# ../data 就是 /app/data、../frontend 就是 /app/frontend。
# /app/data 必须挂出来，它是数据库、封面缓存与头像的唯一落脚点。
#
# 与 requirements.txt 的差别：pystray / pyinstaller 只服务 Windows 托盘与打包，
# 容器里没有桌面，去掉；openai-whisper 会带进约 2GB 的 torch，语音翻译在容器里
# 不可用（/translate/check-tools 会如实报缺），默认不装，要用再开构建参数。
FROM python:3.11-slim

ARG INSTALL_WHISPER=0

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONUTF8=1 \
    TZ=Asia/Shanghai

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
        tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依赖单独一层，改代码时不会失效重装。
COPY requirements.docker.txt ./requirements.docker.txt
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
        --extra-index-url https://pypi.org/simple \
        -r requirements.docker.txt \
    && if [ "$INSTALL_WHISPER" = "1" ]; then \
         pip install --no-cache-dir -i https://pypi.org/simple openai-whisper; \
       fi

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY config.docker.ini ./backend/config.ini

# 覆盖镜像里的占位目录，让 /app/data 由挂载提供；没挂载时也不会因为只读而启动失败。
RUN mkdir -p /app/data/covers /app/data/avatars /app/info && \
    useradd --uid 1024 --create-home --shell /usr/sbin/nologin app && \
    chown -R 1024:1024 /app

USER 1024

EXPOSE 8000

# / 是静态前端，永远 200。用带 `path` 参数的 /open-folder 探测会拿到 422，
# 那说明服务活着，但 urlopen 对 4xx 抛异常，会被误判成不健康。
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=4).read()"]

# main.py 自带端口占用自动顺延，这里仍固定 8000 以便 compose 映射稳定。
CMD ["python", "backend/main.py"]
