# Agent Workforce V3 — 用户故事与验收标准

## 适配说明

Multica 面向 2-10 人团队，我们是 **1 人 + AI 编队**。
以下故事从 Multica 的 10 个场景中提炼出适合我们的 7 个，
每个故事定义了"做到什么样算好"和"做到什么样算不好"。

---

## Story 1: 早起看板 — "昨天 Agent 们干了什么"

> 用户打开 Dashboard，3 秒内看懂昨天的全貌。

### 好的标准
- [ ] 打开页面 < 2 秒加载完成（含数据）
- [ ] 4 个统计卡片立刻展示：Tasks / Golden率 / Cost / Memories
- [ ] Agent Performance 表格显示每个 agent 的任务数、golden 率、成本，可排序
- [ ] Activity Feed 按时间倒序展示最近 30 条 trace，每条有：时间、agent、项目、摘要、评分标签
- [ ] 评分标签用颜色区分：golden=绿 good=蓝 fine=黄 bad=红
- [ ] 点击某条 activity 能看到详情（文件变更、工具调用数）

### 不好的标准
- 打开白屏 > 3 秒
- 统计数字是硬编码或 0
- Activity Feed 为空或只显示 "Loading..."
- 无法区分不同 agent 的贡献
- 看不出哪些任务做得好、哪些做得差

### Sub-agent 拆解
| # | 任务 | 验收 |
|---|------|------|
| 1a | Dashboard 统计卡片从 API 动态取值（含 memory count） | 4 个数字都是实时数据 |
| 1b | Activity Feed 加载 + 评分色条 + 骨架屏 | 有数据时渲染、无数据时友好空状态 |
| 1c | Agent Performance 表增加 golden_rate 列 | 表格至少 5 列可排序 |

---

## Story 2: Agent 体检 — "这个 Agent 最近状态怎么样"

> 用户点进某个 Agent，看到它的健康度、擅长什么、弱在哪。

### 好的标准
- [ ] 左侧 Agent 列表显示所有 agent + 任务数 + 状态圆点
- [ ] 右侧详情区展示 3 行信息：统计卡片 / 热点文件 / 最近 Trace
- [ ] 热点文件列表：文件名 + 修改次数，最多 10 个
- [ ] 最近 Trace 列表：时间 + 摘要 + 评分，最多 10 条
- [ ] 绑定的 Skills 以标签展示
- [ ] 点击不同 agent 右侧立刻切换（无需重新加载页面）

### 不好的标准
- 右侧只有 3 个统计数字，没有文件和 trace 信息
- 显示 "coming in next phase"
- 切换 agent 需要等待 > 1 秒
- 没有 hot_files 和 recent_traces 数据

### Sub-agent 拆解
| # | 任务 | 验收 |
|---|------|------|
| 2a | Agent 详情面板：热点文件区块 | 显示 top10 文件名+次数 |
| 2b | Agent 详情面板：最近 trace 区块 | 显示 10 条 trace 含摘要+评分 |
| 2c | Agent 详情面板：Skills 标签 | 显示绑定的 skills 名称 |
| 2d | 左侧列表状态圆点 | 有任务=绿，空闲=灰 |

---

## Story 3: 技能复用 — "把这个解法存下来，下次自动用"

> 用户发现某个操作流程反复出现，创建 Skill 后所有 Agent 都能复用。

### 好的标准
- [ ] Skills 页展示已有技能卡片：名称 + 描述 + 绑定的 agents/projects
- [ ] 点 "+ New Skill" 弹出表单：name / description / content / projects / agents
- [ ] 表单提交后列表立刻更新（不刷页面）
- [ ] 每个 skill 可删除（有确认弹窗）
- [ ] 初始就有 5+ 个预填 skill，不是空页面

### 不好的标准
- Skills 页空空如也，显示 "No skills yet"
- "+ New Skill" 按钮不可点击或没有表单
- 提交后需要手动刷新
- 无法删除错误创建的 skill

### Sub-agent 拆解
| # | 任务 | 验收 |
|---|------|------|
| 3a | Skill 创建 Modal（表单 + 提交） | 填写后 POST 成功，列表自动刷新 |
| 3b | Skill 删除（确认 + 调用 API） | 点删除 → 确认 → 列表移除 |
| 3c | Skill 卡片展示 projects + agents 标签 | 标签用不同颜色区分 |

---

## Story 4: 记忆检索 — "上次 VPN 503 是怎么修的"

> 用户搜索过去的经验，快速找到相关记忆帮助当前决策。

### 好的标准
- [ ] 页面加载时默认展示 importance 最高的 20 条记忆
- [ ] 搜索框输入后回车立刻返回结果 (< 500ms)
- [ ] 支持按 type 过滤：All / lesson / feedback / pattern / project
- [ ] 每条结果显示：importance 星标 + type 标签 + project + 内容预览 + 访问次数 + 创建日期
- [ ] 搜索 "VPN 503" 能命中相关的网络排查经验
- [ ] 顶部显示总记忆数和库大小

### 不好的标准
- 页面打开是空白，必须搜索才有内容
- 搜索无结果但不提示
- 没有过滤器，海量结果无法缩小范围
- 记忆没有 importance 排序，重要的和琐碎的混在一起

### Sub-agent 拆解
| # | 任务 | 验收 |
|---|------|------|
| 4a | 默认加载 top20 记忆 | 页面打开即有内容 |
| 4b | Type 过滤器按钮组 | 点击切换，结果即时变化 |
| 4c | 搜索结果展示日期 + 访问次数 | 每条底部有元数据 |

---

## Story 5: 实时感知 — "Agent 刚完成了一个任务"

> 用户在 Dashboard 页停留时，新 trace 自动出现在 Activity Feed。

### 好的标准
- [ ] 页面打开后 SSE 连接建立
- [ ] 新 trace 产生后 < 5 秒出现在 Feed 顶部
- [ ] 无需手动刷新页面
- [ ] 新条目有一个轻微的进入动画（淡入或滑入）

### 不好的标准
- 必须手动 F5 才能看到新数据
- SSE 连接断开后不重连
- 新数据出现但不在顶部

### Sub-agent 拆解
| # | 任务 | 验收 |
|---|------|------|
| 5a | 前端 SSE 连接 + 自动刷新 Activity | 新 trace 自动出现 |
| 5b | SSE 断线重连 | 网络恢复后 10 秒内重连 |

---

## Story 6: 暗色模式 — "晚上用不刺眼"

> 用户在晚间工作时切换到暗色模式。

### 好的标准
- [ ] 导航栏有明暗切换按钮
- [ ] 切换后所有页面立刻变色（无闪烁）
- [ ] 暗色模式下文字可读、对比度充足
- [ ] 偏好保存到 localStorage，刷新后保持

### 不好的标准
- 没有切换入口
- 切换后部分组件还是白色
- 暗色模式下文字看不清

### Sub-agent 拆解
| # | 任务 | 验收 |
|---|------|------|
| 6a | App.tsx 加暗色切换按钮 + localStorage | 切换生效 + 持久化 |
| 6b | 所有页面暗色适配 | 无白色残留 |

---

## Story 7: 一键部署 — "改完代码直接上线"

> 用户在本地改完前端/后端，一条命令部署到火山云。

### 好的标准
- [ ] 有一个 deploy.sh 脚本: `bash scripts/deploy_v3.sh`
- [ ] 脚本自动: build 前端 → scp 后端+前端 → restart PM2 → 健康检查
- [ ] 部署后自动 curl 验证 5 个核心 API
- [ ] 失败时打印错误信息，不静默

### 不好的标准
- 部署需要手动执行 5+ 条命令
- 部署后不验证，上线了才发现挂了
- 前端 base path 忘记设置导致白屏（今天踩过的坑）

### Sub-agent 拆解
| # | 任务 | 验收 |
|---|------|------|
| 7a | deploy_v3.sh 一键部署脚本 | 执行一次完成全流程 |
| 7b | 健康检查: 前端 + 5 个 API | 全部 200 才算成功 |

---

## Sub-agent 工作分配总表

| Sub-agent | 负责故事 | 任务数 | 关键文件 |
|-----------|----------|--------|----------|
| **Frontend-A** | S1 (Dashboard) + S5 (SSE) + S6 (暗色) | 1a,1b,1c,5a,5b,6a,6b | App.tsx, Dashboard.tsx, index.css |
| **Frontend-B** | S2 (Agents) + S3 (Skills) + S4 (Memory) | 2a-d,3a-c,4a-c | Agents.tsx, Skills.tsx, Memory.tsx |
| **Deploy** | S7 (部署) | 7a,7b | scripts/deploy_v3.sh |

共 **19 个子任务**，按故事优先级: S1 > S4 > S2 > S3 > S5 > S6 > S7
