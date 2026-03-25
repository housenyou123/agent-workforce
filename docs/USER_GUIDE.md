# Agent Workforce — 使用指南

## 安装（一次性）

```bash
# 1. 加到 ~/.zshrc（每次开终端自动加载）
echo 'source ~/agent-workforce/hooks/claude_code_hook.sh' >> ~/.zshrc
source ~/.zshrc

# 2. 配置飞书群 webhook
#    在飞书群添加自定义机器人 → 拿到 webhook URL → 填入:
vim ~/agent-workforce/config.yaml
#    feishu.webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/你的URL"

# 3. 验证
aws    # 查看系统状态
```

## 日常使用

### 最简用法（3 秒反馈）

Claude Code 完成任务后，在终端输入:

```bash
aw_done "给 PixelBeat 加了分享功能"
# 会显示摘要面板，按 1-4 评分，或 Enter 跳过
```

或者更快:

```bash
aw3 "加了分享功能"    # 直接标记 👍，一步完成
```

### 完整用法（带计时）

```bash
# 任务开始时
aw_start "给 StoryDetailView 加分享按钮"

# ... 在 Claude Code 中工作 ...

# 任务完成时
aw_done
# 自动使用 aw_start 时的目标描述
# 自动计算耗时
# 显示反馈面板
```

### 快捷评分

```bash
aw1 "任务描述"    # 👎 不满意
aw2 "任务描述"    # 🔄 还行，需要微调
aw3 "任务描述"    # 👍 满意
aw4 "任务描述"    # ⭐ 标杆（加入 golden examples）
```

### 查看状态

```bash
aws              # Agent 状态总览
awt              # 今天的所有 traces
awr              # 最近 7 天的报告
```

## 飞书群交互

### 反馈按钮

每个任务完成后，飞书群会收到通知卡片，上面有 4 个按钮:
- 👍 满意 — 做得好
- 🔄 还行 — 大方向对，细节需要调
- 👎 不满意 — 需要重做
- ⭐ 标杆 — 特别好，存为参考样本

**直接在飞书点按钮就行**，和终端的 aw1-4 效果一样。

### 审批请求

以下事项会推送到飞书 #审批请求:
- ❌ Cross-Review reject（Agent 之间有分歧）
- 🆕 新 Agent 创建提案
- 📝 规则修改提案
- 🚀 部署确认
- 🔄 工作模式切换

**直接在飞书回复 ✅/❌/💬 即可。**

### 每日报告

每天早上飞书群收到:
- 昨天的任务总览（数量、成功率、成本）
- 每个 Agent 的表现
- 自动升级记录
- 待确认事项

## 什么都不做也可以

系统有三层反馈采集:

| 层级 | 你的操作 | 信号质量 |
|------|----------|----------|
| **自动采集** | 什么都不做 | git commit/revert/追问次数 → 低-中置信度 |
| **快捷评分** | 按一个数字键 | 1-4 分 → 中置信度 |
| **详细反馈** | 失败时选原因 | A-G 分类 → 高置信度 |

**推荐**: 大部分任务按 Enter 跳过就好。只在**特别好**（⭐）或**特别差**（👎）时给反馈。系统会从你的 git 行为自动推断其余的。

## 高级用法

### 手动触发评测

```bash
python3 ~/agent-workforce/cli.py evaluate --date 2026-03-25
```

### 查看某个 Agent 的历史

```bash
python3 ~/agent-workforce/cli.py report --agent ios_agent --days 14
```

### 手动补录反馈

```bash
# 查看今天的 traces
awt

# 找到 trace_id，补录反馈
python3 ~/agent-workforce/cli.py feedback tr_20260325_003 thumbs_up
```

## 场景自动识别

系统从你的工作目录自动推断项目和 Agent:

| 你在哪 | 识别为 | 分配 Agent |
|--------|--------|------------|
| `~/Desktop/CC/IOS Demo/PixelBeat/` | pixelbeat-ios | ios_agent |
| `~/Desktop/CC/IOS Demo/pixel-beat-backend/` | pixelbeat-backend | backend_agent |
| `~/Desktop/社交贴纸产品设计/ios-app/` | dog-story-ios | ios_agent |
| `~/Desktop/社交贴纸产品设计/backend/` | dog-story-backend | backend_agent |
| `~/Desktop/社交贴纸产品设计/spot-playground/` | spot-playground | web_agent |
| `~/Documents/instagram-us-college-ugc-data/` | instagram-ugc | data_agent |

**在子目录中也能识别**。如果识别不了，aw_quick 第二个参数可以手动指定项目。

## 系统进化

你不需要手动调整 Agent。系统每晚自动:

1. 分析当天任务表现
2. 识别失败模式
3. 生成 profile 改进
4. 用历史标杆样本回归测试
5. 通过 → 自动升级（飞书通知）
6. 未通过 / 重大变更 → 推送飞书等你确认

**你唯一要做的**: 偶尔标一个 ⭐ golden example，这是系统进化的最好燃料。
