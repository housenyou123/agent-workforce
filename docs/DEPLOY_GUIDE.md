# Agent Workforce — 部署指南

给同事用的完整部署手册。从零开始，30 分钟内跑通。

## 前提条件

- macOS (zsh)
- Python 3.11+
- Claude Code CLI (`claude` 命令可用)
- 一台 Linux 服务器 (用于存储 traces + Dashboard)
- 一个飞书群 (用于反馈通知)

## 第一步：克隆仓库 (2 分钟)

```bash
cd ~
git clone https://github.com/housenyou123/agent-workforce.git
cd agent-workforce
```

## 第二步：配置 (5 分钟)

### 2.1 飞书群 Webhook

1. 在飞书群里添加「自定义机器人」
2. 拿到 webhook URL
3. 填入 config.yaml:

```bash
vim config.yaml
# 修改 feishu.webhook_url 为你的 URL
```

### 2.2 服务器信息

修改 config.yaml 中的 server.url 为你的服务器地址:

```yaml
server:
  url: "http://YOUR_SERVER_IP:9100"
```

### 2.3 项目路由映射

修改 config.yaml 中的 `project_routes`，把路径改成你自己的项目目录:

```yaml
project_routes:
  "your/project/path": {project: "my-project", scenario: "backend_api", agent: "backend_agent"}
```

scenario 可选值: `ios_development` / `backend_api` / `web_frontend` / `data_analysis` / `infra`

## 第三步：安装 Hooks (3 分钟)

### 3.1 Shell 快捷命令

```bash
echo 'source ~/agent-workforce/hooks/claude_code_hook.sh 2>/dev/null' >> ~/.zshrc
source ~/.zshrc
```

验证: 终端输入 `aws`（不是 AWS CLI，是 agent-workforce status），应该看到 7 个 agent profile。

### 3.2 Claude Code Hooks

运行以下命令，把 4 个 hook 加到 Claude Code 配置:

```bash
python3 -c "
import json
f=open('\$HOME/.claude/settings.json')
d=json.load(f); f.close()
d.setdefault('hooks', {})
d['hooks']['PostToolUse']=[{'matcher':'Bash|Edit|Write','hooks':[{'type':'command','command':'bash ~/agent-workforce/hooks/auto_trace.sh','timeout':5,'async':True}]}]
d['hooks']['Stop']=[{'hooks':[{'type':'command','command':'bash ~/agent-workforce/hooks/session_stop_trace.sh','timeout':10,'statusMessage':'Saving trace...'}]}]
d['hooks']['UserPromptSubmit']=[{'hooks':[{'type':'command','command':'bash ~/agent-workforce/hooks/capture_goal.sh','timeout':3,'async':True}]}]
d['hooks']['SessionStart']=[{'hooks':[{'type':'command','command':'bash ~/agent-workforce/hooks/session_start.sh','timeout':3}]}]
f=open('\$HOME/.claude/settings.json','w')
json.dump(d,f,indent=2,ensure_ascii=False); f.close()
print('Done: 4 hooks added')
"
```

验证:
```bash
cat ~/.claude/settings.json | python3 -c "import sys,json; h=json.load(sys.stdin).get('hooks',{}); print(f'{len(h)} hooks: {list(h.keys())}')"
# 应该输出: 4 hooks: ['PostToolUse', 'Stop', 'UserPromptSubmit', 'SessionStart']
```

### 3.3 注入 Profile 到项目

```bash
python3 scripts/inject_profiles.py
```

这会在每个项目的 `.claude/CLAUDE.md` 中注入对应 agent 的 profile。Claude Code 打开项目时自动读取。

## 第四步：部署服务端 (10 分钟)

### 4.1 上传代码

```bash
# 替换为你的服务器信息
export DEPLOY_KEY="~/.ssh/your_key.pem"
export DEPLOY_HOST="root@YOUR_SERVER_IP"

ssh -i $DEPLOY_KEY $DEPLOY_HOST "mkdir -p /opt/agent-workforce /data/agent-workforce"
scp -i $DEPLOY_KEY -r server/ $DEPLOY_HOST:/opt/agent-workforce/
scp -i $DEPLOY_KEY -r profiles/ $DEPLOY_HOST:/opt/agent-workforce/
```

### 4.2 安装依赖

```bash
ssh -i $DEPLOY_KEY $DEPLOY_HOST "cd /opt/agent-workforce/server && pip3 install fastapi uvicorn -q"
```

### 4.3 设置 systemd 开机自启

```bash
ssh -i $DEPLOY_KEY $DEPLOY_HOST "cat > /etc/systemd/system/aw-server.service << 'EOF'
[Unit]
Description=Agent Workforce Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/agent-workforce/server
Environment=AW_DB_PATH=/data/agent-workforce/traces.db
Environment=AW_PROFILES_DIR=/opt/agent-workforce/profiles
ExecStart=/usr/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port 9100
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable aw-server
systemctl start aw-server"
```

### 4.4 开放端口

在服务器的安全组/防火墙中开放 TCP 9100 端口。

### 4.5 验证

```bash
curl http://YOUR_SERVER_IP:9100/api/stats
# 应该返回 []

# 打开浏览器访问 Dashboard
open http://YOUR_SERVER_IP:9100
```

## 第五步：验证完整链路 (5 分钟)

### 5.1 开一个新的 Claude Code 窗口

```bash
cd ~/your-project
claude
```

### 5.2 做一个小任务

让 Claude 改一个文件，比如:
```
帮我在 README.md 末尾加一行 "test"
```

### 5.3 退出 Claude Code

按 Ctrl+C 或输入 `/exit`。终端应该显示:
```
[aw] tr_20260326_001 | Rate: http://... | Today: 1
```

### 5.4 检查数据

```bash
# 本地 trace
awt   # 或 python3 ~/agent-workforce/cli.py traces

# 服务端
curl http://YOUR_SERVER_IP:9100/api/traces

# 飞书群应该收到通知 (如果任务有文件修改)
```

### 5.5 点飞书反馈链接

飞书通知里的 "满意 | 还行 | 不满意 | 标杆" 链接点一下，浏览器会显示确认页。

## 日常使用

完成上述 5 步后，系统自动运行，你什么都不用做。

| 场景 | 会发生什么 |
|------|-----------|
| 正常用 Claude Code | 自动记录 trace，session 结束时自动汇总 |
| 改了文件的 session | 飞书推送通知 + 反馈链接 |
| 纯对话 session | 静默记录，不推飞书 |
| 想快速评分 | 终端: `aw3 "做了什么"` (👍) |
| 想看今天进展 | 终端: `awt` |
| 想看系统状态 | 终端: `aws` |
| 想看 Dashboard | 浏览器: `http://YOUR_SERVER_IP:9100` |
| 想看 Agent Profiles | 浏览器: `http://YOUR_SERVER_IP:9100/profiles` |

## 快捷命令

| 命令 | 含义 |
|------|------|
| `aw1 "做了什么"` | 👎 不满意 |
| `aw2 "做了什么"` | 🔄 还行 |
| `aw3 "做了什么"` | 👍 满意 |
| `aw4 "做了什么"` | 标杆 (golden example) |
| `aws` | 系统状态 |
| `awt` | 今天的 traces |
| `awr` | 最近 7 天报告 |

## 自定义 Agent Profile

如果你有不同的项目类型，可以修改 `profiles/` 下的 YAML 文件:

```bash
# 编辑 profile
vim profiles/backend_agent/v1.0.yaml

# 重新注入到项目
python3 scripts/inject_profiles.py

# 同步到服务器
bash scripts/sync_to_server.sh
```

修改 `sync_to_server.sh` 中的服务器信息为你自己的。

## 夜间评测

积累 50+ traces 后，手动跑一次评测看效果:

```bash
python3 evolution/nightly_eval.py --date 2026-03-26
```

觉得有价值后再配 cron:
```bash
# 每天凌晨 2 点跑评测
0 2 * * * cd ~/agent-workforce && python3 evolution/nightly_eval.py >> /tmp/aw-eval.log 2>&1
```

## 架构一图流

```
你用 Claude Code
    ↓ (自动)
SessionStart hook → 记录开始时间
UserPromptSubmit hook → 捕获你的第一句话
PostToolUse hook → 每个 Bash/Edit/Write 记录到 buffer
Stop hook → 汇总 trace → 本地 JSONL + 远程 SQLite + 飞书通知
    ↓ (你在飞书)
点反馈链接 → 写入服务端
    ↓ (每晚)
nightly_eval.py → 分析 traces → 产出 insight + proposal → 人工确认后改 profile
```

## 常见问题

**Q: Hook 没生效？**
A: 确认 `~/.claude/settings.json` 里有 4 个 hooks。新开一个 Claude Code 窗口生效。

**Q: 飞书没收到通知？**
A: 检查 `config.yaml` 的 webhook_url 是否正确。只有修改了文件的 session 才推送。

**Q: Dashboard 打不开？**
A: 检查服务器 9100 端口是否开放（安全组 + 防火墙）。`systemctl status aw-server` 看服务状态。

**Q: traces 全是 unknown 项目？**
A: 在 `config.yaml` 的 `project_routes` 中加你的项目路径映射。

**Q: 改了 profile 但 Dashboard 没更新？**
A: 跑 `bash scripts/sync_to_server.sh` 同步到服务器。
