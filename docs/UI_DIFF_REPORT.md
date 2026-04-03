# UI 差异对比: Agent Workforce vs Multica

## 整体架构

| 维度 | Multica | AW 当前 | 差距 |
|------|---------|---------|------|
| 布局 | Sidebar + SidebarInset | ✅ Sidebar + Main (已对齐) | 无 |
| 色彩系统 | oklch + shadcn/ui 变量 | ✅ hex 近似 Multica 色值 | 细微色差 |
| 组件库 | shadcn/ui 全套 (Dialog/Button/Badge/Tabs/...) | 手写组件 | **最大差距** |
| 图标 | Lucide 全套 (30+ 图标) | ✅ Lucide 基础 (6 图标) | 需要更多图标 |
| 字体 | Geist Sans / Geist Mono (自托管) | Inter (CDN) | 可选升级 |
| 暗色模式 | next-themes + system 检测 | ✅ localStorage + .dark class | 功能等价 |
| 实时通信 | WebSocket Hub (双向) | ✅ SSE (单向，够用) | 功能等价 |

## 逐页对比

### 1. Sidebar 导航

| 细节 | Multica | AW 当前 | 对齐度 |
|------|---------|---------|--------|
| Workspace 切换器 | ✅ 顶部 dropdown | ❌ 无 (单用户不需要) | N/A |
| Logo | 彩色图标 + workspace 名 | ✅ 品牌色方块 + 文字 | 80% |
| 导航图标 | 6 项 (Inbox/MyIssues/Issues/Agents/Runtimes/Skills) | 4 项 (Dashboard/Agents/Skills/Memory) | 合理裁剪 |
| 选中态 | bg-sidebar-accent + 加粗 | ✅ 类似实现 | 90% |
| 未选中态 | text-muted-foreground + hover 变亮 | ✅ opacity 方式 | 80% |
| "New Issue" 快捷键 | ✅ 右上角 SquarePen 图标 | ❌ 无 | 可加 |
| Inbox badge | ✅ 未读数字 | ❌ 无 | 不需要 |
| Theme toggle | Footer 区域, Sun/Moon/Monitor 三选 | ✅ Footer 区域, 二选 | 90% |
| SidebarRail | ✅ 可折叠 rail | ❌ 固定宽度 | 低优 |

### 2. Dashboard / Issues 页

Multica 没有传统 Dashboard，它的首页是 **Issues 列表**。我们的 Dashboard 是独创的。

| 细节 | Multica Issues | AW Dashboard | 差异 |
|------|---------------|--------------|------|
| 主体 | Issue 列表 (表格) | 统计卡片 + Agent 表格 + Activity | **不同设计** |
| 统计卡片 | ❌ 无 | ✅ 4 个 StatCard | AW 独创 |
| Activity Feed | 在 Issue 详情内 | ✅ 独立 Feed | AW 独创 |
| 数据表格 | shadcn Table 组件 | 手写 table | 样式差距 |
| 骨架屏 | Skeleton 组件 | ✅ 手写 skeleton | 功能等价 |

### 3. Agents 页 (**差距最大**)

| 细节 | Multica | AW 当前 | 对齐度 |
|------|---------|---------|--------|
| 布局 | ResizablePanelGroup (可拖拽分栏) | 固定左右分栏 | 60% |
| Agent 卡片 | 名称 + 状态点 + Runtime + 描述 | ✅ 名称 + 任务数 + 状态点 | 70% |
| 状态系统 | idle/working/blocked/error/offline 5 态 | ✅ 有任务/空闲 2 态 | 需要增加 |
| 详情页 Tabs | Tabs: Overview / Tasks / Skills / Settings | 平铺展示 | **需要 Tabs** |
| Create Agent | Dialog 表单 (名称/描述/Runtime/Visibility) | ❌ 无创建功能 | 低优 |
| Agent 编辑 | 内联编辑 Instructions + Tools + Triggers | ❌ 只读 | 低优 |
| Skills 管理 | 可绑定/解绑 Skills (多选) | ✅ 展示绑定的 Skills | 70% |
| Task Queue | 展示任务队列 (queued/running/completed) | ✅ 展示 recent traces | 70% |
| Avatar | Bot 图标 + 品牌色圆形 | ❌ 无 avatar | 需要加 |
| Archive/Restore | ✅ 归档 + 恢复 | ❌ 无 | 低优 |

### 4. Skills 页

| 细节 | Multica | AW 当前 | 对齐度 |
|------|---------|---------|--------|
| 布局 | ResizablePanel (左列表 + 右编辑器) | 单列卡片列表 | **需要改** |
| 左侧 | Skill 列表 + 搜索 | ❌ 卡片直列 | 需要分栏 |
| 右侧 | File Tree + File Viewer (代码编辑) | ❌ 无编辑器 | 需要加 |
| Create | Dialog (Create + Import 两个 tab) | ✅ Modal 表单 | 80% |
| File 管理 | 多文件 (SKILL.md + config + templates) | 单 content 字段 | 低优 |
| Import | 从 ClawHub/Skills.sh 导入 | ❌ 无 | 不需要 |

### 5. Memory 页 (AW 独创)

Multica **没有 Memory 页**，这是我们的差异化。

| 细节 | AW 当前 | 建议 |
|------|---------|------|
| 搜索 | ✅ FTS5 搜索 | 已完成 |
| 过滤器 | ✅ Type 过滤 | 已完成 |
| 默认展示 | ✅ Top20 by importance | 已完成 |
| 可视化 | ❌ 无图表 | 可加 importance 分布图 |

### 6. 通用组件差距

| 组件 | Multica | AW 当前 | 需要做 |
|------|---------|---------|--------|
| **Dialog/Modal** | shadcn Dialog (统一样式) | ✅ 手写 Modal | 样式差距 |
| **Button** | shadcn Button (variant: default/outline/ghost/destructive) | 手写 button | 需要统一 |
| **Badge** | shadcn Badge (多色) | 手写 span | 需要统一 |
| **Tabs** | shadcn Tabs | ❌ 无 | **Agents 页需要** |
| **Tooltip** | shadcn Tooltip | ❌ 无 | 低优 |
| **Skeleton** | shadcn Skeleton | ✅ 手写 | 功能等价 |
| **Toast** | sonner | ❌ 无反馈提示 | 需要加 |
| **ResizablePanel** | react-resizable-panels | ❌ 固定布局 | 中优 |
| **DropdownMenu** | shadcn DropdownMenu | ❌ 无 | 低优 |
| **Input** | shadcn Input | 原生 input + 手写样式 | 需要统一 |
| **Avatar** | ActorAvatar (圆形 + 首字母) | ❌ 无 | **需要** |

---

## 优先级排序: 最大 ROI 改进

### P0: 必须做 (视觉差距最大)

1. **Agents 页加 Tabs** — Overview / Tasks / Skills 三个 tab，Multica 最核心的 UI 模式
2. **Avatar 组件** — Agent 列表和 Activity Feed 都需要圆形首字母头像
3. **Skills 页改为左右分栏** — 左侧列表，右侧 content 展示/编辑

### P1: 应该做 (体验差距)

4. **统一 Button 样式** — 定义 primary/outline/ghost/destructive 四种 variant
5. **统一 Badge 样式** — agent badge 紫色, project badge 蓝色, status badge 按色
6. **Agent 状态增加到 4 态** — idle(灰)/working(绿)/blocked(黄)/error(红)
7. **Toast 反馈** — 创建 Skill / 删除 / 搜索结果数 等操作给用户反馈

### P2: 可以做 (锦上添花)

8. **ResizablePanel** — Skills 和 Agents 页可拖拽分栏
9. **Sidebar 可折叠** — 小屏幕时折叠为图标
10. **Skill 详情查看器** — 右侧 Markdown 渲染 content

### 不做

- Workspace 切换 (单用户)
- Issue 系统 (trace 代替)
- Inbox 通知 (飞书代替)
- Agent 创建/编辑 (profile YAML 代替)
- Skill Import (不需要)
