"""
Tests for auto_rate() function in trace_engine.py
"""
import sys
sys.path.insert(0, ".")

from trace_engine import auto_rate


def test_build_failed_returns_bad():
    """build 失败 → 1 (bad)"""
    v = {"build_passed": False, "credentials_safe": True, "files_in_boundary": True}
    assert auto_rate(
        completion_score=1.0, retry_edits=0, rounds=1,
        files_modified_count=1, verification=v
    ) == 1


def test_credentials_leak_returns_bad():
    """凭据泄露 → 1"""
    v = {"build_passed": None, "credentials_safe": False, "files_in_boundary": True}
    assert auto_rate(
        completion_score=1.0, retry_edits=0, rounds=1,
        files_modified_count=1, verification=v
    ) == 1


def test_out_of_boundary_returns_bad():
    """越界 → 1"""
    v = {"build_passed": None, "credentials_safe": True, "files_in_boundary": False}
    assert auto_rate(
        completion_score=1.0, retry_edits=0, rounds=1,
        files_modified_count=1, verification=v
    ) == 1


def test_high_retry_returns_fine():
    """retry > 2 → 2 (fine)"""
    v = {"build_passed": None, "credentials_safe": True, "files_in_boundary": True}
    assert auto_rate(
        completion_score=1.0, retry_edits=3, rounds=1,
        files_modified_count=1, verification=v
    ) == 2


def test_many_rounds_returns_fine():
    """rounds > 5 → 2 (fine)"""
    v = {"build_passed": None, "credentials_safe": True, "files_in_boundary": True}
    assert auto_rate(
        completion_score=1.0, retry_edits=0, rounds=6,
        files_modified_count=1, verification=v
    ) == 2


def test_build_passed_clean_returns_golden():
    """build 显式通过 + 0 retry + 有产出 → 4 (golden)"""
    v = {"build_passed": True, "credentials_safe": True, "files_in_boundary": True}
    assert auto_rate(
        completion_score=1.0, retry_edits=0, rounds=2,
        files_modified_count=3, verification=v
    ) == 4


def test_normal_success_returns_good():
    """正常完成 (build 未运行) → 3 (good)"""
    v = {"build_passed": None, "credentials_safe": True, "files_in_boundary": True}
    assert auto_rate(
        completion_score=1.0, retry_edits=0, rounds=2,
        files_modified_count=2, verification=v
    ) == 3


def test_read_only_session_returns_good():
    """纯查阅 (无文件修改) → 3 (good)"""
    v = {"build_passed": None, "credentials_safe": True, "files_in_boundary": True}
    assert auto_rate(
        completion_score=0.65, retry_edits=0, rounds=1,
        files_modified_count=0, verification=v
    ) == 3


def test_retry_and_rounds_combined():
    """retry=2 + rounds=4 各自不超阈值 → 3"""
    v = {"build_passed": None, "credentials_safe": True, "files_in_boundary": True}
    assert auto_rate(
        completion_score=1.0, retry_edits=2, rounds=4,
        files_modified_count=1, verification=v
    ) == 3


if __name__ == "__main__":
    tests = [f for f in dir() if f.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            globals()[t]()
            print(f"  PASS  {t}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t}: {e}")
        except Exception as e:
            print(f"  ERROR {t}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
