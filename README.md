# SSH Audit — 带审计的 SSH 运维工具

让所有 SSH 操作**全程有据可查**：审计日志、危险命令告警、回放、命令学习日志。

---

## 快速开始

### 1. 安装

```powershell
# 以管理员身份运行 PowerShell，执行安装脚本
.\install.ps1
```

安装脚本会自动：
- 检测自带嵌入式 Python 3.11 运行时（无需系统安装 Python）
- 验证 paramiko 依赖
- 设置环境变量 `AGENT_SSH_AUDIT_HOME`
- 创建日志目录结构

### 2. 配置凭据

```powershell
# 加密存储 SSH 密码（Windows DPAPI 加密，绑定当前用户）
python\python.exe bin\agent-ssh-cred.py store <服务器IP>
```

### 3. 运行

```powershell
# 单条命令
python\python.exe bin\agent-ssh-run.py user@host "df -h" --password-base64 $pw

# 批量命令
python\python.exe bin\agent-ssh-run.py user@host --batch commands.txt --password-base64 $pw

# 交互式 Shell
python\python.exe bin\agent-ssh-shell.py user@host --password-base64 $pw
```

---

## AI 智能体使用案例

将本技能加载到 AI 智能体（如 QClaw / Claude / 自定义 Agent）后，可直接通过自然语言完成 SSH 运维。

### 首次对话示例

> **你：** 帮我看一下服务器 192.168.1.100 的磁盘使用情况
>
> **AI：** 好，我先检查一下这台服务器的凭据是否已配置。
>
> 未检测到 `192.168.1.100` 的凭据，首次使用需要你提供以下信息：
>
> 1. **SSH 用户名**（如 `root` 或你的登录账号）
> 2. **SSH 密码**（明文输入即可，AI 会调用 DPAPI 加密存储，不会明文展示）
> 3. **端口号**（默认 22，可按需修改）
>
> 请提供这些信息，我会先帮你加密保存凭据，再执行查询。

### 凭据配置完成后

> **你：** root，密码是 MyServer@2024，端口 22
>
> **AI：** 已收到，正在加密存储凭据…
>
> ✅ 凭据已通过 Windows DPAPI 加密保存（绑定当前用户，其他进程不可读）。
>
> 现在执行磁盘检查：
>
> ```bash
> ▶ 执行命令: df -h
> ```
> **作用：** 查看文件系统磁盘空间使用情况，`-h` 以人类可读格式显示（GB/MB）。
>
> **执行结果：**
> ```
> Filesystem      Size  Used Avail Use% Mounted on
> /dev/sda1        98G   45G   53G  46% /
> /dev/sdb1       500G  200G  300G  40% /data
> ```
> `/` 根分区使用 46%，`/data` 数据盘使用 40%，均在安全范围内，无需处理。

### 执行多条命令

> **你：** 顺便看看内存和负载
>
> **AI：** 好的，连续执行两条命令：
>
> ```bash
> ▶ 执行命令: free -h
> ```
> **作用：** 查看内存使用总量、已用/可用内存和交换分区。
>
> ```bash
> ▶ 执行命令: uptime
> ```
> **作用：** 显示系统运行时长、当前登录用户数和过去 1/5/15 分钟的平均负载。
>
> 内存充足，负载正常。完整记录已写入审计日志和学习日志。

### 危险命令触发告警

> **你：** 执行一下 rm -rf /
>
> **AI：** ⛔ **命令被拦截！**
>
> `rm -rf /` 触发了 **Critical 级别审计规则** —— 递归删除根目录，这是极其危险的操作。
>
> 安全起见，该命令**已记录但未执行**。如果你确实有清理需求，请明确说明具体路径和目的。

---

## 功能特性

| 功能 | 说明 |
|------|------|
| 🔐 **凭据安全** | Windows DPAPI 加密存储密码，绑定当前用户，其他进程不可读 |
| 📋 **审计日志** | 每条命令写入 JSONL 日志，含时间戳、session_id、命令、结果 |
| 🚨 **危险命令检测** | 内置 14 条规则（rm -rf /、mkfs、dd 等），命中即告警 |
| 🔍 **会话回放** | 可逐条回放历史命令执行过程 |
| 📚 **命令学习日志** | 独立 Markdown 日志，按天归档所有执行过的命令 |
| 🎤 **命令展示与解释** | AI 执行后逐条展示命令并解释作用 |
| 🐍 **嵌入式 Python** | 自带 Python 3.11 运行环境，无需系统安装 |

---

## 执行流程

![执行流程图](执行流程图.png)

整体工作流说明：

1. **凭据管理** — 通过 `agent-ssh-cred.py` 用 Windows DPAPI 加密存储密码
2. **命令执行** — `agent-ssh-run.py` 或 `agent-ssh-shell.py` 发起 SSH 连接
3. **审计检查** — 每条命令经过 14 条安全规则检测，命中即告警并记录
4. **日志归档** — JSONL 格式审计日志 + Markdown 命令学习日志双通道
5. **会话回放** — 通过 `agent-ssh-replay.py` 随时查看历史操作

---

## 目录结构

```
ssh-audit/
├── SKILL.md                    # 技能文档（详细用法）
├── install.ps1                 # 安装脚本
├── package.ps1                 # 打包脚本
├── requirements.txt            # Python 依赖
├── .gitignore
├── README.md
│
├── agent_ssh_audit/            # 核心库
│   ├── __init__.py
│   ├── client.py               # SSH 客户端（审计封装）
│   ├── crypto.py               # DPAPI 加解密
│   ├── rules.py                # 危险命令检测规则
│   ├── storage.py              # 日志存储
│   ├── recorder.py             # 事件记录器
│   ├── replay.py               # 会话回放
│   └── cmd_learner.py          # 命令学习日志
│
├── bin/                        # CLI 工具
│   ├── agent-ssh-run.py        # 执行 SSH 命令
│   ├── agent-ssh-shell.py      # 交互式 Shell
│   ├── agent-ssh-replay.py     # 会话回放
│   └── agent-ssh-cred.py       # 凭据管理
│
├── demo.py                     # 端到端演示
├── test_shell.py               # Shell 流程测试
│
├── python/                     # 嵌入式 Python 3.11 运行时
├── wheels/                     # Python 轮子文件（离线安装用）
└── logs/                       # 日志目录（自动生成）
    ├── sessions/               # 审计 session 日志
    └── cmds_learn/             # 命令学习日志（Markdown）
```

---

## 危险命令审计规则

内置 14 条审计规则，覆盖常见高危操作：

| 级别 | 规则 | 触发条件 |
|------|------|---------|
| 🔴 Critical | `rm -rf /` | 递归删除根目录 |
| 🔴 Critical | `rm -rf ~` | 删除家目录 |
| 🟡 Warn | `rm -rf` 绝对路径 | 删除非当前目录下的路径 |
| 🔴 Critical | `dd of=/dev/sd*` | 磁盘直接写入 |
| 🔴 Critical | `mkfs` | 格式化磁盘 |
| 🔴 Critical | `chmod 777 /` | 修改根目录权限 |
| 🔴 Critical | `chown ... /` | 修改根目录属主 |
| 🔴 Critical | `curl url \| bash` | 管道执行远程脚本 |
| 🟡 Warn | `reboot/shutdown/halt` | 重启/关机 |
| 🔴 Critical | `systemctl stop ssh` | 禁用 SSH 服务 |
| 🟡 Warn | `iptables -F` | 清空防火墙规则 |
| 🟡 Warn | `passwd/useradd/userdel` | 用户管理操作 |
| 🔴 Critical | 编辑 `/etc/passwd` 等 | 修改系统配置文件 |
| 🟡 Warn | `history -c` | 清除命令历史 |

---

## 安全说明

- 密码通过 **Windows DPAPI** 加密存储，绑定当前 Windows 用户
- 即使 `credentials.txt` 泄露，脱离加密时的用户会话无法解密
- 禁止在脚本/回复中展示明文密码
- 所有 SSH 操作强制走审计通道，禁止裸 `paramiko`/`subprocess ssh`
