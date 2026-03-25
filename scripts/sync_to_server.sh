#!/usr/bin/env bash
##############################################################################
# 同步 profiles + server 代码到火山云
# 用法: bash scripts/sync_to_server.sh
##############################################################################

set -euo pipefail
KEY="$HOME/Downloads/rootpassword2.pem"
HOST="root@118.196.147.14"
REMOTE="/opt/agent-workforce"

echo "[sync] Uploading profiles..."
scp -i "$KEY" -r ~/agent-workforce/profiles/ "$HOST:$REMOTE/"

echo "[sync] Uploading server..."
scp -i "$KEY" ~/agent-workforce/server/app.py "$HOST:$REMOTE/server/app.py"

echo "[sync] Restarting service..."
ssh -i "$KEY" "$HOST" "systemctl restart aw-server"

echo "[sync] Done. Dashboard: http://118.196.147.14:9100"
