# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /app

# 精简依赖：容器内不需要 whisper(带torch)/托盘/打包组件
COPY backend/requirements.txt /tmp/requirements.txt
RUN grep -vE "openai-whisper|pystray|pyinstaller" /tmp/requirements.txt > /tmp/req-docker.txt \
    && pip install --no-cache-dir -r /tmp/req-docker.txt

COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

WORKDIR /app/backend
EXPOSE 8000
VOLUME ["/app/data", "/volume1/video"]

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]