#!/bin/bash
set -e

echo "[Entrypoint] 古代木牛流马分析系统 - 后端服务启动"
echo "[Entrypoint] 环境: ${APP_ENV:-production}"
echo "[Entrypoint] Workers: ${GUNICORN_WORKERS:-auto}"

if [ "${APP_ENV}" = "development" ]; then
    echo "[Entrypoint] 开发模式 - 使用uvicorn"
    exec uvicorn main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        --log-level debug
else
    echo "[Entrypoint] 生产模式 - 使用gunicorn + uvicorn workers"
    exec gunicorn main:app \
        -c gunicorn_conf.py
fi
