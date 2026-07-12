#!/usr/bin/env python3
"""
agent-ssh-cred — 凭据管理 CLI

基于 Windows DPAPI 加密存储 SSH 密码到 credentials.txt。
加密数据绑定到当前用户登录会话，其他用户/程序无法解密。

用法:
    python bin/agent-ssh-cred.py store <key> <password>
        加密存储密码（key 通常为 IP 或 user@host）
    python bin/agent-ssh-cred.py get <key>
        解密并输出密码的 Base64 编码（可直接喂给 --password-base64）
    python bin/agent-ssh-cred.py get-plain <key>
        解密并输出明文密码（仅调试用，不要在生产中使用）

    python bin/agent-ssh-cred.py list
        列出所有凭据 key 及其加密方式

    python bin/agent-ssh-cred.py delete <key>
        删除指定凭据

    python bin/agent-ssh-cred.py migrate
        扫描并升级所有旧版凭据为 DPAPI 加密

示例:
    python bin/agent-ssh-cred.py store 192.168.1.100 MySecret123
    python bin/agent-ssh-cred.py get 192.168.1.100
    # 输出: <base64 编码的密码>（可直接用作 --password-base64）

集成到 SSH 命令:
    $pw = python bin/agent-ssh-cred.py get 192.168.1.100
    python bin/agent-ssh-run.py root@192.168.1.100 "df -h" --password-base64 $pw
"""

import sys
import os
import base64
import argparse
from pathlib import Path

# 将技能根目录加入 sys.path
HERE = Path(__file__).resolve().parent
SKILL_HOME = HERE.parent
sys.path.insert(0, str(SKILL_HOME))

from agent_ssh_audit.crypto import (
    encrypt_password,
    decrypt_password,
    get_credential,
    store_credential,
    list_credentials,
    delete_credential,
    is_encrypted,
    migrate_if_needed,
)
from agent_ssh_audit import storage


def _cred_file() -> Path:
    """credentials.txt 路径"""
    return storage.get_home().parent / "credentials.txt"


def cmd_store(args):
    """加密存储密码"""
    pw = args.password
    if not pw:
        # 交互式输入（不回显）
        import getpass as gp
        pw = gp.getpass(f"请输入 {args.key} 的密码: ")
        confirm = gp.getpass("再次输入确认: ")
        if pw != confirm:
            print("错误: 两次输入不一致", file=sys.stderr)
            sys.exit(1)

    cf = _cred_file()
    store_credential(args.key, pw, cf)
    print(f"已加密存储: {args.key} → {cf}")


def cmd_get(args):
    """解密获取密码（Base64 输出）"""
    cf = _cred_file()
    pw = get_credential(args.key, cf)
    if pw is None:
        print(f"错误: 未找到凭据 '{args.key}'", file=sys.stderr)
        sys.exit(1)
    # 输出 Base64 编码（可直接用于 --password-base64）
    print(base64.b64encode(pw.encode("utf-8")).decode("ascii"))


def cmd_get_plain(args):
    """解密获取密码（明文，仅调试用）"""
    cf = _cred_file()
    pw = get_credential(args.key, cf)
    if pw is None:
        print(f"错误: 未找到凭据 '{args.key}'", file=sys.stderr)
        sys.exit(1)
    print(pw)


def cmd_list(args):
    """列出所有凭据"""
    cf = _cred_file()
    creds = list_credentials(cf)
    if not creds:
        print("(无凭据)")
        return

    # 表格输出
    max_key = max(len(k) for k, _ in creds) if creds else 10
    print(f"{'KEY':<{max_key}}  {'加密方式'}")
    print(f"{'-'*max_key}  {'-'*20}")
    for key, method in creds:
        flag = "✓" if method == "DPAPI" else "⚠"
        print(f"{key:<{max_key}}  {flag} {method}")

    legacy_count = sum(1 for _, m in creds if m != "DPAPI")
    if legacy_count:
        print(f"\n⚠ 有 {legacy_count} 条旧版凭据，运行 'migrate' 升级为 DPAPI 加密。")


def cmd_delete(args):
    """删除凭据"""
    cf = _cred_file()
    ok = delete_credential(args.key, cf)
    if ok:
        print(f"已删除: {args.key}")
    else:
        print(f"未找到: {args.key}", file=sys.stderr)
        sys.exit(1)


def cmd_migrate(args):
    """扫描并升级所有旧版凭据为 DPAPI"""
    cf = _cred_file()
    if not cf.exists():
        print("credentials.txt 不存在，无需迁移。")
        return

    lines = cf.read_text(encoding="utf-8-sig").splitlines()
    migrated = 0
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if not v:
            continue

        if is_encrypted(v):
            continue  # 已是 DPAPI，跳过
        # 尝试迁移（自动识别 Fernet / Base64 等旧格式）
        try:
            migrate_if_needed(k.strip(), v, cf)
            migrated += 1
            print(f"  已升级: {k.strip()}")
        except Exception as e:
            print(f"  升级失败: {k.strip()} — {e}", file=sys.stderr)

    if migrated:
        print(f"\n共升级 {migrated} 条凭据为 DPAPI 加密。")
    else:
        print("没有需要迁移的旧版凭据。")


def main():
    p = argparse.ArgumentParser(
        description="SSH 凭据管理 — Windows DPAPI 加密存储",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s store 192.168.1.100 MyP@ss         # 加密存储
  %(prog)s get 192.168.1.100                   # 获取 Base64（用于 --password-base64）
  %(prog)s get-plain 192.168.1.100             # 获取明文（调试用）
  %(prog)s list                                # 列出所有
  %(prog)s delete 192.168.1.100                # 删除
  %(prog)s migrate                             # 升级旧版凭据
        """,
    )
    sub = p.add_subparsers(dest="command", required=True)

    # store
    sp = sub.add_parser("store", help="加密存储密码")
    sp.add_argument("key", help="凭据标识（如 IP 或 user@host）")
    sp.add_argument("password", nargs="?", help="密码（省略则交互输入）")
    sp.set_defaults(func=cmd_store)

    # get
    sp = sub.add_parser("get", help="解密获取密码（Base64 输出）")
    sp.add_argument("key", help="凭据标识")
    sp.set_defaults(func=cmd_get)

    # get-plain
    sp = sub.add_parser("get-plain", help="解密获取密码（明文，调试用）")
    sp.add_argument("key", help="凭据标识")
    sp.set_defaults(func=cmd_get_plain)

    # list
    sp = sub.add_parser("list", help="列出所有凭据")
    sp.set_defaults(func=cmd_list)

    # delete
    sp = sub.add_parser("delete", help="删除凭据")
    sp.add_argument("key", help="凭据标识")
    sp.set_defaults(func=cmd_delete)

    # migrate
    sp = sub.add_parser("migrate", help="升级旧版凭据为 DPAPI 加密")
    sp.set_defaults(func=cmd_migrate)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
