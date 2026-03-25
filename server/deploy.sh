#!/usr/bin/env bash
##############################################################################
# Agent Workforce Server — 部署脚本 (火山云 ECS)
#
# 需要人类确认后手动执行:
#   scp -i ~/Downloads/rootpassword2.pem -r server/ root@118.196.147.14:/opt/agent-workforce/
#   ssh -i ~/Downloads/rootpassword2.pem root@118.196.147.14 "bash /opt/agent-workforce/deploy.sh"
##############################################################################

set -euo pipefail

APP_DIR="/opt/agent-workforce"
DATA_DIR="/data/agent-workforce"
PORT=9100

echo "[aw-server] Setting up..."

# 创建数据目录
mkdir -p "$DATA_DIR"

# 安装依赖
cd "$APP_DIR"
pip3 install -r requirements.txt -q

# PM2 管理
if command -v pm2 &>/dev/null; then
    pm2 delete aw-server 2>/dev/null || true
    pm2 start "uvicorn app:app --host 0.0.0.0 --port $PORT" \
        --name aw-server \
        --cwd "$APP_DIR" \
        --interpreter python3
    pm2 save
    echo "[aw-server] Started on port $PORT via PM2"
else
    echo "[aw-server] PM2 not found, starting directly..."
    nohup uvicorn app:app --host 0.0.0.0 --port $PORT > /var/log/aw-server.log 2>&1 &
    echo "[aw-server] Started on port $PORT (PID: $!)"
fi

echo "[aw-server] Dashboard: http://118.196.147.14:$PORT"
echo "[aw-server] API: http://118.196.147.14:$PORT/api/traces"
echo "[aw-server] Feedback: http://118.196.147.14:$PORT/api/feedback?trace_id=xxx&rating=3"
