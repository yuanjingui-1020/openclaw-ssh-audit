# SSH Audit — 带审计的 SSH 运维工具

让所有 SSH 操作**全程有据可查**：审计日志、危险命令告警、回放、命令学习日志。

---

## 一键安装提示词

将下方内容**完整复制**发送给 AI 智能体，它会自动完成：克隆仓库 → 安装技能 → 加载使用。

```
请帮我安装并加载 SSH Audit 技能，仓库地址是：
https://github.com/yuanjingui-1020/openclaw-ssh-audit.git

操作步骤：
1. 克隆该仓库到本地
2. 将仓库中的 SKILL.md 加载为技能
3. 技能加载成功后，告诉我技能已就绪，可以开始使用
```

---

## 快速开始

### 1. 安装

```powershell
# 以管理员身份运行 PowerShell，执行安装脚本
.\install.ps1
```

安装脚本会自动：
- 检测系统 Python 3（需用户自行安装）
- 安装 paramiko 依赖
- 设置环境变量 `AGENT_SSH_AUDIT_HOME`
- 创建日志目录结构

### 2. 配置凭据

```powershell
# 加密存储 SSH 密码（Windows DPAPI 加密，绑定当前用户）
python bin\agent-ssh-cred.py store <服务器IP>
```

### 3. 运行

```powershell
# 单条命令
python bin\agent-ssh-run.py user@host "df -h" --password-base64 $pw

# 批量命令
python bin\agent-ssh-run.py user@host --batch commands.txt --password-base64 $pw

# 交互式 Shell
python bin\agent-ssh-shell.py user@host --password-base64 $pw
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
> 2. **SSH 密码**
> 3. **端口号**（默认 22，可按需修改）
>
> 请问是否需要我帮你将密码加密保存到本地？这样后续使用就无需再次输入密码。如果不需要保存，我会在本次会话中直接使用。

### 凭据配置完成后（不保存，一次性使用）

> **你：** root，密码是 MyServer@2024，端口 22，不保存
>
> **AI：** 好的，使用一次性密码进行连接（本次会话有效，密码不会写入磁盘）。
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

### 审计回放与日志查询

> **你：** 把今天所有的操作记录回放给我看
>
> **AI：** 好的，正在读取今日审计日志…
>
> 你今天的操作摘要：
> | 时间 | 目标主机 | 命令 | session_id |
> |------|----------|------|------------|
> | 00:15 | root@192.168.1.100 | df -h | s_001 |
> | 00:16 | root@192.168.1.100 | free -h | s_001 |
> | 00:16 | root@192.168.1.100 | uptime | s_001 |
>
> 审计日志文件位于：
> ```
> logs/sessions/YYYY-MM-DD.jsonl
> ```
> ⚠️ **注意：** 该文件内命令内容和执行结果经过加密，不支持直接 Notepad / cat 阅读。
>
> 必须通过回放工具解密查看：
> ```powershell
> # 按 session ID 回放（解密展示）
> python bin\agent-ssh-replay.py logs\sessions\YYYY-MM-DD.jsonl --session s_001
>
> # 回放并显示详细信息
> python bin\agent-ssh-replay.py logs\sessions\YYYY-MM-DD.jsonl --session s_001 --verbose
> ```

### 命令学习日志（纯命令行教程）

每次操作后，AI 会自动将执行的命令按天归档到独立的 Markdown 学习日志中，便于复盘回顾。

> **日志路径：** `logs/cmds_learn/YYYY-MM-DD.md`

**手动查看命令学习日志：**

```powershell
# 直接查看今日的学习日志
notepad logs/cmds_learn/$(Get-Date -Format 'yyyy-MM-dd').md

# 在 PowerShell 中预览
Get-Content logs/cmds_learn/$(Get-Date -Format 'yyyy-MM-dd').md -Head 30

# 查看历史某天的记录
Get-Content logs/cmds_learn/2026-07-11.md
```

**学习日志内容示例：**

```markdown
# 命令学习日志 — 2026-07-11

## 22:35 | root@192.168.1.100 | session: s_001

```bash
▶ df -h
▶ free -h
▶ uptime
▶ ip addr
```

## 22:40 | testuser@192.168.1.100 | session: s_002

```bash
▶ systemctl status nginx
▶ journalctl -u nginx --no-pager -n 50
```
```

**纯命令行动作流程（无需 AI，直接终端操作）：**

```powershell
# 1. 加密存密码（首次）
python bin\agent-ssh-cred.py store 192.168.1.100

# 2. 执行单条命令
python bin\agent-ssh-run.py root@192.168.1.100 "df -h" --password-base64 (Get-Content credentials.txt)

# 3. 批量执行
python bin\agent-ssh-run.py root@192.168.1.100 --batch commands.txt --password-base64 (Get-Content credentials.txt)

# 4. 交互式 Shell
python bin\agent-ssh-shell.py root@192.168.1.100 --password-base64 (Get-Content credentials.txt)

# 5. 回放历史 session
python bin\agent-ssh-replay.py logs\sessions\2026-07-11.jsonl --session s_001

# 6. 查看今日学习日志
Get-Content logs/cmds_learn/$(Get-Date -Format 'yyyy-MM-dd').md
```

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
│   ├── recorder.py              # 事件记录器
│   ├── replay.py               # 会话回放
│   └── cmd_learner.py          # 命令学习日志
│
├── bin/                        # CLI 工具
│   ├── agent-ssh-run.py        # 执行 SSH 命令
│   ├── agent-ssh-shell.py      # 交互式 Shell
│   ├── agent-ssh-replay.py     # 会话回放
│   └── agent-ssh-cred.py        # 凭据管理
│
├── demo.py                     # 端到端演示
├── test_shell.py               # Shell 流程测试
│
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
