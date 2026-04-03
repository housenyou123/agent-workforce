"""
Agent Workforce — Evolution V2 验证测试

验证 P0-P3 所有改动:
  P0: auto_feedback 回补
  P1: 三级路由 (路径/session继承/内容推断)
  P2: NetOps Agent 路由
  P3: 文件边界检测

运行: cd ~/agent-workforce/scripts && python3 test_evolution_v2.py
"""

import os
import sys
import json
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from trace_schema import detect_scenario, _load_project_routes, _CONTENT_KEYWORDS
from trace_engine import auto_rate, check_file_boundary

HOME = str(Path.home())


class TestThreeLevelRouting(unittest.TestCase):
    """P1: 三级路由测试"""

    def test_level1_path_match(self):
        """Level 1: 已注册路径精确匹配"""
        p, s, a = detect_scenario(f"{HOME}/Desktop/enterprise-vpn-shadowrocket")
        self.assertEqual(p, "enterprise-vpn")
        self.assertEqual(a, "netops_agent")  # P2: 路由到 NetOps

    def test_level1_pixelbeat(self):
        p, s, a = detect_scenario(f"{HOME}/Desktop/CC/IOS Demo/PixelBeat")
        self.assertEqual(p, "pixelbeat-ios")
        self.assertEqual(a, "ios_agent")

    def test_level1_spot_playground(self):
        p, s, a = detect_scenario(f"{HOME}/Desktop/社交贴纸产品设计/spot-playground")
        self.assertEqual(p, "spot-playground")
        self.assertEqual(a, "web_agent")

    def test_level3_content_vpn(self):
        """Level 3: 从 goal 关键词推断 VPN"""
        p, s, a = detect_scenario(HOME, goal="查看我vpn 的项目，检查下网络")
        self.assertEqual(p, "enterprise-vpn")
        self.assertEqual(a, "netops_agent")

    def test_level3_content_agent_workforce(self):
        """Level 3: 从 goal 推断 agent-workforce"""
        p, s, a = detect_scenario(HOME, goal="看下 agent workforce 的 trace 数据")
        self.assertEqual(p, "agent-workforce")

    def test_level3_content_spot(self):
        """Level 3: 从 goal 推断 spot-playground"""
        import trace_schema
        trace_schema._LAST_SESSION_ROUTE = None
        p, s, a = detect_scenario(HOME, goal="进入我的玩法评测台看看数据")
        self.assertEqual(p, "spot-playground")

    def test_level3_content_shadowrocket(self):
        """Level 3: shadowrocket 关键词路由到 VPN"""
        import trace_schema
        trace_schema._LAST_SESSION_ROUTE = None
        p, s, a = detect_scenario(HOME, goal="shadowrocket 订阅 url 有问题")
        self.assertEqual(p, "enterprise-vpn")

    def test_unknown_fallback(self):
        """无匹配时返回 unknown"""
        import trace_schema
        trace_schema._LAST_SESSION_ROUTE = None
        p, s, a = detect_scenario(HOME, goal="今天天气怎么样")
        self.assertEqual(p, "unknown")

    def test_level2_session_inherit(self):
        """Level 2: 短指令继承上一条的 project"""
        import trace_schema
        # 先设定一个有效路由
        detect_scenario(f"{HOME}/Desktop/enterprise-vpn-shadowrocket", goal="检查VPN")
        # 短指令应该继承
        p, s, a = detect_scenario(HOME, goal="好了")
        self.assertEqual(p, "enterprise-vpn")
        # 清理状态
        trace_schema._LAST_SESSION_ROUTE = None

    def test_level2_auto_session_inherit(self):
        """Level 2: (auto) session 继承"""
        import trace_schema
        detect_scenario(f"{HOME}/Desktop/CC/IOS Demo/PixelBeat", goal="修改View")
        p, s, a = detect_scenario(HOME, goal="(auto) session with 3 tool calls")
        self.assertEqual(p, "pixelbeat-ios")
        trace_schema._LAST_SESSION_ROUTE = None


class TestNetOpsRouting(unittest.TestCase):
    """P2: NetOps Agent 路由测试"""

    def test_vpn_routes_to_netops(self):
        """VPN 项目路由到 NetOps Agent"""
        p, s, a = detect_scenario(f"{HOME}/Desktop/enterprise-vpn-shadowrocket")
        self.assertEqual(a, "netops_agent")
        self.assertEqual(s, "network_ops")

    def test_vpn_keyword_routes_to_netops(self):
        """VPN 关键词路由到 NetOps"""
        p, s, a = detect_scenario(HOME, goal="503 排查下原因")
        self.assertEqual(a, "netops_agent")


class TestAutoFeedback(unittest.TestCase):
    """P0: auto_rate 测试"""

    def test_golden(self):
        """Build 通过 + 0 retry + 有产出 = golden(4)"""
        r = auto_rate(0, retry_edits=0, rounds=2, files_modified_count=3,
                      verification={"build_passed": True, "credentials_safe": True, "files_in_boundary": True})
        self.assertEqual(r, 4)

    def test_bad_build_fail(self):
        """Build 失败 = bad(1)"""
        r = auto_rate(0, retry_edits=0, rounds=1, files_modified_count=1,
                      verification={"build_passed": False, "credentials_safe": True, "files_in_boundary": True})
        self.assertEqual(r, 1)

    def test_bad_credential_leak(self):
        """凭据泄露 = bad(1)"""
        r = auto_rate(0, retry_edits=0, rounds=1, files_modified_count=1,
                      verification={"build_passed": None, "credentials_safe": False, "files_in_boundary": True})
        self.assertEqual(r, 1)

    def test_fine_high_retry(self):
        """retry_edits > 2 = fine(2)"""
        r = auto_rate(0, retry_edits=4, rounds=2, files_modified_count=2,
                      verification={"build_passed": None, "credentials_safe": True, "files_in_boundary": True})
        self.assertEqual(r, 2)

    def test_fine_many_rounds(self):
        """rounds > 5 = fine(2)"""
        r = auto_rate(0, retry_edits=0, rounds=8, files_modified_count=1,
                      verification={"build_passed": None, "credentials_safe": True, "files_in_boundary": True})
        self.assertEqual(r, 2)

    def test_good_default(self):
        """默认 = good(3)"""
        r = auto_rate(0, retry_edits=1, rounds=3, files_modified_count=1,
                      verification={"build_passed": None, "credentials_safe": True, "files_in_boundary": True},
                      tool_call_count=8)
        self.assertEqual(r, 3)

    def test_golden_efficient_no_build(self):
        """v2: 高效完成无显式 build = golden(4)"""
        r = auto_rate(0, retry_edits=0, rounds=1, files_modified_count=2,
                      verification={"build_passed": None, "credentials_safe": True, "files_in_boundary": True},
                      tool_call_count=5)
        self.assertEqual(r, 4)

    def test_golden_quick_read_only(self):
        """v2: 快速查阅 (0 files, <=3 tools) = golden(4)"""
        r = auto_rate(0, retry_edits=0, rounds=1, files_modified_count=0,
                      verification={"build_passed": None, "credentials_safe": True, "files_in_boundary": True},
                      tool_call_count=2)
        self.assertEqual(r, 4)

    def test_fine_low_efficiency_with_retry(self):
        """v2: 低效(ratio>15) + retry = fine(2)"""
        r = auto_rate(0, retry_edits=1, rounds=2, files_modified_count=1,
                      verification={"build_passed": None, "credentials_safe": True, "files_in_boundary": True},
                      tool_call_count=20)
        self.assertEqual(r, 2)

    def test_fine_retry_and_rounds(self):
        """v2: retry>=2 + rounds>=3 = fine(2)"""
        r = auto_rate(0, retry_edits=2, rounds=3, files_modified_count=2,
                      verification={"build_passed": None, "credentials_safe": True, "files_in_boundary": True},
                      tool_call_count=10)
        self.assertEqual(r, 2)

    def test_good_moderate_work(self):
        """中等工作量保持 good(3)"""
        r = auto_rate(0, retry_edits=1, rounds=2, files_modified_count=3,
                      verification={"build_passed": None, "credentials_safe": True, "files_in_boundary": True},
                      tool_call_count=15)
        self.assertEqual(r, 3)


class TestFileBoundary(unittest.TestCase):
    """P3: 文件边界检测测试"""

    def test_ios_agent_swift_ok(self):
        """iOS Agent 修改 .swift 文件 = 无越界"""
        v = check_file_boundary("ios_agent", ["/path/to/View.swift", "/path/Info.plist"])
        self.assertEqual(v, [])

    def test_ios_agent_go_violation(self):
        """iOS Agent 修改 .go 文件 = 越界"""
        v = check_file_boundary("ios_agent", ["/path/to/View.swift", "/path/server.go"])
        self.assertIn("server.go", v)

    def test_web_agent_tsx_ok(self):
        """Web Agent 修改 .tsx 文件 = 无越界"""
        v = check_file_boundary("web_agent", ["/path/App.tsx", "/path/style.css"])
        self.assertEqual(v, [])

    def test_web_agent_swift_violation(self):
        """Web Agent 修改 .swift 文件 = 越界"""
        v = check_file_boundary("web_agent", ["/path/App.tsx", "/path/Model.swift"])
        self.assertIn("Model.swift", v)

    def test_backend_agent_mixed_ok(self):
        """Backend Agent 修改 .go + .py + .ts = 全部允许"""
        v = check_file_boundary("backend_agent", ["/p/main.go", "/p/app.py", "/p/index.ts"])
        self.assertEqual(v, [])

    def test_netops_agent_go_ok(self):
        """NetOps Agent 修改 .go + .sh + .yaml = 全部允许"""
        v = check_file_boundary("netops_agent", ["/p/vpn.go", "/p/deploy.sh", "/p/config.yaml"])
        self.assertEqual(v, [])

    def test_md_universally_allowed(self):
        """所有 Agent 修改 .md 文件 = 无越界"""
        v = check_file_boundary("ios_agent", ["/p/README.md"])
        self.assertEqual(v, [])

    def test_unknown_agent_no_check(self):
        """未知 agent 不做检查"""
        v = check_file_boundary("unknown", ["/p/anything.xyz"])
        self.assertEqual(v, [])

    def test_cross_contamination(self):
        """跨语言修改 = 检测出越界"""
        v = check_file_boundary("ios_agent", ["/p/View.swift", "/p/engine.py", "/p/server.go"])
        self.assertIn("engine.py", v)
        self.assertIn("server.go", v)
        self.assertEqual(len(v), 2)


class TestRecalcDryRun(unittest.TestCase):
    """回测: 用历史数据验证 recalc 效果"""

    def test_unknown_rate_acceptable(self):
        """回测: unknown 率应低于 40% (已回补数据)"""
        traces_dir = Path.home() / "agent-workforce" / "traces"

        total = 0
        unknown = 0

        for f in sorted(traces_dir.glob("2026-*.jsonl")):
            for line in f.read_text().strip().split("\n"):
                if not line.strip():
                    continue
                t = json.loads(line)
                total += 1
                if t.get("project") == "unknown":
                    unknown += 1

        if total > 0:
            pct = unknown * 100 // total
            print(f"\n  Unknown: {unknown}/{total} ({pct}%)")
            self.assertLess(pct, 40, "unknown 率应低于 40%")

    def test_auto_feedback_full_coverage(self):
        """回测: auto_feedback 100% 覆盖"""
        traces_dir = Path.home() / "agent-workforce" / "traces"

        total = 0
        covered = 0

        for f in sorted(traces_dir.glob("2026-*.jsonl")):
            for line in f.read_text().strip().split("\n"):
                if not line.strip():
                    continue
                t = json.loads(line)
                total += 1
                if t.get("auto_feedback") is not None:
                    covered += 1

        if total > 0:
            pct = covered * 100 // total
            print(f"\n  auto_feedback coverage: {covered}/{total} ({pct}%)")
            self.assertGreaterEqual(pct, 95, "auto_feedback 覆盖率应 >= 95%")


if __name__ == "__main__":
    unittest.main(verbosity=2)
