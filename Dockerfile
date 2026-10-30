# MyMovieDB 容器镜像。
#
# 路径口径来自 backend/config.py：配置项相对 backend/ 解析，所以
# ../data 就是 /app/data、../frontend 就是 /app/frontend。
# /app/data 必须挂出来，它是数据库、封面缓存与头像的唯一落脚点。
#
# 与 requirements.txt 的差别：pystray / pyinstaller 只服务 Windows 托盘与打包，
# 容器里没有桌面，去掉；openai-whisper 会带进约 2GB 的 torch，语音翻译在容器里
# 不可用（/translate/check-tools 会如实报缺），默认不装，要用再开构建参数。
# 基础镜像走 daocloud 镜像源：NAS 直连 registry-1.docker.io 会超时（约 12s 无响应）。
ARG BASE_IMAGE=docker.m.daocloud.io/library/python:3.11-slim
FROM ${BASE_IMAGE}

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
# 依赖用本地 wheel 离线安装：NAS 到 pypi 的单连接带宽只有 ~15 KB/s，
# 直接 pip install 会卡在 pillow（7.1MB）上几十分钟下不完。
# wheel 在 PC 上用下面的命令取好（Windows 能直连 aliyun 源），传到 NAS 的 wheels/ 目录：
#   pip download -d wheels \
#     --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 --platform any \
#     --python-version 3.11 --implementation cp --only-binary=:all: \
#     -i https://mirrors.aliyun.com/pypi/simple/ \
#     -r requirements.docker.txt
COPY requirements.docker.txt ./requirements.docker.txt
COPY wheels/ /tmp/wheels/
RUN pip install --no-cache-dir --no-index --find-links=/tmp/wheels \
        -r requirements.docker.txt \
    && if [ "$INSTALL_WHISPER" = "1" ]; then \
         pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ openai-whisper; \
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
