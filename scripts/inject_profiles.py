"""
Agent Workforce — Profile Injector

在每个项目目录的 .claude/CLAUDE.md 中注入对应 Agent Profile。
这样 Claude Code 打开项目时会自动加载 profile 规范。

用法:
  python3 inject_profiles.py          # 注入所有项目
  python3 inject_profiles.py --check  # 只检查，不修改
"""

import argparse
import os
from pathlib import Path

BASE_DIR = Path.home() / "agent-workforce"
PROFILES_DIR = BASE_DIR / "profiles"

# 项目 → agent 映射（和 trace_schema.py 的 SCENARIO_RULES 保持一致）
PROJECT_AGENT_MAP = {
    # PixelBeat 系列
    "~/Desktop/CC/IOS Demo/PixelBeat": "ios_agent",
    "~/Desktop/CC/IOS Demo/pixel-beat-backend": "backend_agent",
    "~/Desktop/CC/IOS Demo/pupixel_pe_tool": "web_agent",
    # IPGuard
    "~/Desktop/CC/IPGuard": "ios_agent",
    # Dog Story 系列
    "~/Desktop/社交贴纸产品设计/ios-app": "ios_agent",
    "~/Desktop/社交贴纸产品设计/backend": "backend_agent",
    "~/Desktop/社交贴纸产品设计/sticker-vision": "backend_agent",
    "~/Desktop/社交贴纸产品设计/spot-playground": "web_agent",
    "~/Desktop/社交贴纸产品设计/gossip-dog-debug": "web_agent",
    # 数据项目
    "~/Documents/instagram-us-college-ugc-data": "data_agent",
    # GT Web
    "~/Desktop/数据素材/发布意图分类项目/gt_web/frontend": "web_agent",
    "~/Desktop/数据素材/发布意图分类项目/gt_web/backend": "backend_agent",
    # 基础设施
    "~/projects/claude-api-proxy": "infra_agent",
    "~/openclaw": "backend_agent",
}


def get_latest_profile_version(agent_id: str) -> str:
    """获取 agent 最新的 profile 版本号"""
    profile_dir = PROFILES_DIR / agent_id
    if not profile_dir.exists():
        return "v1.0"
    yamls = sorted(profile_dir.glob("v*.yaml"), reverse=True)
    return yamls[0].stem if yamls else "v1.0"


def read_profile_content(agent_id: str, version: str) -> str:
    """读取 profile 内容"""
    path = PROFILES_DIR / agent_id / f"{version}.yaml"
    if path.exists():
        return path.read_text()
    return ""


def generate_claude_md_section(agent_id: str, version: str) -> str:
    """生成要注入到 CLAUDE.md 的 Agent Workforce 段落"""
    profile_path = PROFILES_DIR / agent_id / f"{version}.yaml"
    profile_content = read_profile_content(agent_id, version)

    # 提取关键信息
    lines = profile_content.split("\n")
    role_lines = []
    can_do = []
    cannot_do = []
    quality_gates = []
    lessons = []

    section = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("role:"):
            section = "role"
        elif stripped.startswith("can_do:"):
            section = "can_do"
        elif stripped.startswith("cannot_do:"):
            section = "cannot_do"
        elif stripped.startswith("quality_gates:"):
            section = "quality_gates"
        elif stripped.startswith("must_pass:"):
            section = "must_pass"
        elif stripped.startswith("lessons:"):
            section = "lessons"
        elif stripped.startswith("lesson:") and section == "lessons":
            lessons.append(stripped.split(":", 1)[1].strip().strip('"'))
        elif any(stripped.startswith(k) for k in ["capabilities:", "projects:", "review_dimensions:", "workflow:", "boundaries:", "should_pass:"]):
            section = None
        elif section == "role" and stripped and not stripped.startswith("#"):
            role_lines.append(stripped)
        elif section == "can_do" and stripped.startswith("- "):
            can_do.append(stripped[2:].strip().strip('"'))
        elif section == "cannot_do" and stripped.startswith("- "):
            cannot_do.append(stripped[2:].strip().strip('"'))
        elif section == "must_pass" and stripped.startswith("- "):
            quality_gates.append(stripped[2:].strip().strip('"'))

    role_text = " ".join(role_lines)

    result = f"""
## Agent Workforce Profile

> 此段由 Agent Workforce 自动注入 ({agent_id} {version})
> 完整 profile: {profile_path}

**角色**: {role_text[:200]}

**禁止**:
{chr(10).join(f'- {c}' for c in cannot_do[:8])}

**质量门槛**:
{chr(10).join(f'- {c}' for c in quality_gates[:6])}

**历史经验**:
{chr(10).join(f'- {l}' for l in lessons[:5])}
"""
    return result.strip()


# Agent Workforce 段落的标记
AW_START = "<!-- AGENT_WORKFORCE_START -->"
AW_END = "<!-- AGENT_WORKFORCE_END -->"


def inject_into_claude_md(project_path: str, agent_id: str, dry_run: bool = False) -> bool:
    """在项目的 CLAUDE.md 中注入或更新 Agent Workforce 段落"""
    project_path = Path(project_path).expanduser()
    if not project_path.exists():
        return False

    claude_dir = project_path / ".claude"
    claude_md = claude_dir / "CLAUDE.md"

    version = get_latest_profile_version(agent_id)
    aw_section = f"{AW_START}\n{generate_claude_md_section(agent_id, version)}\n{AW_END}"

    if claude_md.exists():
        content = claude_md.read_text()
        # 替换已有的 AW 段落
        if AW_START in content:
            import re
            content = re.sub(
                f"{AW_START}.*?{AW_END}",
                aw_section,
                content,
                flags=re.DOTALL,
            )
        else:
            # 追加到末尾
            content = content.rstrip() + "\n\n" + aw_section + "\n"
    else:
        content = aw_section + "\n"

    if dry_run:
        print(f"  [dry-run] {claude_md}")
        print(f"            → {agent_id} {version}")
        return True

    claude_dir.mkdir(parents=True, exist_ok=True)
    claude_md.write_text(content)
    print(f"  [injected] {claude_md}")
    print(f"             → {agent_id} {version}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Inject Agent Profiles into CLAUDE.md")
    parser.add_argument("--check", action="store_true", help="只检查，不修改")
    args = parser.parse_args()

    print("\nAgent Workforce — Profile Injector\n")

    for project_path, agent_id in PROJECT_AGENT_MAP.items():
        expanded = Path(project_path).expanduser()
        if not expanded.exists():
            print(f"  [skip] {project_path} (目录不存在)")
            continue

        inject_into_claude_md(project_path, agent_id, dry_run=args.check)

    print("\nDone.\n")


if __name__ == "__main__":
    main()
