"""
Agent Workforce — Memory DB 测试

运行: cd ~/agent-workforce/scripts && python3 test_memory_db.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from memory_db import MemoryDB


class TestMemoryDB(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = MemoryDB(self.tmp.name)

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmp.name)

    def test_save_and_recall(self):
        """保存并召回记忆"""
        self.db.save("lesson", content="VPN 503 先查 nginx", project="enterprise-vpn", agent="netops_agent")
        results = self.db.recall(project="enterprise-vpn")
        self.assertEqual(len(results), 1)
        self.assertIn("503", results[0]["content"])

    def test_fts_search(self):
        """FTS5 全文搜索"""
        self.db.save("lesson", content="shadowrocket 订阅生成需要检查 base64 编码", project="enterprise-vpn")
        self.db.save("lesson", content="SwiftUI 布局使用 VStack", project="pixelbeat-ios")

        results = self.db.search("shadowrocket")
        self.assertEqual(len(results), 1)
        self.assertIn("shadowrocket", results[0]["content"])

    def test_importance_ordering(self):
        """按 importance 排序"""
        self.db.save("lesson", content="低优先级", project="test", importance=0.2)
        self.db.save("lesson", content="高优先级", project="test", importance=0.9)

        results = self.db.recall(project="test")
        self.assertEqual(results[0]["content"], "高优先级")

    def test_access_count_increment(self):
        """访问自动增加 access_count"""
        mid = self.db.save("lesson", content="test memory", project="test")
        self.db.recall(project="test")
        self.db.recall(project="test")

        row = self.db.conn.execute("SELECT access_count FROM memories WHERE id=?", (mid,)).fetchone()
        self.assertEqual(row[0], 2)

    def test_update_existing(self):
        """更新已有记忆"""
        mid = self.db.save("lesson", id="test_1", content="v1", project="test")
        self.db.save("lesson", id="test_1", content="v2 updated", project="test")

        results = self.db.recall(project="test")
        self.assertEqual(len(results), 1)
        self.assertIn("v2", results[0]["content"])

    def test_decay_importance(self):
        """时间衰减"""
        self.db.save("lesson", content="old memory", project="test", importance=0.8)
        # Manually set last_accessed to 60 days ago
        self.db.conn.execute(
            "UPDATE memories SET last_accessed = '2026-02-01T00:00:00+08:00'"
        )
        self.db.conn.commit()

        updated = self.db.decay_importance(half_life_days=30)
        self.assertGreater(updated, 0)

        row = self.db.conn.execute("SELECT importance FROM memories").fetchone()
        self.assertLess(row[0], 0.5)  # 60 days = 2 half-lives, 0.8 * 0.25 ≈ 0.2

    def test_format_for_injection(self):
        """格式化输出"""
        self.db.save("lesson", content="VPN 排查先画拓扑", project="vpn", importance=0.9)
        self.db.save("pattern", content="重试链反模式", importance=0.8)

        memories = self.db.recall(limit=5)
        text = self.db.format_for_injection(memories)

        self.assertIn("## 相关经验", text)
        self.assertIn("VPN", text)

    def test_citations(self):
        """Citation 保存和验证"""
        self.db.save("lesson", content="test",
                     citations=[{"file": "/Users/housen/agent-workforce/scripts/memory_db.py"}])
        results = self.db.recall()
        citations = json.loads(results[0]["citations"])
        self.assertEqual(len(citations), 1)

        # Verify citations
        verify = self.db.verify_citations(results[0]["id"])
        self.assertEqual(len(verify["valid"]), 1)

    def test_stats(self):
        """统计信息"""
        self.db.save("lesson", content="a", project="p1")
        self.db.save("pattern", content="b", project="p2")
        s = self.db.stats()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["by_type"]["lesson"], 1)
        self.assertEqual(s["by_type"]["pattern"], 1)

    def test_delete(self):
        """删除记忆"""
        mid = self.db.save("lesson", content="to delete")
        self.db.delete(mid)
        results = self.db.recall()
        self.assertEqual(len(results), 0)

    def test_project_filter(self):
        """按项目过滤"""
        self.db.save("lesson", content="VPN stuff", project="enterprise-vpn")
        self.db.save("lesson", content="iOS stuff", project="pixelbeat-ios")

        vpn = self.db.recall(project="enterprise-vpn")
        ios = self.db.recall(project="pixelbeat-ios")
        self.assertEqual(len(vpn), 1)
        self.assertEqual(len(ios), 1)


class TestProductionDB(unittest.TestCase):
    """测试生产数据库"""

    def test_production_db_exists(self):
        """生产 memory.db 存在且有数据"""
        prod_db = Path.home() / "agent-workforce" / "knowledge" / "memory.db"
        if not prod_db.exists():
            self.skipTest("Production DB not yet created")

        db = MemoryDB(prod_db)
        s = db.stats()
        print(f"\n  Production DB: {s['total']} memories, {s['db_size_kb']}KB")
        self.assertGreater(s["total"], 0)
        db.close()

    def test_production_search(self):
        """生产环境搜索"""
        prod_db = Path.home() / "agent-workforce" / "knowledge" / "memory.db"
        if not prod_db.exists():
            self.skipTest("Production DB not yet created")

        db = MemoryDB(prod_db)
        results = db.search("shadowrocket")
        print(f"\n  Search 'shadowrocket': {len(results)} results")
        self.assertGreater(len(results), 0)
        db.close()

    def test_production_recall_vpn(self):
        """生产环境: 召回 VPN 项目记忆"""
        prod_db = Path.home() / "agent-workforce" / "knowledge" / "memory.db"
        if not prod_db.exists():
            self.skipTest("Production DB not yet created")

        db = MemoryDB(prod_db)
        results = db.recall(project="enterprise-vpn")
        text = db.format_for_injection(results)
        print(f"\n  VPN recall: {len(results)} memories")
        print(f"  Injection text ({len(text)} chars):")
        print(f"  {text[:300]}")
        self.assertGreater(len(results), 0)
        db.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
