"""
cmd_learner — SSH 命令学习日志（纯 Markdown，按天归档）

与审计日志完全独立：
- 只保存执行的命令行，不含审计规则、输出结果等高阶数据
- 每天一个 Markdown 文件，方便翻阅、搜索、学习
- 纯追加写入，不破坏已有内容

路径：$AGENT_SSH_AUDIT_HOME/logs/cmds_learn/YYYY-MM-DD.md
"""
import os
from datetime import datetime
from pathlib import Path

from . import storage


def _learn_dir() -> Path:
    """学习日志根目录：$AGENT_SSH_AUDIT_HOME/logs/cmds_learn/"""
    p = storage.get_home() / "cmds_learn"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _daily_path(dt: datetime = None) -> Path:
    """当天学习日志文件路径"""
    d = (dt or datetime.now()).strftime("%Y-%m-%d")
    return _learn_dir() / f"{d}.md"


def log_command(cmd: str, user: str = "", host: str = "",
                session_id: str = "", note: str = "") -> None:
    """
    追加记录一条执行过的命令行到当天的学习日志。

    参数:
        cmd:        执行的命令全文
        user:       登录用户（可选）
        host:       目标主机（可选）
        session_id: 审计 session ID（可选，方便关联回放）
        note:       备注说明（可选，AI 可写入简短解释）

    写入格式（Markdown）:
        ### HH:MM:SS | user@host
        ```bash
        cmd 全文
        ```

    文件不存在时自动创建文件头和当日标题。
    """
    now = datetime.now()
    path = _daily_path(now)
    ts = now.strftime("%H:%M:%S")

    # 构建归属标签
    parts = [ts]
    label_parts = []
    if user:
        label_parts.append(user)
    if host:
        label_parts.append(host)
    if label_parts:
        parts.append("@".join(label_parts))
    if session_id:
        parts.append(f"sid:{session_id}")
    heading = " | ".join(parts)

    # 文件头（仅首次写入时）
    header = "# SSH 命令学习日志\n\n"
    day_title = f"## {now.strftime('%Y-%m-%d')}\n\n"

    # 检查文件是否存在以决定是否写入文件头
    if not path.exists():
        with path.open("w", encoding="utf-8", newline="\n") as f:
            f.write(header)
            f.write(day_title)
    else:
        # 检查当天标题是否存在
        content = path.read_text(encoding="utf-8")
        if day_title.strip() not in content:
            with path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(day_title)

    # 追加入口
    entry = f"### {heading}\n"
    if note:
        entry += f"> {note}\n\n"
    entry += "```bash\n"
    entry += cmd.rstrip("\n") + "\n"
    entry += "```\n\n"

    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(entry)


def list_daily_files(limit: int = 30) -> list:
    """列出最近的学习日志文件"""
    d = _learn_dir()
    if not d.exists():
        return []
    files = sorted(d.glob("*.md"), reverse=True)
    return [{
        "date": f.stem,
        "path": str(f),
        "size": f.stat().st_size,
    } for f in files[:limit]]


if __name__ == "__main__":
    # 简单自测
    log_command("df -h", user="root", host="192.168.1.1",
                session_id="test_001", note="检查磁盘使用率")
    log_command("uname -a", user="root", host="192.168.1.1",
                session_id="test_001")
    log_command("systemctl status nginx", user="appen", host="192.168.1.100",
                note="检查 Nginx 运行状态")
    print(f"已写入: {_daily_path()}")
    print("内容预览:")
    print(_daily_path().read_text(encoding="utf-8"))
