# syntax=docker/dockerfile:1
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# 预装依赖（利用缓存）
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install .

# 复制其余运行所需文件（不影响已安装的包）
COPY celery_app ./celery_app
COPY docs ./docs
COPY examples ./examples
# 可选：如果存在配置文件则复制
# COPY config.yaml ./config.yaml

EXPOSE 8000

# 默认运行 API，可在 docker-compose 中覆盖
CMD ["python", "-m", "autoscorer.api.run"]
