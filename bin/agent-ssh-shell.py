#!/usr/bin/env python3
"""
agent-ssh-shell — 像原生 ssh 一样的交互式 shell，自动记录 + 审计 + 回放

用法:
    python agent-ssh-shell.py appen@192.168.1.100 --password appen
    python agent-ssh-shell.py appen@192.168.1.100 --key ~/.ssh/id_ed25519
    echo pwd | python agent-ssh-shell.py appen@192.168.1.100 --password appen --batch

跟 ssh 行为对齐:
- 进 shell 后随便敲命令
- exit / logout / quit 退出
- Ctrl+C 中断当前命令（不退出 session）
- 第二次 Ctrl+C 断开
"""
import sys
import os
import re
import time
import json
import argparse
import getpass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from agent_ssh_audit import SSHAuditClient, storage, cmd_learner

ANSI_CSI = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]')
ANSI_OSC = re.compile(r'\x1b\][^\x07\x1b]*\x07')


def strip_ansi(s: str) -> str:
    s = ANSI_OSC.sub("", s)
    s = ANSI_CSI.sub("", s)
    return s


def parse_target(target: str, default_port: int = 22):
    if "@" not in target:
        raise ValueError("target 必须是 user@host[:port]")
    user, host_port = target.split("@", 1)
    if ":" in host_port:
        host, port_s = host_port.split(":", 1)
        port = int(port_s) or default_port
    else:
        host, port = host_port, default_port
    return user, host, port


def drain_output(sh, max_wait: float = 0.4) -> str:
    """短轮询读所有可用输出，合成一段字符串返回"""
    buf = ""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        chunk = sh.recv(timeout=0.15)
        if chunk:
            buf += strip_ansi(chunk.decode("utf-8", errors="replace"))
        else:
            if buf:
                break  # 已有输出且无新内容，停止
    return buf


def drain_stderr(sh, max_wait: float = 0.2) -> str:
    buf = ""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        chunk = sh.recv_stderr(timeout=0.15)
        if chunk:
            buf += strip_ansi(chunk.decode("utf-8", errors="replace"))
        else:
            if buf:
                break
    return buf


def extract_prompt(text: str) -> str:
    """从输出末尾提取 prompt（以 $ 或 # 结尾的最后一行）"""
    text = text.rstrip()
    if not text:
        return ""
    last_line = text.split("\n")[-1].strip()
    if last_line.endswith("$") or last_line.endswith("#"):
        return last_line + " "
    return ""


# ──────────────────────────────────────────
# 学习日志辅助函数
# ──────────────────────────────────────────


def _log_shell_cmd(cmd: str, user: str, host: str, sid: str):
    """将交互式 shell 中发送的命令写入学习日志"""
    try:
        cmd_learner.log_command(
            cmd=cmd, user=user, host=host,
            session_id=sid,
        )
    except Exception as e:
        print(f"[agent-ssh-shell] 学习日志写入失败: {e}", file=sys.stderr)


def main():
    p = argparse.ArgumentParser(description="Agent SSH interactive shell (audit-enabled)")
    p.add_argument("target", help="user@host[:port]")
    p.add_argument("--password", help="密码(也可走 stdin / env)")
    p.add_argument("--key", help="私钥路径")
    p.add_argument("--port", type=int, default=22)
    p.add_argument("--meta", help="元信息(JSON)")
    p.add_argument("--no-color", action="store_true", help="关闭 ANSI 颜色(默认就是关的)")
    p.add_argument("--prompt", help="手动指定 prompt 字符串(默认从服务端输出提取)")
    args = p.parse_args()

    user, host, port = parse_target(args.target, args.port)

    password = args.password or os.environ.get("AGENT_SSH_PASSWORD")
    if not args.key and not password:
        password = getpass.getpass("password: ")

    meta = json.loads(args.meta) if args.meta else {}

    sid = storage.new_session_id(host=host, user=user)

    print(f"\n[agent-ssh-shell] 已连接 {user}@{host}:{port}", file=sys.stderr)
    print(f"[agent-ssh-shell] session: {sid}", file=sys.stderr)
    print(f"[agent-ssh-shell] 日志: {storage.session_log_path(sid)}", file=sys.stderr)
    print(f"[agent-ssh-shell] 输入命令，exit / logout / quit 退出，Ctrl+C 中断当前\n", file=sys.stderr)

    interrupted_once = False
    fixed_prompt = args.prompt  # 如果指定了就固定用，不再提取(避免重复)

    try:
        with SSHAuditClient(
            host=host, user=user, port=port,
            password=password, key_filename=args.key,
            extra_audit_meta=meta,
            session_id=sid,
        ) as c:
            sh = c.shell()
            time.sleep(0.3)

            # 吃欢迎语 / banner / 第一个 prompt
            initial = drain_output(sh, max_wait=1.2)
            if initial:
                sys.stdout.write(initial)
                sys.stdout.flush()

            while True:
                # 服务端已经发过的 prompt 会在 stdout 上显示
                # 我们不传 prompt 给 input() —— 避免双重 prompt
                try:
                    line = input()
                except EOFError:
                    print("\n[EOF]", file=sys.stderr)
                    break
                except KeyboardInterrupt:
                    if interrupted_once:
                        print("\n[断开]", file=sys.stderr)
                        break
                    interrupted_once = True
                    # 发送 Ctrl+C (0x03) 给服务器，中断当前命令
                    sh.send("\x03")
                    out = drain_output(sh, max_wait=0.6)
                    if out:
                        sys.stdout.write(out)
                        sys.stdout.flush()
                    continue

                interrupted_once = False

                if not line:
                    sh.send("\n")
                    time.sleep(0.1)
                    out = drain_output(sh, max_wait=0.3)
                    if out:
                        sys.stdout.write(out)
                        sys.stdout.flush()
                    continue

                # 记录命令到学习日志（排除空行、退出命令）
                line_stripped = line.strip()
                if line_stripped and line_stripped not in ("exit", "logout", "quit"):
                    _log_shell_cmd(line_stripped, user, host, sid)

                sh.send(line + "\n")

                # 短轮询读输出 —— 等到没新数据
                out = drain_output(sh, max_wait=0.5)
                err = drain_stderr(sh, max_wait=0.2)
                combined = out + err
                if combined:
                    sys.stdout.write(combined)
                    sys.stdout.flush()

                if line.strip() in ("exit", "logout", "quit"):
                    break

    except KeyboardInterrupt:
        print("\n[断开]", file=sys.stderr)
    except Exception as e:
        print(f"\n[FATAL] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n[agent-ssh-shell] session 结束: {sid}", file=sys.stderr)
    replay_py = (Path(__file__).parent / "agent-ssh-replay.py").resolve()
    print(f"[agent-ssh-shell] 回放(绝对路径):", file=sys.stderr)
    print(f"  python {replay_py} {sid}", file=sys.stderr)
    print(f"[agent-ssh-shell] 回放(切到项目目录):", file=sys.stderr)
    print(f"  cd {Path(__file__).resolve().parent.parent}", file=sys.stderr)
    print(f"  python bin\\agent-ssh-replay.py {sid}", file=sys.stderr)
    print(f"[agent-ssh-shell] 列所有 sessions:", file=sys.stderr)
    print(f"  python {replay_py} --list", file=sys.stderr)


if __name__ == "__main__":
    main()
