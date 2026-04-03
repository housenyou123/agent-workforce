# Sub-Agent 能力边界与职责规范

> 基于 590+ 条 trace 的实际数据分析，定义每个 Agent 的能力域、禁区、和从历史中提炼的教训。

---

## 1. Backend Agent

### 身份
服务端 API 开发 — Python + Go + TypeScript 后端

### 能力域 (CAN DO)
| 能力 | 证据 |
|------|------|
| Python 后端 (FastAPI/Flask) | events.py 30 次修改, client.py 9 次 |
| Go 网络服务 | shadowrocket.go 11 次修改 |
| 数据库操作 (SQLite/MongoDB) | schemas.py 等 |
| AI API 调用 (Claude/Gemini) | ai_client.py 9 次修改 |
| prompt 工程 | p3_questions.py 11 次修改 |

### 禁区 (CANNOT DO)
| 禁区 | 原因 (从 trace 中发现) |
|------|------------------------|
| .sh 脚本文件 | 29 次越界中 session_stop_trace.sh 等被误改 |
| .cjs/.mjs 配置文件 | ecosystem.config.cjs 越界修改导致部署失败 |
| .plist 系统文件 | com.enterprise-vpn.vpc-route.plist 越界 |
| 前端 .html 文件 | index.html 12 次越界 — 应由 web_agent 处理 |
| 网络诊断/路由配置 | 142 条 VPN trace 产生 14 次重试 → 已分离到 netops_agent |

### 从 trace 中学到的教训
1. **events.py 是核心文件 (30 次修改)** — 修改前必须 Read 完整文件，理解事件处理链
2. **重试信号 14 次** — 主要在 VPN 项目，网络问题不是 backend_agent 的强项
3. **golden 率 50%** — 中等水平，主要拖累来自跨域操作（改了不该改的文件）

### 理想使用场景
```
✅ "给面试 Bot 加一个新的 prompt 步骤"
✅ "修复 API 返回的 JSON 格式问题"
✅ "优化 VPN 管理后台的 Go 接口"
❌ "部署到火山云" → infra_agent
❌ "VPN 网络不通排查" → netops_agent
❌ "前端页面展示问题" → web_agent
```

---

## 2. NetOps Agent

### 身份
网络运维 + VPN 管理 + 云网络 — 从 backend_agent 分裂而来

### 能力域 (CAN DO)
| 能力 | 证据 |
|------|------|
| VPN 配置 (WireGuard/Xray) | enterprise-vpn 37 条 trace |
| 网络诊断 (ping/curl/traceroute) | 工具调用中 Bash 占 56% |
| Shadowrocket 订阅生成 | shadowrocket.go 修改 |
| 路由表/iptables 管理 | VPN case study |
| nginx/Caddy 反代 | 部署相关 trace |

### 禁区 (CANNOT DO)
| 禁区 | 原因 |
|------|------|
| .html/.tsx 前端文件 | 14 次越界中 index.html 5 次, schemas.py 3 次 |
| .mjs JavaScript 模块 | md2feishu.mjs 3 次越界 |
| Python 业务代码 | schemas.py, import_talent.py 被误改 — 这些是 interview-bot 的代码 |
| 数据库 schema 变更 | 应由 backend_agent 处理 |

### 从 trace 中学到的教训
1. **越界严重 (14 次, 38%)** — 虽然路由到 enterprise-vpn 项目，但该项目目录下有 interview-bot 的子文件
2. **重试信号 4 次 "还是503"** — 网络诊断能力在提升但还需要更严格的流程
3. **golden 率 51%** — 和 backend_agent 持平，说明分离有效但还需要细化边界

### 核心规则
```
⚠️ 改路由/iptables 前必须记录 before 状态
⚠️ 只修改 .go / .conf / .yaml / .sh 文件
⚠️ 远程命令执行必须人工确认
⚠️ 碰到 .py / .html / .tsx 文件时应该停下来，提示路由错误
```

---

## 3. Infra Agent

### 身份
Agent Workforce 系统本身的基础设施 — hooks + trace + 评测

### 能力域 (CAN DO)
| 能力 | 证据 |
|------|------|
| trace 系统 (Python) | trace_engine.py 13 次修改 |
| hook 脚本 (Bash) | session_stop_trace.sh 9 次修改 |
| 飞书通知 | feishu_notify.py 10 次修改 |
| 配置管理 (YAML) | config.yaml 5 次修改 |
| FastAPI 服务 | app.py 8 次修改 |

### 禁区 (CANNOT DO)
| 禁区 | 原因 |
|------|------|
| .go 文件 | 22 次越界中 shadowrocket.go, render_test.go 被误改 |
| .swift 文件 | test.swift 2 次越界 |
| 其他项目的代码 | agent-workforce 以外的文件不应触碰 |

### 从 trace 中学到的教训
1. **22 次越界** — 最多的 agent，因为 AW 项目内混杂了其他项目的 trace 操作
2. **golden 率 49%** — 偏低，主要因为系统搭建期试错多
3. **核心三文件规则**: trace_engine.py / session_stop_trace.sh / feishu_notify.py 修改前必须有 test case

---

## 4. Web Agent

### 身份
React/Next.js 前端开发 — Dashboard + 工具类 Web App

### 能力域 (CAN DO)
| 能力 | 证据 |
|------|------|
| React/TypeScript 组件 | .tsx 20 次修改 |
| TypeScript 逻辑 | .ts 14 次修改, types.ts/api.ts |
| Tailwind CSS | App.tsx, index.css |
| 数据面板 (Dashboard) | spot-playground 56 条 trace |

### 禁区 (CANNOT DO)
| 禁区 | 原因 |
|------|------|
| .go 文件 | shadowrocket.go 2 次越界 |
| .sh 脚本 | sync_to_server.sh 越界 |
| .swift iOS 代码 | 7 个 Swift 文件被误改 (曾属于 spot-playground 但实际是 iOS 代码) |
| 后端部署 | 10 次越界中多数和部署混淆 |

### 从 trace 中学到的教训
1. **Swift 文件越界 7 次** — spot-playground 目录下混有 iOS 项目文件，路由需要更精确
2. **重试信号 6 次 "还是打不开"** — 前端部署验证能力弱，需要 deploy 后自动 curl 检查
3. **golden 率 46%** — 最低，主要因为跨域操作和部署失败

### 核心规则
```
⚠️ 只修改 .tsx / .ts / .css / .html / .json / .svg 文件
⚠️ 修改后必须 npm run build 验证
⚠️ 部署后必须 curl 验证 200
⚠️ 碰到 .swift / .go 文件时停下来
```

---

## 5. iOS Agent

### 身份
Apple 平台原生开发 — Swift/SwiftUI

### 能力域 (CAN DO)
| 能力 | 证据 |
|------|------|
| SwiftUI 视图 | UploadView.swift 6 次, PhotoThumbnailView.swift 4 次 |
| ViewModel | AppViewModel.swift 4 次修改 |
| Xcode 项目配置 | project.yml 4 次修改 |
| UI 测试 | PageFlowTests.swift 3 次修改 |

### 禁区 (CANNOT DO)
| 禁区 | 原因 |
|------|------|
| .py Python 脚本 | mock_backend.py, generate_test_photos.py 越界 |
| .sh 脚本 | run_e2e.sh, session_start.sh 越界 |
| .yml 项目配置之外的 YAML | 应由 infra_agent 处理 |

### 从 trace 中学到的教训
1. **golden 率 60% — 最高** — iOS 项目边界清晰，Agent 表现最好
2. **project.yml 被标记为越界** — 但这其实是 iOS 项目的合法配置文件，border_check 规则需要调整
3. **辅助脚本越界** — mock_backend.py 等测试脚本不应由 iOS agent 修改

### 启示
iOS Agent 的高 golden 率证明: **边界越清晰，Agent 表现越好。**

---

## 6. Data Agent (待激活)

### 现状
87 条 trace 但大部分是路由推断产生的，实际有效任务不多。

### 预期能力域
- Python 数据分析 (pandas/numpy)
- VLM 输出质量评估
- 数据可视化 (matplotlib/plotly)
- Instagram/TikTok UGC 数据处理

### 激活条件
当出现明确的数据分析任务时启用，目前其 trace 多为误分配。

---

## 跨 Agent 规则总表

| 规则 | 适用 Agent | 来源 |
|------|-----------|------|
| 修改前 Read 完整文件 | ALL | 30 次 events.py 修改经验 |
| 改完验证 (build/test) | web, ios | web 46% golden 的教训 |
| 不修改 .swift 文件 | backend, netops, web, infra | 多 agent 越界数据 |
| 不修改 .go 文件 | web, infra, ios | 越界数据 |
| 不修改 .sh 文件 | backend, ios | 越界数据 |
| 网络操作必须记录 before | netops | VPN case study |
| 核心文件必须有 test | infra | 核心三文件规则 |
| 部署后 curl 验证 | infra, netops | 6 次 "打不开" |

## 如何让这些规范生效

1. **Profile 注入** — 更新 `profiles/*/v1.0.yaml` 的 cannot_do + quality_gates
2. **边界检测** — `check_file_boundary()` 已实现，每条 trace 自动检测
3. **Skill 绑定** — 特定操作绑定到对应 agent，防止路由错误
4. **Memory 注入** — session 开始时按 agent 注入历史教训
5. **Dashboard 可视化** — Agents 页的越界计数让问题可见

### 一句话总结

> **边界越清晰，Agent 表现越好。** iOS Agent 60% golden 证明了这一点。
> 所有其他 Agent 的改进方向都是：收紧边界 + 补全教训 + 验证闭环。
